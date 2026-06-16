from typing import Annotated

from wunderspec import *

from dns import *
from defs import *

# We have only one zone in this example, to keep things simple
ZONE = Val("db.us-east-1.example.com")
# The entry name of the rollback record within a zone
ROLLBACK_ADDR = Val("rollback.db.example.com")
# The entry name for the lock record
LOCK_NAME = Val("lock.example.com")


@record
class DnsUpdate(Expr):
    """A DNS update plan"""
    # the plan identifier, e.g., "plan1.db.example.com"
    plan_id: Field[str]
    # the set of aliases to create, e.g.,
    # plan1.db.example.com A 192.0.2.1
    # plan1.db.example.com A 192.0.2.2
    creates: Field[set[DnsRecord]]


@record
class DeployerView(Expr):
    """A snapshot of the system state as observed by a deployer."""
    # the latest lock record observed by the deployer
    lock: Field[DnsRecord]
    # the latest root CNAME record observed by the deployer
    root: Field[str]
    # the latest rollback CNAME record observed by the deployer
    rollback: Field[str]


@state
class DnsBalancerState(MachineStateBase):
    # the set of deployers in the system
    DEPLOYERS: Param[set[str]]
    # the set of possible plan identifiers
    PLAN_IDS: Param[set[str]]
    # the set of possible IP addresses to use in A records
    IPS: Param[set[str]]
    # balancer names: mapping from (plan_id, ip_addr) to balancer name
    BALANCER_NAMES: Param[dict[tuple[str, str], str]]
    # the set of possible weights to use in A records
    WEIGHTS: Param[set[int]]
    # The maximum age for plan records in the planner's update list,
    # before they are garbage collected.
    MAX_PLAN_AGE: Param[int]
    # DNS records for a single zone. This is the storage.
    zone_records: StateVar[set[DnsRecord]]
    # Updates that are published by the planner.
    # This list keeps growing and the deployers read plans from it.
    planner_updates: StateVar[list[DnsUpdate]]
    # The index of the next plan to be executed by a deployer.
    deployer_next_plan: StateVar[dict[str, int]]
    # The latest view of the system state for each deployer.
    # This is the currently observed state of the world for each deployer.
    deployer_view: StateVar[dict[str, DeployerView]]
    # Auxiliary trace metadata: the semantic action that produced this state.
    ghost_action: StateVar[GhostAction]


@action(init=True)
def init(c: Context[DnsBalancerState]):
    s = c.state
    # initially, we have:
    #  1. One TXT record for the lock, with epoch 0.
    #  2. ZONE points to plan-init.
    #  3. plan-init points to lb-1-init.db.example.com, but has no A record.
    #     The init plan is a structural placeholder, not a resolvable deployment.
    #  4. ROLLBACK_ADDR points to plan-init.
    lock_record = DnsRecord(name=LOCK_NAME, kind=TXT, value=Tuple("genesis", 0))
    init_name = Val("plan-init.db.example.com")
    zone_to_plan = mk_cname(name=ZONE, canonical_name=init_name, weight=Val(1))
    lb_name = Val("lb-1-init.db.example.com")
    plan_to_lb = mk_cname(name=init_name, canonical_name=lb_name, weight=Val(100))
    rollback_to_plan = mk_cname(name=ROLLBACK_ADDR, canonical_name=init_name, weight=Val(1))
    s.zone_records = Set(lock_record, zone_to_plan, plan_to_lb, rollback_to_plan)
    # the deployers are set to observe the initial lock value
    s.deployer_view = Map(DeployerView(lock=lock_record, root=init_name, rollback=init_name) for _ in s.DEPLOYERS)
    s.deployer_next_plan = Map(0 for _ in s.DEPLOYERS)
    # no plans yet
    s.planner_updates = List(DnsUpdate)
    s.ghost_action = GhostAction.Init()


