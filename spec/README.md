# DNS Balancer Spec

This folder is isolated from the rest of the workspace and uses its own `pyproject.toml`.

The main spec is [dns_balancer.py](dns_balancer.py). It models a DNS balancer with:

- `init`: initial DNS zone setup
- `step`: one randomized system transition
- invariants such as `no_inconsistent_root` and `no_inconsistent_rollback`
- examples such as `epoch5` and `plans3`
- instances such as `n3_20_3` and `n3_30_20`

## Installation

Install [uv](https://docs.astral.sh/uv/), if you don't have it. Then, from this
folder, install the dependencies (including Wunderspec) from the lockfile:

```sh
uv sync
uv tool install wunderspec
```

That's it. The commands below use this environment automatically.

## 1) Run the spec directly

From this folder:

```sh
wunderspec lint dns_balancer.py
```

This is useful as a quick import/syntax check.

## 2) Run randomized searches

Find an example trace where a deployer reaches epoch 5:

```sh
wunderspec run dns_balancer.py \
  --property=epoch5 --instance=n3_20_3 \
  --max-steps=20 --max-samples=100000
```

Check an invariant with the Python runner:

```sh
wunderspec run dns_balancer.py \
  --property=no_inconsistent_root \
  --instance=n3_20_3 --max-steps=20 \
  --max-samples=100000
```

When an invariant violation or example is found, `wunderspec run` prints a
command to replay the schedule.

## 3) Replay the schedule and produce ITF

Replay a saved schedule with the Python runner and write an ITF trace:

```sh
wunderspec replay dns_balancer.py --instance n3_20_3 --property epoch5 \
  --max-steps 20 --seed 6333471430350457850 --out-itf=t.itf.json
```

The generated `t.itf.json` is the input to the visualizer. It includes
`ghost_action`, which lets the viewer show the semantic action that produced
each state.

## 4) Visualize an ITF trace

Generate the self-contained HTML trace viewer:

```sh
uv run python visualize_dns_trace.py \
  t.itf.json --output=t.itf.trace.html
```

Open the generated file in a browser:

```sh
xdg-open t.itf.trace.html
```

On macOS, use:

```sh
open t.itf.trace.html
```

The viewer animates each ITF state as a DNS tree from the root and rollback CNAMEs. It also shows:

- the action summary from `ghost_action`
- root and rollback targets
- reachable plans and balancers
- added, removed, and changed DNS records per step

If the DNS names differ, override the entry names:

```sh
uv run python visualize_dns_trace.py \
  t.itf.json \
  --root-name=db.us-east-1.example.com \
  --rollback-name=rollback.db.example.com \
  --output=t.itf.trace.html
```
