from pathlib import Path

import pytest

from dns_control_plane.constants import DNS_CLOUDDB_LOCK_NAME, DNS_CLOUDDB_ROLLBACK_NAME, DNS_CLOUDDB_ROOT_NAME
from dns_control_plane.deployer import Deployer
from dns_control_plane.models import DnsBatchChange, DnsRecord
from dns_control_plane.planner import Planner
from dns_control_plane.wormhole53 import DnsBatchChangeBatchError, Wormhole53Store


def test_create_delete_upsert_are_transactional(tmp_path: Path):
    store = Wormhole53Store(tmp_path / "current_dns_zone.json")
    a = DnsRecord(name="example.com", type="A", value="192.0.2.1")
    b = DnsRecord(name="other.example.com", type="A", value="192.0.2.2")

    store.change_record_sets([DnsBatchChange(type="CREATE", record=a)])

    with pytest.raises(DnsBatchChangeBatchError):
        store.change_record_sets([
            DnsBatchChange(type="UPSERT", record=b),
            DnsBatchChange(type="CREATE", record=a),
        ])

    assert store.get("example.com", "A") == a
    assert store.get("other.example.com", "A") is None


def test_delete_requires_exact_value(tmp_path: Path):
    store = Wormhole53Store(tmp_path / "current_dns_zone.json")
    actual = DnsRecord(name=DNS_CLOUDDB_LOCK_NAME, type="TXT", value="deployer-a 1")
    stale = DnsRecord(name=DNS_CLOUDDB_LOCK_NAME, type="TXT", value="deployer-b 1")

    store.change_record_sets([DnsBatchChange(type="CREATE", record=actual)])

    with pytest.raises(DnsBatchChangeBatchError):
        store.change_record_sets([DnsBatchChange(type="DELETE", record=stale)])

    assert store.get(DNS_CLOUDDB_LOCK_NAME, "TXT") == actual


def test_redeploying_current_plan_preserves_rollback_pointer(tmp_path: Path):
    s3 = tmp_path / "s3-persistence"
    wormhole53 = Wormhole53Store(s3 / "current_dns_zone.json")
    planner = Planner(s3 / "plans")
    deployer_a = Deployer("deployer-a", wormhole53, planner)
    deployer_b = Deployer("deployer-b", wormhole53, planner)

    planner.generate()
    planner.generate()

    deployer_a.sync_dns_state()
    assert deployer_a.deploy_once()["version"] == 1
    deployer_a.sync_dns_state()
    assert deployer_a.deploy_once()["version"] == 2
    assert wormhole53.get(DNS_CLOUDDB_ROOT_NAME, "ALIAS").value == "plan-002.cdb.acme"
    assert wormhole53.get(DNS_CLOUDDB_ROLLBACK_NAME, "ALIAS").value == "plan-001.cdb.acme"

    # Deployer B catches up. Its second deployment re-applies the already-active
    # plan-002 tree, so it should not collapse rollback to the current root.
    deployer_b.sync_dns_state()
    assert deployer_b.deploy_once()["version"] == 1
    deployer_b.sync_dns_state()
    assert deployer_b.deploy_once()["version"] == 2
    assert wormhole53.get(DNS_CLOUDDB_ROOT_NAME, "ALIAS").value == "plan-002.cdb.acme"
    assert wormhole53.get(DNS_CLOUDDB_ROLLBACK_NAME, "ALIAS").value == "plan-001.cdb.acme"
