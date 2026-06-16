# DNS Control Plane Lab Workshop System

This document describes the lab implementation of a DNS control-plane system inspired by the DynamoDB/Route53 control-plane incident described in the AWS re:Invent 2025 talk "DynamoDB: Resilience & lessons from the Oct 2025 service disruption (DAT453)". In the lab system, the fictional company is ACME, the database service is CloudDB, and the DNS control plane is Wormhole53.

The goal is to build a deliberately small, understandable system that can be tested with model-based testing. The implementation should contain a latent race-condition bug similar in shape to the one described in the talk. Do **not** implement the fix yet.

## Goals

- Build a standalone service that can be run independently.
- Use Python.
- Use FastAPI for the HTTP API.
- Use Uvicorn to serve the FastAPI application.
- Use pytest for tests.
- Later, model-based tests will interact with the service as an external black box over HTTP.
- The service should run autonomous background components, not only expose direct imperative endpoints.
- The test harness should influence timing/environment but should not directly tell a deployer to install a specific plan.
- Keep the Wormhole53 model minimal.
- IPv4 only.
- Model one region only: `us-east-1`.
- One DNS hosted zone is enough.
- Store plans and the persisted Wormhole53 DNS zone as JSON on disk in a single `s3-persistence/` directory that mimics an S3 bucket.

## Non-goals

- Do not build a full DNS server.
- Do not model recursive resolvers, TTLs, propagation delay, negative caching, health checks, or real weighted random selection.
- Do not implement IPv6.
- Do not implement multiple hosted zones.
- Do not fix the race condition yet.
- Do not expose a `/zone` endpoint in the core API.

## High-level architecture

The process should run one FastAPI service plus autonomous background loops:

```text
Process
  ├── FastAPI HTTP API
  ├── Wormhole53-like transactional control-plane store
  ├── autonomous planner loop / plan store
  ├── deployer-a loop
  ├── deployer-b loop
  └── deployer-c loop
```

There is no separate cleaner service in the first design. Record cleanup is behavior performed by the deployer loops after successful installs, matching the shape described in the talk. A single explicit deploy action installs one plan; cleanup remains a separate deployer action that the loop or MBT cleanup endpoint can invoke.

The architecture should mimic the real system shape:

```text
planner autonomously writes immutable plans
        ↓
deployers autonomously poll plans and apply them
        ↓
deployers install plan trees, flip root aliases, then clean old plan-tree records
        ↓
Wormhole53-like transactional control plane stores DNS records
        ↓
resolver follows stable root alias to plan tree to A records
```

## DNS names

Use these default names:

```text
DNS_CLOUDDB_ROOT_NAME = clouddb.us-east-1.api.acme
DNS_CLOUDDB_ROLLBACK_NAME = _rollback.clouddb.us-east-1.api.acme
DNS_CLOUDDB_LOCK_NAME = _lock.clouddb.us-east-1.api.acme
DNS_PLAN_NAME_FORMAT = plan-{version:03d}.cdb.acme
LOADBALANCER_NAME_FORMAT = lb-{plan_version:03d}-{lb_id}.cdb.acme
```

Example alias trees:

```text
clouddb.us-east-1.api.acme ----> plan-101.cdb.acme

plan-101.cdb.acme -------------> lb-101-1.cdb.acme  A 192.0.101.1  weight 100
                         \----> lb-101-2.cdb.acme  A 192.0.101.2  weight 105


# A later plan can build a second complete tree before the stable root alias flips.

clouddb.us-east-1.api.acme ----> plan-102.cdb.acme

plan-102.cdb.acme -------------> lb-102-1.cdb.acme  A 192.0.102.1  weight 110
                         \----> lb-102-2.cdb.acme  A 192.0.102.2  weight 105
```

For deterministic tests, the resolver may return all leaf IPs reachable from the root instead of randomly selecting by weight.

## Record model

Keep records minimal.

Supported record types:

- `A`
- `ALIAS`
- `TXT`

Suggested JSON shapes:

```json
{
  "name": "lb-101-1.cdb.acme",
  "type": "A",
  "value": "192.0.101.1"
}
```

```json
{
  "name": "clouddb.us-east-1.api.acme",
  "type": "ALIAS",
  "value": "plan-101.cdb.acme"
}
```

