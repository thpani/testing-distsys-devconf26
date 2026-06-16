from pathlib import Path

from dns_control_plane.constants import DEPLOYERS, DNS_CLOUDDB_ROOT_NAME, DNS_CLOUDDB_ROLLBACK_NAME
from dns_control_plane.deployer import Deployer
from dns_control_plane.planner import Planner
from dns_control_plane.wormhole53 import Wormhole53Store


def make_system(tmp_path: Path):
    s3 = tmp_path / "s3-persistence"
    wormhole53 = Wormhole53Store(s3 / "current_dns_zone.json")
    planner = Planner(s3 / "plans")
    deployers = {name: Deployer(name, wormhole53, planner) for name in DEPLOYERS}
    return wormhole53, planner, deployers


def test_stale_deployer_plus_cleanup_can_break_root_resolution(tmp_path: Path):
    wormhole53, planner, deployers = make_system(tmp_path)

    planner.generate()  # plan 001
    deployers["deployer-a"].sync_dns_state()
    assert deployers["deployer-a"].deploy_once()["ok"]
    assert wormhole53.resolve(DNS_CLOUDDB_ROOT_NAME) == ["192.0.1.1"]
    assert wormhole53.get(DNS_CLOUDDB_ROLLBACK_NAME, "ALIAS") is None

    # Generate four more plans, but do not schedule a deployer run yet.
    planner.generate()  # plan 002
    planner.generate()  # plan 003
    planner.generate()  # plan 004
    planner.generate()  # plan 005

    # Newer plans become active while deployer-c has not been scheduled yet.
    deployers["deployer-a"].sync_dns_state()
    assert deployers["deployer-a"].deploy_once()["version"] == 2
    deployers["deployer-a"].sync_dns_state()
    assert deployers["deployer-a"].deploy_once()["version"] == 3
    deployers["deployer-b"].sync_dns_state()
    assert deployers["deployer-b"].deploy_once()["version"] == 1
    deployers["deployer-b"].sync_dns_state()
    assert deployers["deployer-b"].deploy_once()["version"] == 2
    deployers["deployer-b"].sync_dns_state()
    assert deployers["deployer-b"].deploy_once()["version"] == 3
    deployers["deployer-b"].sync_dns_state()
    assert deployers["deployer-b"].deploy_once()["version"] == 4
    assert wormhole53.get(DNS_CLOUDDB_ROOT_NAME, "ALIAS").value == "plan-004.cdb.acme"

    # When deployer-c finally runs, it starts from local progress 1 and installs stale plan 001.
    deployers["deployer-c"].sync_dns_state()
    result = deployers["deployer-c"].deploy_once()
    assert result["ok"] and result["version"] == 1
    assert wormhole53.get(DNS_CLOUDDB_ROOT_NAME, "ALIAS").value == "plan-001.cdb.acme"
    assert wormhole53.get(DNS_CLOUDDB_ROLLBACK_NAME, "ALIAS").value == "plan-004.cdb.acme"

    # Unsafe version-based cleanup deletes the old tree now referenced by root.
    # OUTAGE: root points at nothing -> clouddb.us-east-1.api.acme becomes unresolvable.
    cleanup = deployers["deployer-a"].cleanup_once(keep_last_n=2)
    assert cleanup == {"ok": True, "deleted_versions": [1]}
    assert wormhole53.get(DNS_CLOUDDB_ROOT_NAME, "ALIAS").value == "plan-001.cdb.acme"
    assert wormhole53.get("plan-001.cdb.acme", "ALIAS") is None
    assert wormhole53.resolve(DNS_CLOUDDB_ROOT_NAME) == []

    # Rollback still points to a newer, valid tree.
    assert wormhole53.get(DNS_CLOUDDB_ROLLBACK_NAME, "ALIAS").value == "plan-004.cdb.acme"
    assert wormhole53.resolve("plan-004.cdb.acme") == ["192.0.4.1"]

    # NO FORWARD PROGRESS: Each deployer has a plan it would normally be able to
    # install. These local counters show where each deployer is paused:
    # - deployer-a can retry/reapply plan 004,
    # - deployer-b can install the newest generated plan, plan 005,
    # - deployer-c can continue catching up with plan 002.
    # In a healthy eventually-consistent system, at least one of these actions
    # would repair root resolution by moving the stable root to an existing tree.
    # Instead, all of them get stuck while computing rollback metadata from the
    # missing current root target.
    assert deployers["deployer-a"].next_plan_version == 4  # next would be plan 004
    assert deployers["deployer-b"].next_plan_version == 5  # next would be plan 005
    assert deployers["deployer-c"].next_plan_version == 2  # next would be plan 002

    for name in DEPLOYERS:
        deployers[name].sync_dns_state()
        stuck = deployers[name].deploy_once()
        assert stuck == {"ok": False, "message": "current root target is missing: plan-001.cdb.acme"}

    # The deployers did not advance their local progress counters. They will
    # retry the same plans again on the next loop, hit the same missing-root
    # rollback computation, and stay stuck.
    assert deployers["deployer-a"].next_plan_version == 4
    assert deployers["deployer-b"].next_plan_version == 5
    assert deployers["deployer-c"].next_plan_version == 2

    # The failed deploy attempts did not repair anything: root still names the
    # deleted plan-001 tree, CloudDB still resolves to zero IPs, and the newer
    # plan-005 tree was never written.
    assert wormhole53.get(DNS_CLOUDDB_ROOT_NAME, "ALIAS").value == "plan-001.cdb.acme"
    assert wormhole53.resolve(DNS_CLOUDDB_ROOT_NAME) == []
    assert wormhole53.get("plan-005.cdb.acme", "ALIAS") is None