@action(inline=False)
def planner_generate(c: Context[DnsBalancerState]):
    """Planner adds a new plan to the system."""
    s = c.state
    with c.one_of(s.PLAN_IDS) as plan_id:
        c.assume(Forall(p.plan_id != plan_id for p in s.planner_updates))
        with c.one_of(AllSubsets(s.IPS)) as ips:
            c.assume(ips != Set(str))
            with c.one_of(AllMaps(ips, s.WEIGHTS)) as weights:
                # create weighted CNAMEs for plan_id,
                # pointing to several A records for the balancers
                a_records = Set(mk_a(name=plan_id, ip_addr=ip) for ip in ips)
                cnames = Set(mk_cname(name=plan_id,
                                     canonical_name=s.BALANCER_NAMES[Tuple(plan_id, ip)],
                                     weight=weights[ip]) for ip in ips)
                new_plan = DnsUpdate(plan_id=plan_id, creates=cnames | a_records)
                s.planner_updates += List(new_plan)
                s.ghost_action = GhostAction.GeneratePlan(
                    GeneratePlanAction(plan_id=plan_id, ips=ips, weights=weights)
                )


@action(inline=False)
def deployer_query(c: Context[DnsBalancerState], deployer: Annotated[Expr, str]):
    """Deployer updates its view of the latest lock and root CNAME."""
    s = c.state
    roots = (s.zone_records
        .filter(lambda r: (r.kind == CNAME) & (r.name == ZONE))
        .map(lambda r: r.value[0]))
    rollbacks = (s.zone_records
        .filter(lambda r: (r.kind == CNAME) & (r.name == ROLLBACK_ADDR))
        .map(lambda r: r.value[0]))
    locks = s.zone_records.filter(lambda r: r.name == LOCK_NAME)
    with (c.one_of(locks) as rec,
          c.one_of(roots) as root, c.one_of(rollbacks) as rollback):
        s.deployer_view[deployer] = DeployerView(lock=rec, root=root, rollback=rollback)
        s.ghost_action = GhostAction.Sync(
            SyncAction(deployer=deployer, lock=rec, root=root, rollback=rollback)
        )


@action(inline=False)
def deployer_backoff(c: Context[DnsBalancerState], deployer: Annotated[Expr, str]):
    s = c.state
    deployer_view = s.deployer_view[deployer]
    c.assume(~s.zone_records.contains(deployer_view.lock))
    # back off
    s.ghost_action = GhostAction.Backoff(
        BackoffAction(deployer=deployer, lock=deployer_view.lock)
    )


@action(inline=False)
def deployer_apply(c: Context[DnsBalancerState], deployer: Annotated[Expr, str]):
    s = c.state
    deployer_view = s.deployer_view[deployer]
    updated_records = s.zone_records
    # Next plan is ready
    c.assume(s.planner_updates.keys.contains(s.deployer_next_plan[deployer]))
    plan = s.planner_updates[s.deployer_next_plan[deployer]]
    # Note that this is an atomic all-or-nothing update to the zone records.
    # DELETE the old lock record for this deployer, if it exists
    c.assume(s.zone_records.contains(deployer_view.lock))
    updated_records -= Set(deployer_view.lock)
    # CREATE the new lock record with incremented version
    new_version = deployer_view.lock.value[1] + 1
    new_record = mk_txt(name=LOCK_NAME, hostname=deployer, epoch=new_version)
    updated_records |= Set(new_record)
    # CONSISTENCY RULE: the root CNAME must always point to an existing plan.
    # This is a safety check to ensure that we can roll back.
    latest_root = deployer_view.root
    c.assume(Exists((r.value[0] == latest_root) & (r.kind == CNAME) for r in s.zone_records))
    # Apply the plan's updates to the zone records.
    updated_records |= plan.creates
    # DELETE the old CNAME record for the zone and CREATE a new one pointing to the new plan
    cname_to_delete = SetIf((r.kind == CNAME) & (r.name == ZONE) for r in updated_records)
    c.assume(~cname_to_delete.is_empty) # sanity check: there is a CNAME record for the zone
    updated_records -= cname_to_delete
    cname_to_create = Set(mk_cname(name=ZONE, canonical_name=plan.plan_id, weight=Val(100)))
    updated_records |= cname_to_create
    # UPSERT the rollback record to point to latest_root
    rollbacks_to_delete = SetIf((r.kind == CNAME) & (r.name == ROLLBACK_ADDR) for r in updated_records)
    updated_records -= rollbacks_to_delete
    rollback_record = mk_cname(name=ROLLBACK_ADDR, canonical_name=latest_root, weight=Val(1))
    updated_records |= Set(rollback_record)
    s.ghost_action = GhostAction.Deploy(
        DeployAction(
            deployer=deployer,
            plan_id=plan.plan_id,
            previous_root=latest_root,
            new_root=plan.plan_id,
            rollback=latest_root,
            new_epoch=new_version,
        )
    )
    s.zone_records = updated_records
    # update the zone records and the deployer's state
    s.deployer_view[deployer] = DeployerView(lock=new_record, root=plan.plan_id, rollback=latest_root)
    s.deployer_next_plan[deployer] += 1