Weighted alias fanout can be represented as an `ALIAS` whose value is a list of targets:

```json
{
  "name": "plan-101.cdb.acme",
  "type": "ALIAS",
  "value": [
    {"name": "lb-101-1.cdb.acme", "weight": 100},
    {"name": "lb-101-2.cdb.acme", "weight": 105}
  ]
}
```

Lock record:

```json
{
  "name": "_lock.clouddb.us-east-1.api.acme",
  "type": "TXT",
  "value": "deployer-a 1760000000"
}
```

Record identity should be based on `(name, type)`. `DnsRecord` is represented as one model, but conceptually behaves like a small discriminated union:

- `type == "A"`: `value` is an IPv4 address string.
- `type == "TXT"`: `value` is a text string.
- `type == "ALIAS"`: `value` is either one target name string or a list of weighted alias targets.

For `DELETE`, the existing record must exactly match the supplied record, including value.

## Minimal Wormhole53-like transactional batch semantics

Implement a Wormhole53-like control plane with:

```python
change_record_sets(changes: list[DnsBatchChange]) -> None
```

Each `DnsBatchChange` has:

- `type`: `CREATE`, `DELETE`, or `UPSERT`
- `record`: the `DnsRecord` being created, deleted, or upserted

Supported change types:

- `CREATE`
  - fails if `(name, type)` already exists.
- `DELETE`
  - fails if `(name, type)` does not exist or the existing record does not exactly equal the supplied record.
- `UPSERT`
  - creates or replaces the record.

Batch behavior:

- The batch is transactional.
- Validate/apply all changes against a copy of current state.
- If any operation fails, discard the copy and leave real state unchanged.
- If all operations succeed, commit the copied state.
- If persisting to disk, write to a temp file and atomically replace the old JSON file.

This enables a compare-and-swap-like lock protocol:

```text
DELETE _lock.clouddb.us-east-1.api.acme TXT "deployer-a <old_epoch>"
CREATE _lock.clouddb.us-east-1.api.acme TXT "deployer-a <new_epoch>"
UPSERT ... actual DNS changes ...
```

If another deployer changed the lock, the `DELETE` no longer matches and the entire batch fails.

## Plans

The planner creates immutable versioned plan JSON files.

Example `s3-persistence/plans/plan-101.json`:

```json
{
  "version": 101,
  "root": "clouddb.us-east-1.api.acme",
  "plan_name": "plan-101.cdb.acme",
  "records": [
    {
      "name": "plan-101.cdb.acme",
      "type": "ALIAS",
      "value": [
        {"name": "lb-101-1.cdb.acme", "weight": 100},
        {"name": "lb-101-2.cdb.acme", "weight": 105}
      ]
    },
    {
      "name": "lb-101-1.cdb.acme",
      "type": "A",
      "value": "192.0.101.1"
    },
    {
      "name": "lb-101-2.cdb.acme",
      "type": "A",
      "value": "192.0.101.2"
    }
  ]
}
```

Each plan describes the complete desired DNS tree for that plan version, excluding the stable root alias flip.

The service should run an autonomous planner loop that periodically generates new plans. In a real system, planner work would be triggered externally by changing service load/capacity signals. In this lab/workshop, the autonomous planner chooses random weights and keeps increasing the load-balancer count to mimic growing load, so the DNS tree visibly evolves. Leaf IP addresses should include the plan version, e.g. `plan-004` load balancer 2 uses `192.0.4.2`. This keeps the lab close to the real control-plane shape: plans continue appearing while deployers independently poll and apply them.

For deterministic workshop scenarios, the harness can still generate one plan immediately via an HTTP endpoint. Implementations may provide one global environment toggle so model-based tests can disable all background loops when they need tight control.

Suggested environment variables:

```text
DNS_LAB_BASE_DIR=/path/to/lab/state    # override the base directory for s3-persistence/
DNS_LAB_DISABLE_BACKGROUND=1          # disable planner and deployer background loops
DNS_LAB_PLANNER_INTERVAL_SECONDS=5.0
DNS_LAB_DEPLOYER_INTERVAL_SECONDS=0.25
DNS_LAB_DEPLOYER_JITTER_SECONDS=0.25
```

## Rollback record

The real pattern keeps old plan trees around so rollback can be a single stable-root alias flip.

The lab system should include a rollback pointer:

