from __future__ import annotations

import json
import threading
from pathlib import Path

from .models import DnsAliasTarget, DnsBatchChange, DnsRecord


class DnsBatchChangeBatchError(Exception):
    pass


class Wormhole53Store:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.RLock()
        self.records: dict[str, DnsRecord] = {}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self.records = {r.key(): r for r in [DnsRecord.model_validate(item) for item in json.loads(self.path.read_text())]}
        else:
            self._persist()

    # Public Wormhole53 API -------------------------------------------------

    def get(self, name: str, type: str) -> DnsRecord | None:
        with self._lock:
            return self.records.get(f"{name}|{type}")

    def resolve(self, name: str) -> list[str]:
        with self._lock:
            return self._resolve_unlocked(name, visited=set())

    def change_record_sets(self, changes: list[DnsBatchChange]) -> None:
        with self._lock:
            copy = dict(self.records)
            for change in changes:
                key = change.record.key()
                existing = copy.get(key)
                if change.type == "CREATE":
                    if existing is not None:
                        raise DnsBatchChangeBatchError(f"record already exists: {key}")
                    copy[key] = change.record
                elif change.type == "DELETE":
                    if existing is None:
                        raise DnsBatchChangeBatchError(f"record missing: {key}")
                    if existing.model_dump(mode="json") != change.record.model_dump(mode="json"):
                        raise DnsBatchChangeBatchError(f"record mismatch: {key}")
                    del copy[key]
                elif change.type == "UPSERT":
                    copy[key] = change.record
                else:
                    raise DnsBatchChangeBatchError(f"unknown action: {change.type}")
            self.records = copy
            self._persist()

    # Helpers ---------------------------------------------------------------

    def _resolve_unlocked(self, name: str, visited: set[str]) -> list[str]:
        # Alias cycles are invalid DNS trees. Treat a cycle as an unresolved branch.
        if name in visited:
            return []
        visited.add(name)

        # A records are leaf records: resolution has found one concrete IPv4 address.
        arec = self.records.get(f"{name}|A")
        if arec and isinstance(arec.value, str):
            return [arec.value]

        # Missing aliases are the outage shape we care about: a root/branch points
        # at a plan-tree record that cleanup has already deleted.
        alias = self.records.get(f"{name}|ALIAS")
        if not alias:
            return []

        # Simple alias: follow a single target name.
        if isinstance(alias.value, str):
            return self._resolve_unlocked(alias.value, visited)

        # Weighted alias fanout: this lab resolver deterministically returns all
        # reachable leaf IPs rather than randomly choosing by weight.
        ips: list[str] = []
        for target in alias.value:
            target_name = target.name if isinstance(target, DnsAliasTarget) else target["name"]
            ips.extend(self._resolve_unlocked(target_name, set(visited)))
        return ips

    def _persist(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        data = [r.model_dump(mode="json") for r in self.records.values()]
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
        tmp.replace(self.path)

    # Internal ACME Cloud routes ---------------------------------

    def _internal__list_records(self) -> list[DnsRecord]:
        """Return all hosted-zone records for internal inspection.

        This is not part of the public Wormhole53 API. Public callers should use
        resolution; the control plane uses full-zone inspection for cleanup and
        the local HTML frontend.
        """
        with self._lock:
            return list(self.records.values())

    def _internal__reset(self) -> None:
        """Clear the hosted zone.

        This is deliberately not part of the public Wormhole53 API.
        """
        with self._lock:
            self.records = {}
            self._persist()
