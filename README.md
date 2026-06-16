# Find distributed systems bugs before production

Workshop repository for the [DevConf.CZ 2026][] talk **“Find distributed systems
bugs before production… with executable specifications”** by [Igor Konnov][] and
[Thomas Pani][].

**Slides:** [https://wunderspec.com/devconf](https://wunderspec.com/devconf)

The workshop uses a small DNS control-plane system to show how executable
specifications, randomized search, and model-based testing can expose
distributed-systems bugs before they reach production. The core idea is to use
executable models as test-generation machines.

## Workshop scenario

The system under test is **ACME CloudDB**, a fictional cloud database endpoint backed by a
DNS control plane.

The control plane has a planner, multiple independent deployers, and a fake DNS service
called Wormhole53. It is intentionally small, but it captures a class of real distributed
systems problems: bugs caused by timing, ordering, stale state, retries, and cleanup races.

The goal is to **"shift left"**: find the outage-causing behavior before it reaches
producation and causes an expensive outage.

## Repository layout

### `dns-control-plane-lab/`

A runnable Python/FastAPI lab application that simulates the ACME Cloud DNS control plane.  
It includes:

- a fake Wormhole53 DNS service,
- a planner that writes immutable DNS plans,
- three independent deployers that apply and clean up plans,
- persistence simulated on-disk under `s3-persistence/`, and
- an `/mbt` API used by the model-based testing harness.

Useful commands:

```sh
cd dns-control-plane-lab
make run    # serve the workshop app at http://localhost:8000
make test   # run lab tests
make clean  # remove generated local state
```

See [`dns-control-plane-lab/README.md`](dns-control-plane-lab/README.md) for details.

### `spec/`

An executable specification of the DNS balancer/control-plane behavior in [Wunderspec][].

It contains:

- `dns_balancer.py`, the main WunderSpec model,
- invariants such as root and rollback consistency checks,
- randomized search and replay workflows for finding counterexample traces, and
- `visualize_dns_trace.py` for generating an HTML trace viewer.

See [`spec/README.md`](spec/README.md) for setup, randomized search, replay, and visualization commands.

### `mbt/`

Model-based testing glue between traces produced by `spec/` and the runnable lab in
`dns-control-plane-lab/`.

The replay script reads Wunderspec ITF traces, drives the lab through its `/mbt` API, and checks that
`clouddb.us-east-1.api.acme` remains resolvable after each relevant action. Counterexample
traces are expected to fail and produce the outage behavior.

See [`mbt/README.md`](mbt/README.md) for replay examples.

## Top-level commands

The root `Makefile` provides shortcuts for workshop flows:

```sh
make spec-story  # check code blocks in spec-story.md
make mbt         # replay the checked-in ITF trace against the lab
```

## Workshop flow

A typical path through the material is:

1. Run and inspect the lab in `dns-control-plane-lab/`.
2. Discuss what ordinary tests cover, and what distributed-systems bugs they miss.
3. Explore the executable model in `spec/` and search for invariant violations.
4. Export an ITF trace from the model.
5. Replay that trace against the implementation using `mbt/`.

## About

For more information about the speakers, the talk, and the workshop, see:
- [wunderspec.com](https://wunderspec.com/): the executable specification framework used in the workshop
- [konnov.phd][Igor Konnov]: Igor's professional website
- [protocols-made-fun.com][]: Igor's blog on protocol design and testing
- [blltprf.xyz][Thomas Pani]: Thomas's professional website and blog

[Igor Konnov]: https://konnov.phd/
[Thomas Pani]: https://blltprf.xyz/
[DevConf.CZ 2026]: https://www.devconf.info/cz/
[Wunderspec]: https://github.com/wunderspec/wunderspec
[protocols-made-fun.com]: https://protocols-made-fun.com/