```text
DNS_CLOUDDB_ROLLBACK_NAME = _rollback.clouddb.us-east-1.api.acme
```

Whenever a deployer modifies the stable root record, it should also update `_rollback.clouddb.us-east-1.api.acme` in the same transactional batch. The rollback record should point to the root's previous target: the plan that was active immediately before this root modification.

Example: if the current root points to `plan-101.cdb.acme` and a deployer installs `plan-102.cdb.acme`, the batch should include:

```text
UPSERT clouddb.us-east-1.api.acme ALIAS plan-102.cdb.acme
UPSERT _rollback.clouddb.us-east-1.api.acme           ALIAS plan-101.cdb.acme
```

Then an operator rollback would conceptually do:

```text
UPSERT clouddb.us-east-1.api.acme ALIAS <current _rollback.clouddb.us-east-1.api.acme target>
```

If there is no previous root target, such as during the first successful install, omit the rollback update. The rollback record appears after the second distinct root update, when there is a real previous root target.

For the first lab version, rollback does not need a public API unless useful for the workshop. The important idea is that rollback relies on old plan trees still existing. If cleanup deletes the tree referenced by the root or rollback pointer, rollback and/or normal resolution can fail.

The inconsistent state described in the talk is slightly subtler than just "rollback points to a deleted tree". The root can point to a deleted old tree, while the rollback record points to a newer valid tree:

```text
clouddb.us-east-1.api.acme ----> (deleted)  # was: plan-110.cdb.acme tree

_rollback.clouddb.us-east-1.api.acme -------------> plan-145.cdb.acme ---> lb-145-1.cdb.acme  A ...
                                             \-----> lb-145-2.cdb.acme  A ...
```

In this state, normal customer resolution fails because the stable root points at a deleted plan tree. The rollback pointer itself may still point at a valid plan tree, but the deployer code can still fail if it assumes the current root target exists when computing/updating rollback metadata. In this lab, a deployer treats a missing current root target record as a deployment error before it flips root to the next plan, so normal deployer actions cannot make forward progress. This is the inconsistent state the lab system should be able to represent.

## Deployers

Run three autonomous deployer loops:

```text
deployer-a
deployer-b
deployer-c
```

Each deployer should expose an internal "deploy one plan" operation and a separate "cleanup once" operation. The autonomous loop calls deploy and, after a successful install, cleanup. The action API can trigger either action once for deterministic workshop scenarios.

One deployment step should:

1. Poll the plan store.
2. Notice the next plan version from this deployer's own internal counter.
3. Attempt to acquire/refresh the Wormhole53 TXT lock using a transactional batch.
4. If it fails to acquire the lock because another deployer changed the expected lock value, return without advancing local progress.
5. If it acquires the lock, install the plan tree, flip the stable root alias to that plan, and update `_rollback.clouddb.us-east-1.api.acme` to the previous root target in the same transactional batch.
6. Advance this deployer's local next-plan-version counter.

The background loop should continue calling this operation while the service is running. Add a small per-loop jitter or initial offset so the same deployer does not always win simply because asyncio tasks were created in a fixed order.

Important: deployers should keep local progress state as an internal next-plan-version counter. This allows one deployer to become stale if it is delayed or simply not scheduled while other deployers move forward. Do not replace this with global latest-version tracking.

The deliberately vulnerable behavior:

- A deployer that falls behind may later acquire the lock and install an older/stale plan.
- It should not reject stale plans yet.

The lock can be simplified as long as it preserves the important semantics:

- The lock is a `TXT` record.
- Lock ownership/value contains the deployer hostname and an epoch/counter.
- Updating the lock is part of the same transactional batch as DNS updates.
- A stale expected lock value causes the batch to fail.

## Record cleanup

Record cleanup should be implemented as part of the deployer behavior, not as a separate autonomous cleaner service.

After a deployer loop successfully installs/applies a plan, it may perform cleanup of old plan-tree records by calling the deployer's separate cleanup-once operation. This matches the talk's description where a deployer can finish installing a plan and then clean up sufficiently old records.

Cleanup behavior:

