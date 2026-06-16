"""Replay WunderSpec ITF traces against the DNS control-plane MBT harness."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
LAB_ROOT = REPO_ROOT / "dns-control-plane-lab"
sys.path.insert(0, str(LAB_ROOT))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from dns_control_plane.constants import (  # noqa: E402
    DEPLOYERS,
    DNS_CLOUDDB_LOCK_NAME,
    DNS_CLOUDDB_ROLLBACK_NAME,
    DNS_CLOUDDB_ROOT_NAME,
)
from dns_control_plane.deployer import (  # noqa: E402
    Deployer,
    PLAN_TREES_TO_KEEP_AFTER_DEPLOY,
)
from dns_control_plane.mbt_harness import create_mbt_router  # noqa: E402
from dns_control_plane.models import DnsAliasTarget, DnsBatchChange, DnsRecord  # noqa: E402
from dns_control_plane.planner import Planner  # noqa: E402
from dns_control_plane.wormhole53 import Wormhole53Store  # noqa: E402
from trace_parser import load_itf_traces, parse_itf_traces, unwrap_itf  # noqa: E402


INIT_PLAN_NAME = "plan-init.cdb.acme"
INIT_LB_NAME = "lb-init.cdb.acme"
GREEN = "\033[32m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"
GREEN_OK = f"{GREEN}[OK]{RESET}"
RED_FAIL = f"{RED}[FAIL]{RESET}"


class ItfReplaySystem:
    def __init__(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(prefix="dns-control-plane-mbt-")
        s3 = Path(self._tmpdir.name) / "s3-persistence"

        self.wormhole53 = Wormhole53Store(s3 / "current_dns_zone.json")
        self.planner = Planner(s3 / "plans")
        self.deployers = {
            name: Deployer(name, self.wormhole53, self.planner)
            for name in DEPLOYERS
        }

        app = FastAPI(title="ACME Cloud DNS Control Plane ITF Replay")
        app.include_router(
            create_mbt_router(
                wormhole53=self.wormhole53,
                deployers=self.deployers,
                planner=self.planner,
            )
        )
        self.client = TestClient(app)
        self.model_plan_versions: dict[str, int] = {}
        self.history: list[str] = []

    def close(self) -> None:
        self.client.close()
        self._tmpdir.cleanup()

    def replay_state(self, state: dict[str, Any]) -> str:
        ghost_action = state["ghost_action"]
        action = str(ghost_action["tag"])
        value = unwrap_itf(ghost_action.get("value")) if ghost_action.get("value") is not None else {}
        step = state.get("#meta", {}).get("step", len(self.history))

        deployer = None
        if action in {"Sync", "Deploy", "Backoff", "Cleanup"}:
            deployer = str(value["deployer"])
            if deployer not in DEPLOYERS:
                raise AssertionError(f"unknown deployer in ITF: {deployer!r}")

        if action == "Init":
            response = self._post("/mbt/reset")
            self._seed_init_plan()
            history_entry = self._history_entry("reset", response)
        elif action == "GeneratePlan":
            response = self._post("/mbt/planner/generate", self._planner_body(value))
            self.model_plan_versions[str(value["plan_id"])] = int(response["version"])
            history_entry = self._history_entry("generate", response)
        elif action == "Sync":
            response = self._post(f"/mbt/deployers/{deployer}/sync")
            history_entry = self._history_entry(f"sync:{deployer}", response)
        elif action == "Deploy":
            response = self._post(f"/mbt/deployers/{deployer}/deploy")
            expected = self.model_plan_versions.get(str(value["plan_id"]))
            if response.get("message") == "installed" and expected is not None:
                assert response["version"] == expected
                self._post(f"/mbt/deployers/{deployer}/sync")
            history_entry = self._history_entry(f"deploy:{deployer}", response)
        elif action == "Backoff":
            response = self._post(f"/mbt/deployers/{deployer}/deploy")
            assert response.get("ok") is False, response
            history_entry = self._history_entry(f"deploy:{deployer}", response)
        elif action == "Cleanup":
            response = self._post(
                f"/mbt/deployers/{deployer}/cleanup",
                {"keep_last_n": PLAN_TREES_TO_KEEP_AFTER_DEPLOY},
            )
            history_entry = self._history_entry(f"cleanup:{deployer}", response)
        else:
            raise AssertionError(f"unsupported ITF ghost_action action: {action!r}")

        self.history.append(history_entry)
        self._assert_root_resolvable_or_init(step=step, action=action, response=response)
        return history_entry

    def _planner_body(self, action: dict[str, Any]) -> list[dict[str, int]]:
        weights = dict(action["weights"])
        load_balancer_ids: dict[str, int] = {}
        for ip_addr in action["ips"]:
            try:
                load_balancer_ids[ip_addr] = int(ip_addr.rsplit(".", maxsplit=1)[1])
            except (IndexError, ValueError) as exc:
                raise AssertionError(
                    f"cannot map ITF IP to lab load balancer id: {ip_addr!r}"
                ) from exc

        ips = sorted(action["ips"], key=load_balancer_ids.__getitem__)
        return [{"id": load_balancer_ids[ip], "weight": int(weights[ip])} for ip in ips]

    def _history_entry(self, action: str, response: dict[str, Any]) -> str:
        version = f" version={response['version']}" if "version" in response else ""
        return f"{action}{version} {GREEN_OK}"

    def _post(self, path: str, body: Any = None) -> dict[str, Any]:
        response = self.client.post(path, json=body) if body is not None else self.client.post(path)
        assert response.status_code == 200, response.text
        return response.json()

    def _seed_init_plan(self) -> None:
        lock_record = DnsRecord(name=DNS_CLOUDDB_LOCK_NAME, type="TXT", value="genesis 0")
        root_record = DnsRecord(name=DNS_CLOUDDB_ROOT_NAME, type="ALIAS", value=INIT_PLAN_NAME)
        records = [
            lock_record,
            root_record,
            DnsRecord(name=DNS_CLOUDDB_ROLLBACK_NAME, type="ALIAS", value=INIT_PLAN_NAME),
            DnsRecord(
                name=INIT_PLAN_NAME,
                type="ALIAS",
                value=[DnsAliasTarget(name=INIT_LB_NAME, weight=100)],
            ),
        ]
        self.wormhole53.change_record_sets(
            [DnsBatchChange(type="CREATE", record=record) for record in records]
        )
        for deployer in self.deployers.values():
            deployer.latest_observed_lock = lock_record
            deployer.latest_observed_root = root_record

    def _assert_root_resolvable_or_init(self, *, step: int, action: str, response: dict[str, Any]) -> None:
        ips = self.wormhole53.resolve(DNS_CLOUDDB_ROOT_NAME)
        if ips or self._root_targets_init_plan():
            return

        root = self.wormhole53.get(DNS_CLOUDDB_ROOT_NAME, "ALIAS")
        rollback = self.wormhole53.get(DNS_CLOUDDB_ROLLBACK_NAME, "ALIAS")
        records = [
            record.model_dump(mode="json")
            for record in sorted(
                self.wormhole53._internal__list_records(),
                key=lambda item: (item.name, item.type),
            )
        ]
        details = [
            f"step={step}",
            f"action={action}",
            f"response={response}",
            f"model_plan_versions={self.model_plan_versions}",
            f"root_record={root.model_dump(mode='json') if root else None}",
            f"rollback_record={rollback.model_dump(mode='json') if rollback else None}",
            f"records={records}",
        ]
        raise AssertionError(
            f"{DNS_CLOUDDB_ROOT_NAME} resolved to zero IPs\n" + "\n".join(details)
        )

    def _root_targets_init_plan(self) -> bool:
        root = self.wormhole53.get(DNS_CLOUDDB_ROOT_NAME, "ALIAS")
        return bool(root and isinstance(root.value, str) and "init" in root.value)


def replay_trace(trace: dict[str, Any], *, label: str) -> bool:
    system = ItfReplaySystem()
    try:
        print(f"Replaying {BOLD}{label}{RESET}")
        for state in trace["states"]:
            print(f"  {system.replay_state(state)}")
        return True
    except AssertionError as exc:
        print(f"  {RED_FAIL}")
        print(format_failure(str(exc), prefix="  "))
        return False
    finally:
        print()
        system.close()


def format_failure(text: str, *, prefix: str) -> str:
    lines = text.splitlines()
    if not lines:
        return ""

    formatted = [f"{RED}{prefix}{lines[0]}{RESET}"]
    formatted.extend(f"{prefix}{line}" for line in lines[1:])
    return "\n".join(formatted)


def load_input_traces(input_path: str) -> list[dict[str, Any]]:
    if input_path == "-":
        return parse_itf_traces(sys.stdin.read(), source="<stdin>")
    return load_itf_traces(Path(input_path))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Replay WunderSpec ITF traces against the DNS control-plane MBT harness."
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        metavar="ITF",
        help="ITF JSON or NDJSON input file. Use '-' to read from stdin.",
    )
    args = parser.parse_args(argv)

    failed = 0
    total = 0
    for input_path in args.inputs:
        traces = load_input_traces(input_path)
        for index, trace in enumerate(traces):
            suffix = f"[{index}]" if len(traces) > 1 else ""
            total += 1
            if not replay_trace(trace, label=f"{input_path}{suffix}"):
                failed += 1

    if failed:
        print(f"{RED}{failed} of {total} test(s) failed{RESET}")
        return 1

    print(f"{GREEN}0 of {total} test(s) failed{RESET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
