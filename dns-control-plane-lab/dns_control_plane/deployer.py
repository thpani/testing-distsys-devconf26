from __future__ import annotations

import asyncio
import json
import os
import random
from typing import Any

from .constants import DNS_CLOUDDB_LOCK_NAME, DNS_CLOUDDB_ROLLBACK_NAME, DNS_CLOUDDB_ROOT_NAME
from .models import DnsBatchChange, DnsRecord
from .planner import Planner
from .wormhole53 import DnsBatchChangeBatchError, Wormhole53Store

DEPLOYER_INTERVAL = float(os.environ.get("DNS_LAB_DEPLOYER_INTERVAL_SECONDS", "0.25"))
DEPLOYER_JITTER = float(os.environ.get("DNS_LAB_DEPLOYER_JITTER_SECONDS", str(DEPLOYER_INTERVAL)))
PLAN_TREES_TO_KEEP_AFTER_DEPLOY = 3


class Deployer:
    """Installs planner-generated DNS trees into Wormhole53.

    A deploy operation does three things in one Wormhole53 transaction:

    1. compare-and-swap the TXT lock record,
    2. upsert the plan's DNS tree and flip the stable CloudDB root alias,
    3. update rollback metadata to the previous root target.

    Cleanup is a separate deployer action. The autonomous deployer loop runs a
    cleanup pass after a successful install.
    """

    def __init__(self, name: str, wormhole53: Wormhole53Store, planner: Planner):
        self.name = name
        self.wormhole53 = wormhole53
        self.planner = planner

        self.lock_epoch = 0
        self.next_plan_version = 1

        self.latest_observed_lock = None
        self.latest_observed_root = None

    # Plan deployment behavior ---------------------------------------------

    def sync_dns_state(self) -> dict[str, Any]:
        self.latest_observed_lock = self.wormhole53.get(DNS_CLOUDDB_LOCK_NAME, "TXT")
        self.latest_observed_root = self.wormhole53.get(DNS_CLOUDDB_ROOT_NAME, "ALIAS")

        return { "ok": True, "lock": self.latest_observed_lock, "root": self.latest_observed_root }

    def deploy_once(self) -> dict[str, Any]:
        plan_file = self.planner.path / f"plan-{self.next_plan_version:03d}.json"
        if not plan_file.exists():
            return {"ok": True, "message": "idle"}
        plan = json.loads(plan_file.read_text())

        try:
            self.wormhole53.change_record_sets(self._deployment_batch(plan))
        except DnsBatchChangeBatchError as exc:
            return {"ok": False, "message": str(exc)}

        self.next_plan_version += 1

        return {"ok": True, "message": "installed", "version": plan["version"]}

    def cleanup_once(self, keep_last_n: int) -> dict[str, Any]:
        first_kept_version = self.next_plan_version - keep_last_n
        versions_to_delete = set(range(1, max(1, first_kept_version)))

        changes: list[DnsBatchChange] = []
        deleted_versions: set[int] = set()
        for record in self.wormhole53._internal__list_records():
            version = record.plan_version()
            if version not in versions_to_delete:
                continue
            changes.append(DnsBatchChange(type="DELETE", record=record))
            deleted_versions.add(version)

        if not changes:
            return {"ok": True, "deleted_versions": []}

        try:
            self.wormhole53.change_record_sets(changes)
        except DnsBatchChangeBatchError as exc:
            return {"ok": False, "message": str(exc)}
        return {"ok": True, "deleted_versions": sorted(deleted_versions)}

    # Helpers ---------------------------------------------------------------

    def _deployment_batch(self, plan: dict[str, Any]) -> list[DnsBatchChange]:
        # Rollback target cases:
        # - Normal deploy: root=plan-004, installing plan-005 -> rollback=plan-004.
        # - Idempotent/catch-up deploy: root=plan-004, installing plan-004 ->
        #   leave the existing rollback record unchanged.
        # - First (bootstrapped) deploy: no root, installing plan-001 -> do not
        #   set a rollback.
        rollback_target = None
        if self.latest_observed_root:
            # non-initial deploy
            if self.latest_observed_root.value != plan["plan_name"]:
                # non-idempotent deploy, set rollback to the old root target
                rollback_target = self.latest_observed_root.value
                # safeguard: rollback must always point to an existing plan
                if self.wormhole53.get(self.latest_observed_root.value, "ALIAS") is None:
                    raise DnsBatchChangeBatchError(f"current root target is missing: {self.latest_observed_root.value}")

        # Prepare the new "lock" value.
        # This is actually a fence / compare-and-swap guard to ensure we are not
        # operating on stale state.
        # See: https://youtu.be/YZUNNzLDWb8?si=QX6meB4oOYZmWzEF&t=973
        self.lock_epoch += 1
        new_lock = DnsRecord(
            name=DNS_CLOUDDB_LOCK_NAME,
            type="TXT",
            value=f"{self.name} {self.lock_epoch}",
        )

        # Compare-and-swap preamble: delete the exact lock value we observed,
        # then create our new lock value in the same transactional batch as the
        # DNS changes. If another deployer changed the lock, the DELETE mismatches
        # and Wormhole53 rejects the whole batch.
        # Followed by upserts for all records in the new plan, the root alias,
        # and the rollback alias when there is a previous root.
        # See: https://youtu.be/YZUNNzLDWb8?si=QX6meB4oOYZmWzEF&t=973
        return [
            *([DnsBatchChange(type="DELETE", record=self.latest_observed_lock)] if self.latest_observed_lock else []),
            DnsBatchChange(type="CREATE", record=new_lock),
            *[
                DnsBatchChange(
                    type="UPSERT",
                    record=DnsRecord.model_validate(record_data),
                )
                for record_data in plan["records"]
            ],
            DnsBatchChange(
                type="UPSERT",
                record=DnsRecord(
                    name=DNS_CLOUDDB_ROOT_NAME,
                    type="ALIAS",
                    value=plan["plan_name"],
                ),
            ),
            *(
                [
                    DnsBatchChange(
                        type="UPSERT",
                        record=DnsRecord(
                            name=DNS_CLOUDDB_ROLLBACK_NAME,
                            type="ALIAS",
                            value=rollback_target,
                        ),
                    )
                ]
                if rollback_target
                else []
            ),
        ]

    # Internal ACME Cloud routes -------------------------------------------------

    def _internal__reset(self) -> None:
        """Reset local deployer progress for the MBT harness."""
        self.next_plan_version = 1
        self.lock_epoch = 0
        self.latest_observed_lock = None
        self.latest_observed_root = None


# Launched autonomous behavior ---------------------------------------------


async def deployer_loop(deployer: Deployer) -> None:
    # Without a small independent offset, asyncio schedules deployer-a/b/c in
    # creation order every cycle. Since deploy_once is synchronous, the last
    # created task tends to make the final write for each plan. Jitter makes the
    # autonomous loops behave more like independent workers.
    await asyncio.sleep(random.uniform(0, DEPLOYER_JITTER))
    while True:
        deployer.sync_dns_state()
        result = deployer.deploy_once()
        if result.get("ok") and result.get("message") == "installed":
            deployer.cleanup_once(keep_last_n=PLAN_TREES_TO_KEEP_AFTER_DEPLOY)
        await asyncio.sleep(DEPLOYER_INTERVAL + random.uniform(0, DEPLOYER_JITTER))
