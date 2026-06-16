from wunderspec import *

from dns import *


@record
class GeneratePlanAction(Expr):
    plan_id: Field[str]
    ips: Field[set[str]]
    weights: Field[dict[str, int]]


@record
class SyncAction(Expr):
    deployer: Field[str]
    lock: Field[DnsRecord]
    root: Field[str]
    rollback: Field[str]


@record
class DeployAction(Expr):
    deployer: Field[str]
    plan_id: Field[str]
    previous_root: Field[str]
    new_root: Field[str]
    rollback: Field[str]
    new_epoch: Field[int]


@record
class BackoffAction(Expr):
    deployer: Field[str]
    lock: Field[DnsRecord]


@record
class CleanupAction(Expr):
    deployer: Field[str]
    next_plan: Field[int]
    old_indices: Field[set[int]]


@union
class GhostAction:
    Init: Variant[Unit]
    GeneratePlan: Variant[GeneratePlanAction]
    Sync: Variant[SyncAction]
    Deploy: Variant[DeployAction]
    Backoff: Variant[BackoffAction]
    Cleanup: Variant[CleanupAction]
