# Model-based testing the DNS control plane

We have a spec (`spec/dns_balancer.py`) and an implementation
(`dns-control-plane-lab`). Model-based testing (MBT) connects them: we take a
trace produced by the spec and replay it, action by action, against the real
implementation, checking that the implementation behaves as the model predicts.

## 1. The system under test

Open `dns-control-plane-lab/README.md`. The control plane has three parts:

- **Planner** — writes immutable plans.
- **Deployers** (`deployer-a`, `deployer-b`, `deployer-c`) — independently sync,
  deploy, and clean up.
- **Wormhole53** — the DNS store that resolves `clouddb.us-east-1.api.acme`.

The property we care about: after every action, the CloudDB root name must
resolve to at least one load-balancer IP (the only exception is the `init`
placeholder plan, which has no `A` record).

## 2. The MBT harness

Open `dns-control-plane-lab/dns_control_plane/mbt_harness.py`. It exposes the
control plane as a small FastAPI router so a trace can drive it one action at a
time:

- `POST /mbt/reset`
- `POST /mbt/planner/generate`
- `POST /mbt/deployers/{name}/sync`
- `POST /mbt/deployers/{name}/deploy`
- `POST /mbt/deployers/{name}/cleanup`

## 3. From ITF action to HTTP call

Open `mbt/test_dns_control_plane_itf_replay.py`. Each ITF state carries a
`ghost_action`; `replay_state` maps it to the matching endpoint:

| ITF action     | Harness call                          |
| -------------- | ------------------------------------- |
| `Init`         | `/mbt/reset` + seed init plan         |
| `GeneratePlan` | `/mbt/planner/generate`               |
| `Sync`         | `/mbt/deployers/{d}/sync`             |
| `Deploy`       | `/mbt/deployers/{d}/deploy`           |
| `Backoff`      | `/mbt/deployers/{d}/deploy` (expects failure) |
| `Cleanup`      | `/mbt/deployers/{d}/cleanup`          |

After each action, `_assert_root_resolvable_or_init` checks the property
directly against Wormhole53.

## 4. Replaying a trace

Replaying a trace tells us whether the implementation matches the model on that
exact action sequence. From `spec`, produce an ITF trace and replay it:

```sh
uv run python ../mbt/test_dns_control_plane_itf_replay.py ../spec/t.itf.json
```

Every step prints `[OK]` and the run exits `0`: the implementation agreed with
the model along the whole trace — a confirmed positive example.

## 5. Replaying the checked-in trace

```sh
make mbt
```

This replays `spec/n3_30_20_no_inconsistent_root_violation.itf.json`. Watch each
step print its action and `[OK]`/`[FAIL]`, and read the final report: it shows
where (if anywhere) the implementation diverged from the model — the step,
action, root/rollback records, and the resulting hosted-zone records.

## 6. Where this fits

The spec explores behaviors abstractly; MBT checks that the real code follows
the same behavior on concrete traces. A trace can confirm the implementation is
correct along that path, or pinpoint exactly where and how it diverges — on the
precise action sequence the model produced.