@action(inline=False)
def deployer_gc(c: Context[DnsBalancerState], deployer: Annotated[Expr, str]):
    """Deployer cleans up the old plans to avoid the number of DNS records growing too large."""
    s = c.state
    next_plan = s.deployer_next_plan[deployer]
    old_indices = s.planner_updates.keys.filter(lambda i: next_plan > i + s.MAX_PLAN_AGE)
    old_plan_entries = Set(s.planner_updates[i].creates for i in old_indices).flattened
    # this check is not strictly necessary, but we want to avoid unrealistic events
    c.assume(~(old_plan_entries & s.zone_records).is_empty)
    # Here we simply delete all old records. The implementation may do it in a loop,
    # to avoid failing batch deletes.
    s.zone_records -= old_plan_entries
    s.ghost_action = GhostAction.Cleanup(
        CleanupAction(deployer=deployer, next_plan=next_plan, old_indices=old_indices)
    )


@action
def step(c: Context[DnsBalancerState]):
    """A single step of the system"""
    alts = iter(c.alternatives("add_plan", "query", "backoff", "apply", "gc"))
    with next(alts):
        planner_generate(c)
    with next(alts), c.one_of(c.state.DEPLOYERS, "d") as deployer:
        deployer_query(c, deployer)
    with next(alts), c.one_of(c.state.DEPLOYERS, "d") as deployer:
        deployer_backoff(c, deployer)
    with next(alts), c.one_of(c.state.DEPLOYERS, "d") as deployer:
        deployer_apply(c, deployer)
    with next(alts), c.one_of(c.state.DEPLOYERS, "d") as deployer:
        deployer_gc(c, deployer)


@invariant
def no_inconsistent_root(s: DnsBalancerState):
    """Root must always point to an existing plan."""
    cnames = SetIf(r.kind == CNAME for r in s.zone_records)
    # the plans the zone CNAME points to
    plans = Set(r.value[0] for r in SetIf(r2.name == ZONE for r2 in cnames))
    # Consistency rule: the root CNAME must always point to an existing plan.
    # Moreover, there must be one entry.
    return ~((plans & Set(r.name for r in cnames)).is_empty) & (plans.size == 1)


@invariant
def no_inconsistent_rollback(s: DnsBalancerState):
    """Rollback must always point to an existing plan."""
    cnames = SetIf(r.kind == CNAME for r in s.zone_records)
    rollbacks = Set(r.value[0] for r in SetIf(r2.name == ROLLBACK_ADDR for r2 in cnames))
    # Consistency rule: the rollback CNAME must always point to an existing plan.
    # Moreover, there must be exactly one rollback entry.
    return ~((rollbacks & Set(r.name for r in cnames)).is_empty) & (rollbacks.size == 1)