- Uses the deployer's local next-plan-version counter to decide which versions are old enough to delete.
- Inspects current Wormhole53 hosted-zone records and deletes records belonging to sufficiently old plans.
- Keep policy can be simple, e.g. `keep_last_n` applied to this deployer's local progress.
- Intentionally use age/version-based deletion, not reachability-based deletion.
- Cleanup deletes should use the same Wormhole53-like transactional batch API.
- Cleanup may use the same lock protocol as other deployer updates, or may be part of the deployer's locked work cycle. Keep this simple, but preserve the important property that individual Wormhole53 batches are atomic.

The deliberately vulnerable behavior:

- Cleanup may delete records for a plan that can later become active again due to a stale deployer.
- Do not protect the active root alias target yet.
- Do not implement reachability-safe cleanup yet.

This is the core race shape from the talk:

```text
deployer-a installs a newer plan
deployer-b installs another newer plan
deployer-c, delayed by scheduling/interleaving, later installs an old stale plan and updates rollback to the previously-active newer plan
a cleanup step then deletes records for sufficiently old plans, including the stale plan tree now referenced by the root
root alias points at a deleted plan tree, while rollback may point at a newer valid plan tree
```

## Resolver

Implement resolution as a read operation on the Wormhole53-like store, used by the API:

```python
Wormhole53Store.resolve(name: str) -> list[str]
```

For this lab system:

- Follow `ALIAS` records recursively.
- If an alias target is missing, return an empty list for that branch.
- If an `A` record is reached, return its IP.
- If a weighted alias list is reached, resolve all listed targets and return all resulting IPs.
- Avoid infinite recursion with a visited set.

The key observable invariant for testing:

```python
wormhole53.resolve("clouddb.us-east-1.api.acme") != []
```

The bug should allow this invariant to be violated.

## HTTP API

### Public-facing endpoints

```text
GET /
GET /health
GET /wormhole53/resolve/{name}
```

No core `/zone` endpoint is required.

`GET /` should return a small browser frontend showing the current Wormhole53 DNS layout, a resolver tree from the stable root, inline load-balancer weights, root/rollback/lock pointers, and root resolution status.

`GET /health` should report the same root-resolution health shown by the browser frontend. Example healthy response:

```json
{
  "ok": true,
  "name": "clouddb.us-east-1.api.acme",
  "ips": ["192.0.1.1"]
}
```

`GET /wormhole53/resolve/{name}` example healthy response:

```json
{
  "name": "clouddb.us-east-1.api.acme",
  "ips": ["192.0.1.1"]
}
```

Broken response:

```json
{
  "name": "clouddb.us-east-1.api.acme",
  "ips": []
}
```

### MBT/workshop action endpoints

The test harness controls the system by calling action endpoints. These endpoints should trigger the requested action immediately. Avoid enable/disable style controls and avoid long-lived harness modes.

The service's real planner and deployer loops still run autonomously in the background. The action endpoints are external stimuli: generate one plan immediately, run one deployer once, run one cleanup pass, reset the world, etc. Tests can call one action at a time and then poll public health/resolution endpoints until the desired state appears.

The action endpoints should not directly command a deployer to apply a specific plan.

```text
POST /mbt/reset
POST /mbt/planner/generate
POST /mbt/deployers/{name}/sync
POST /mbt/deployers/{name}/deploy
POST /mbt/deployers/{name}/cleanup
```

No explicit tick endpoint is needed.

#### `POST /mbt/reset`

Immediately reset all state:

- DNS records
- plans
- deployer state
- cleanup state
- on-disk JSON state

After reset, the autonomous planner and deployer loops should continue running unless background loops are globally disabled. If background loops are enabled, new plans may appear after reset without a harness action; if they are disabled for deterministic testing, deployers simply have no plans to process until the harness generates one.

#### `POST /mbt/planner/generate`

Immediately generate one new plan.

Optional request body:

```json
[
  {"id": 1, "weight": 100},
  {"id": 2, "weight": 105}
]
```

If omitted, generate a deterministic default plan with one load balancer using unit weight. Versions should monotonically increase.

#### `POST /mbt/deployers/{name}/sync`

Immediately make the named deployer observe the current Wormhole53 lock and root records. This needs to be executed before deploy so the deployer has the DNS state required for the compare-and-swap lock update.

#### `POST /mbt/deployers/{name}/deploy`

Immediately trigger one deployment step for the named deployer.

This should call the same deploy-once operation that the autonomous deployer loop uses for installation. It should not run cleanup and should not specify a plan version. The deployer chooses what to do based on its own local progress and the current plan store.

