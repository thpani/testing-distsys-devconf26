from __future__ import annotations

import asyncio
import json
import os
import random
import threading
from pathlib import Path
from typing import Any

from .constants import DNS_CLOUDDB_ROOT_NAME
from .models import DnsAliasTarget, LoadBalancerPlanInput, DnsRecord

PLANNER_INTERVAL = float(os.environ.get("DNS_LAB_PLANNER_INTERVAL_SECONDS", "5.0"))
DNS_PLAN_NAME_FORMAT = "plan-{version:03d}.cdb.acme"
LOADBALANCER_NAME_FORMAT = "lb-{plan_version:03d}-{lb_id}.cdb.acme"


class Planner:
    """Creates immutable intended DNS plans and persists them as JSON."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.RLock()
        self.path.mkdir(parents=True, exist_ok=True)
        existing = [int(p.stem.split("-")[1]) for p in self.path.glob("plan-*.json")]
        self._next_version = max(existing, default=0) + 1

    # Plan generation behavior ----------------------------------------

    def generate(self, plan: list[LoadBalancerPlanInput] | None = None) -> dict[str, Any]:
        plan = plan or [LoadBalancerPlanInput(id=1, weight=1)]
        with self._lock:
            version = self._next_version
            self._next_version += 1
            plan_json = _build_plan_json(version, plan)
            self._persist(version, plan_json)
        return plan_json

    # Helpers ---------------------------------------------------------

    def _persist(self, version: int, plan_json: dict[str, Any]) -> None:
        path = self.path / f"plan-{version:03d}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(plan_json, indent=2))
        tmp.replace(path)

    # Internal ACME Cloud routes --------------------------------------

    def _internal__reset(self) -> None:
        """Clear generated plans for the MBT harness."""
        with self._lock:
            for file in self.path.glob("plan-*.json"):
                file.unlink()
            self._next_version = 1


# Helpers -------------------------------------------------------------------


def _build_plan_json(version: int, plan: list[LoadBalancerPlanInput]) -> dict[str, Any]:
    plan_name = DNS_PLAN_NAME_FORMAT.format(version=version)
    load_balancers = sorted(plan, key=lambda lb: lb.id)
    dns_tree = [
        DnsRecord(
            name=plan_name,
            type="ALIAS",
            value=[_alias_target(version, lb) for lb in load_balancers],
        ),
        *[_address_record(version, lb) for lb in load_balancers],
    ]
    return {
        "version": version,
        "root": DNS_CLOUDDB_ROOT_NAME,
        "plan_name": plan_name,
        "records": [record.model_dump(mode="json") for record in dns_tree],
    }


def _alias_target(plan_version: int, lb: LoadBalancerPlanInput) -> DnsAliasTarget:
    return DnsAliasTarget(name=_load_balancer_name(plan_version, lb.id), weight=lb.weight)


def _address_record(plan_version: int, lb: LoadBalancerPlanInput) -> DnsRecord:
    return DnsRecord(name=_load_balancer_name(plan_version, lb.id), type="A", value=f"192.0.{plan_version % 256}.{lb.id}")


def _load_balancer_name(plan_version: int, lb_id: int) -> str:
    return LOADBALANCER_NAME_FORMAT.format(plan_version=plan_version, lb_id=lb_id)


# Launched autonomous behavior ---------------------------------------------
#
# In a real system, planner work would be triggered externally by changing
# service load/capacity signals. For this simulation/workshop, we choose random
# weights and keep increasing load_balancer_count to mimic growing load.


async def planner_loop(planner: Planner) -> None:
    while True:
        plan_count = len(list(planner.path.glob("plan-*.json")))
        load_balancer_count = 2 + min(plan_count // 3, 6)
        planner.generate(plan=_random_plan(load_balancer_count))
        await asyncio.sleep(PLANNER_INTERVAL)


def _random_plan(load_balancer_count: int) -> list[LoadBalancerPlanInput]:
    return [
        LoadBalancerPlanInput(id=lb_number, weight=random.randint(90, 120))
        for lb_number in range(1, load_balancer_count + 1)
    ]