@example
def epoch5(s: DnsBalancerState):
    """At least one deployer has reached epoch 5."""
    return s.DEPLOYERS.exists(lambda deployer: s.deployer_view[deployer].lock.value[1] == 5)


@example
def plans3(s: DnsBalancerState):
    """At least three plans have been created."""
    return s.planner_updates.size >= 3


@instance
def n3_5_3() -> DnsBalancerState:
    """A small instance with 3 deployers, 5 plan identifiers, and 3 epochs before GC."""
    n_ips = 3
    n_ids = 5
    return DnsBalancerState(
        # a fixed set of deployers
        DEPLOYERS=Set("deployer-a", "deployer-b", "deployer-c"),
        # generate a set of plan identifiers to choose from
        PLAN_IDS=Set(*[f"plan{i}.db.example.com" for i in range(0, n_ids)]),
        # generate a set of possible IP addresses to use in A records
        IPS=Set(*[f"192.0.2.{i}" for i in range(1, n_ips + 1)]),
        # generate balancer names for each (plan_id, ip_addr) pair
        BALANCER_NAMES=Map(*[
            (Tuple(Val(f"plan{plan_id}.db.example.com"), Val(f"192.0.2.{i}")),
             Val(f"lb-{i}-{plan_id}.db.example.com"))
            for plan_id in range(0, n_ids)
            for i in range(1, n_ips + 1)
        ]),
        # generate a set of possible weights to use in A records
        WEIGHTS=Set(100, ..., 120),
        # short age
        MAX_PLAN_AGE=3
    )


@instance
def n3_20_3() -> DnsBalancerState:
    """A small instance with 3 deployers, 20 plan identifiers, and 3 epochs before GC."""
    n_ips = 3
    n_ids = 20
    return DnsBalancerState(
        # a fixed set of deployers
        DEPLOYERS=Set("deployer-a", "deployer-b", "deployer-c"),
        # generate a set of plan identifiers to choose from
        PLAN_IDS=Set(*[f"plan{i}.db.example.com" for i in range(0, n_ids)]),
        # generate a set of possible IP addresses to use in A records
        IPS=Set(*[f"192.0.2.{i}" for i in range(1, n_ips + 1)]),
        # generate balancer names for each (plan_id, ip_addr) pair
        BALANCER_NAMES=Map(*[
            (Tuple(Val(f"plan{plan_id}.db.example.com"), Val(f"192.0.2.{i}")),
             Val(f"lb-{i}-{plan_id}.db.example.com"))
            for plan_id in range(0, n_ids)
            for i in range(1, n_ips + 1)
        ]),
        # generate a set of possible weights to use in A records
        WEIGHTS=Set(100, ..., 120),
        # short age
        MAX_PLAN_AGE=3
    )


@instance
def n3_30_20() -> DnsBalancerState:
    """A larger instance with 3 deployers, 30 plan identifiers, and 20 epochs before GC."""
    n_ips = 3
    n_ids = 30
    return DnsBalancerState(
        # a fixed set of deployers
        DEPLOYERS=Set("deployer-a", "deployer-b", "deployer-c"),
        # generate a set of plan identifiers to choose from
        PLAN_IDS=Set(*[f"plan{i}.db.example.com" for i in range(0, n_ids)]),
        # generate a set of possible IP addresses to use in A records
        IPS=Set(*[f"192.0.2.{i}" for i in range(1, n_ips + 1)]),
        # generate balancer names for each (plan_id, ip_addr) pair
        BALANCER_NAMES=Map(*[
            (Tuple(Val(f"plan{plan_id}.db.example.com"), Val(f"192.0.2.{i}")),
             Val(f"lb-{i}-{plan_id}.db.example.com"))
            for plan_id in range(0, n_ids)
            for i in range(1, n_ips + 1)
        ]),
        # generate a set of possible weights to use in A records
        WEIGHTS=Set(100, ..., 120),
        # relative long age
        MAX_PLAN_AGE=20
    )