This endpoint is important for deterministic model-based tests: tests can force a specific deployer to take exactly one normal step without directly telling it which plan to install.

#### `POST /mbt/deployers/{name}/cleanup`

Trigger one cleanup pass immediately for the named deployer.

This should exercise the same cleanup-once code path used by deployers. It should not be a separate long-running cleaner service. Conceptually, this endpoint is a workshop harness action that says, "run this deployer's record-cleaning step now."

Suggested body:

```json
{
  "keep_last_n": 2
}
```

The request body is required. Cleanup uses the same Wormhole53-like transactional update semantics as other DNS modifications.

No cleanup enable/disable/config endpoints are needed.

## Expected bug scenario

The workshop should be able to reproduce a sequence like this through harness actions and polling, not by directly applying plans:

```text
1. `POST /mbt/reset`
2. `POST /mbt/planner/generate` to create the first plan
3. wait until root resolves to IPs, or trigger `POST /mbt/deployers/deployer-a/deploy`
4. Do not schedule deployer-c while it falls behind.
5. `POST /mbt/planner/generate` several more times to create newer plans
6. trigger `POST /mbt/deployers/deployer-a/deploy` and/or `POST /mbt/deployers/deployer-b/deploy` so newer plans are installed
7. trigger `POST /mbt/deployers/deployer-c/deploy`
8. deployer-c continues from stale local progress and installs an old plan, flipping the root back to that old plan and updating `_rollback.clouddb.us-east-1.api.acme` to the previously-active newer plan
9. `POST /mbt/deployers/deployer-a/cleanup` so cleanup deletes sufficiently old plan records, including the old plan now referenced by the root
10. resolving DNS_CLOUDDB_ROOT_NAME returns []
11. later deployer attempts fail while trying to compute rollback metadata from the missing current root target, so the system remains stuck until manual repair
```

The exact versions do not matter. The important shape is:

```text
newer plan active
stale deployer later flips root back to older plan and updates rollback to the newer previous root
deployer-driven cleanup then deletes that older plan tree
root alias points to missing tree
rollback points to newer valid tree
resolver returns zero IPs
```

Key invariant violated:

```text
DNS_CLOUDDB_ROOT_NAME should always resolve to at least one IP after the system has at least one successfully installed plan.
```

## Suggested project layout

```text
dns-control-plane-lab/
  PROMPT.md
  README.md
  pyproject.toml
  dns_control_plane/
    __init__.py
    acme_cloud.py    # public FastAPI app/API and background task lifecycle
    mbt_harness.py   # workshop app that includes public API plus MBT-only API
    models.py        # Pydantic/API models
    wormhole53.py    # transactional Wormhole53-like store and DNS resolution
    planner.py       # plan generation, JSON plan storage, autonomous planner loop
    deployer.py      # autonomous deployer loop, deploy logic, and cleanup behavior

  s3-persistence/
    README.md
    current_dns_zone.json
    plans/
      plan-001.json
      plan-002.json

  tests/
    test_wormhole53.py
    test_service_smoke.py
    test_race_outage_poc.py
```

## Running during the workshop

Run with `make`:

```bash
cd dns-control-plane-lab
make run
```

Run tests when `make` is available:

```bash
make test
```

If `make` is not available, run tests directly with uv. The dev dependency group is synced automatically:

```bash
uv run python -m pytest -q
```

Run the service directly with uv:

```bash
uv run uvicorn dns_control_plane.mbt_harness:app --reload --port 8000
```

Optionally, sync the environment explicitly first:

```bash
uv sync
```

Use API docs:

```text
http://localhost:8000/docs
```

## Dependency suggestions

`pyproject.toml` should include something like:

```toml
[project]
name = "dns-control-plane-lab"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi",
  "uvicorn",
  "pydantic>=2"
]

[dependency-groups]
dev = [
  "pytest",
  "httpx2"
]
```

## Notes for implementation

- Keep code simple and readable for workshop participants.
- Prefer deterministic behavior where practical.
- Use short background loop intervals by default, but make them configurable.
- Use a single process. No need for distributed processes.
- Use locks around shared in-memory state if background tasks can interleave.
- The service should be intentionally vulnerable. Avoid adding safety checks that prevent stale plan installation or reachability-unsafe cleanup.
