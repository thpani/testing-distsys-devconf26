# MBT ITF Replay Tests

This directory contains a replay script for WunderSpec ITF traces from
`spec/dns_balancer.py`.

The script replays each ITF `ghost_action` against the DNS control-plane lab's
`/mbt` FastAPI harness and checks that `clouddb.us-east-1.api.acme` remains
resolvable after every non-init action. The init plan is a structural placeholder
and intentionally has no `A` record, so an unresolved root is allowed only while
the root target contains `init`. The script accepts both single-trace ITF JSON
from `wunderspec replay --out-itf` and newline-delimited ITF traces from
`wunderspec run --out-itf` or `wunderspec check --out-itf`.

## Run

Run from `dns-control-plane-lab` so the lab dependencies are available:

```sh
uv run --extra dev python ../mbt/test_dns_control_plane_itf_replay.py ../spec/t.itf.json
```

Pass any number of ITF JSON or NDJSON inputs:

```sh
uv run --extra dev python ../mbt/test_dns_control_plane_itf_replay.py \
  ../spec/t.itf.json \
  ../traces/found.ndjson
```

Use `-` to read ITF JSON or NDJSON from stdin:

```sh
cat ../spec/t.itf.json | uv run --extra dev python ../mbt/test_dns_control_plane_itf_replay.py -
```

The script continues after a trace fails, prints the failure in red, and exits
non-zero after reporting the total number of failed traces.

## Generate ITF

From `spec`, generate ITF with WunderSpec, for example:

```sh
uv run --active --no-project wunderspec replay \
  --from-schedule=schedule_ghost.json \
  --property=no_inconsistent_root \
  --instance=n3_20_3 \
  --out-itf=t.itf.json \
  dns_balancer.py
```

Traces should use deployer names `deployer-a`, `deployer-b`, and `deployer-c`.

## Expected Failures

Counterexample traces are supposed to fail this test. For example, a trace that
reproduces the stale-deployer cleanup outage should fail at the step where root
points at a deleted non-init plan. The failure message includes the ITF step,
action response, root and rollback records, recent replay history, and the final
hosted-zone records.
