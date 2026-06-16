# DNS balancer specification

## 0. Install Wunderspec

Install [uv](https://docs.astral.sh/uv/), if you don't have it. Then, from this
folder, install the dependencies (including Wunderspec) from the lockfile:

```sh
cd spec
uv sync
uv tool install wunderspec
```

That's it. The commands below use this environment automatically.

## 1. Machine states and instances

Open `dns.py` and show the basic data structures.

Open `dns_balancer.py`. Go over the definitions:

 - `DnsUpdate`,
 - `DeployerView`
 - `DnsBalancerState`

NOTE: our specification is parameterized! To define the parameters, we declare
instances. Go to `n3_5_3` and `n3_20_3` and show them.

Since we are using Python, we can just evaluate these definitions:

```python
from wunderspec import *
from dns_balancer import *
proto = n3_5_3()
# IPython: proto
print(proto.pretty())
```

**NOTE**: these definitions are not just the standard Python data structures.
They are symbolic expressions in our AST.

<details>

<summary>Click to see the output</summary>
<!--pytest-codeblocks:expected-output-->

```text
DnsBalancerState(
  DEPLOYERS=Set(Lit('deployer-a'), Lit('deployer-b'), Lit('deployer-c')),
  PLAN_IDS=Set(
    'plan0.db.example.com',
    'plan1.db.example.com',
    'plan2.db.example.com',
    'plan3.db.example.com',
    'plan4.db.example.com'
  ),
  IPS=Set(Lit('192.0.2.1'), Lit('192.0.2.2'), Lit('192.0.2.3')),
  BALANCER_NAMES=Map(
    Tuple(Tuple(Lit('plan0.db.example.com'), Lit('192.0.2.1')), 'lb-1-0.db.example.com'),
    Tuple(Tuple(Lit('plan0.db.example.com'), Lit('192.0.2.2')), 'lb-2-0.db.example.com'),
    Tuple(Tuple(Lit('plan0.db.example.com'), Lit('192.0.2.3')), 'lb-3-0.db.example.com'),
    Tuple(Tuple(Lit('plan1.db.example.com'), Lit('192.0.2.1')), 'lb-1-1.db.example.com'),
    Tuple(Tuple(Lit('plan1.db.example.com'), Lit('192.0.2.2')), 'lb-2-1.db.example.com'),
    Tuple(Tuple(Lit('plan1.db.example.com'), Lit('192.0.2.3')), 'lb-3-1.db.example.com'),
    Tuple(Tuple(Lit('plan2.db.example.com'), Lit('192.0.2.1')), 'lb-1-2.db.example.com'),
    Tuple(Tuple(Lit('plan2.db.example.com'), Lit('192.0.2.2')), 'lb-2-2.db.example.com'),
    Tuple(Tuple(Lit('plan2.db.example.com'), Lit('192.0.2.3')), 'lb-3-2.db.example.com'),
    Tuple(Tuple(Lit('plan3.db.example.com'), Lit('192.0.2.1')), 'lb-1-3.db.example.com'),
    Tuple(Tuple(Lit('plan3.db.example.com'), Lit('192.0.2.2')), 'lb-2-3.db.example.com'),
    Tuple(Tuple(Lit('plan3.db.example.com'), Lit('192.0.2.3')), 'lb-3-3.db.example.com'),
    Tuple(Tuple(Lit('plan4.db.example.com'), Lit('192.0.2.1')), 'lb-1-4.db.example.com'),
    Tuple(Tuple(Lit('plan4.db.example.com'), Lit('192.0.2.2')), 'lb-2-4.db.example.com'),
    Tuple(Tuple(Lit('plan4.db.example.com'), Lit('192.0.2.3')), 'lb-3-4.db.example.com')
  ),
  WEIGHTS=Interval(Lit(100), Lit(120)),
  MAX_PLAN_AGE=(3),
  zone_records=Var(zone_records),
  planner_updates=Var(planner_updates),
  deployer_next_plan=Var(deployer_next_plan),
  deployer_view=Var(deployer_view),
  ghost_action=Var(ghost_action)
)
```
</details>

## 2. Defining actions

Let's go over `init`, `planner_generate`, `deployer_query`, `deployer_backoff`,
`deployer_apply`, `deployer_gc`. Finally, let's have a look at `step`.

## 3. Manually executing the steps

Did we say that our spec is executable? Let's just manually execute several
steps:

```python
# Step 1
from random import Random
from wunderspec import *
from dns_balancer import *
c = ExecContext(n3_5_3(), RandomScheduler(Random(100)))
c.step(init)
#   IPython: value(c.state.zone_records)
print(value(c.state.zone_records).pretty())
# Step 2
c.try_step(planner_generate)
#   IPython: value(c.state.planner_updates)
print(value(c.state.planner_updates).pretty())
# Step 3: the deployer A applies the plan
assert(c.try_step(deployer_apply, 'deployer-a'))
#   IPython: value(c.state.deployer_view['deployer-a'])
print(value(c.state.deployer_view['deployer-a']).pretty())
# Step 4: the deployer B fails to apply the plan, as it is out of sync
assert(not c.try_step(deployer_apply, 'deployer-b'))
#   IPython: value(c.state.deployer_view['deployer-b'])
print(value(c.state.deployer_view['deployer-b']).pretty())
# Step 5: the deployer B may back off
assert(c.try_step(deployer_backoff, 'deployer-b'))
# Step 6: the deployer B syncs
assert(c.try_step(deployer_query, 'deployer-b'))
# Step 7: the deployer B applies the plan
assert(c.try_step(deployer_apply, 'deployer-b'))
#   IPython: value(c.state.deployer_view['deployer-b'])
print(value(c.state.deployer_view['deployer-b']).pretty())
```

<details>

<summary>Click to see the output</summary>
<!--pytest-codeblocks:expected-output-->
```text
Set({
  Record(
    kind=CNAME,
    name=db.us-east-1.example.com,
    value=(plan-init.db.example.com, 1)
  ),
  Record(
    kind=CNAME,
    name=plan-init.db.example.com,
    value=(lb-1-init.db.example.com, 100)
  ),
  Record(kind=TXT, name=lock.example.com, value=(genesis, 0)),
  Record(
    kind=CNAME,
    name=rollback.db.example.com,
    value=(plan-init.db.example.com, 1)
  )
})
[
  Record(
    creates=Set({
      Record(
        kind=CNAME,
        name=plan2.db.example.com,
        value=(lb-2-2.db.example.com, 119)
      ),
      Record(kind=A, name=plan2.db.example.com, value=(192.0.2.2, 1)),
      Record(
        kind=CNAME,
        name=plan2.db.example.com,
        value=(lb-3-2.db.example.com, 118)
      ),
      Record(
        kind=CNAME,
        name=plan2.db.example.com,
        value=(lb-1-2.db.example.com, 116)
      ),
      Record(kind=A, name=plan2.db.example.com, value=(192.0.2.1, 1)),
      Record(kind=A, name=plan2.db.example.com, value=(192.0.2.3, 1))
    }),
    plan_id=plan2.db.example.com
  )
]
Record(
  lock=Record(kind=TXT, name=lock.example.com, value=(deployer-a, 1)),
  rollback=plan-init.db.example.com,
  root=plan2.db.example.com
)
Record(
  lock=Record(kind=TXT, name=lock.example.com, value=(genesis, 0)),
  rollback=plan-init.db.example.com,
  root=plan-init.db.example.com
)
Record(
  lock=Record(kind=TXT, name=lock.example.com, value=(deployer-b, 2)),
  rollback=plan2.db.example.com,
  root=plan2.db.example.com
)
```
</details>

## 4. Adding a bit of automation

Obviously, choosing the right parameters is tedious. We can rely on the random
scheduler.

### 4.1. Running random simulations

```sh
uv run wunderspec run dns_balancer.py --instance n3_5_3 --seed=123 --max-steps=10
```

<details>

<summary>Click to see the output</summary>
<!--pytest-codeblocks:expected-output-->
```text
info: Seed: 123
Rerun the search with: wunderspec run --seed=123 --instance n3_5_3 --max-steps 10 dns_balancer.py
info: No --property provided; use --property to search for a property. Looking for the longest trace.
success: Explored 1000 samples without checking a predicate
Best trace seed: 4937772249435845478
Best trace length: 10
[State 0]
  BALANCER_NAMES: Map(
                    ('plan0.db.example.com', '192.0.2.1') ->
                      'lb-1-0.db.example.com',
                    ('plan0.db.example.com', '192.0.2.2') ->
                      'lb-2-0.db.example.com',
                    ('plan0.db.example.com', '192.0.2.3') ->
                      'lb-3-0.db.example.com',
                    ('plan1.db.example.com', '192.0.2.1') ->
                      'lb-1-1.db.example.com',
                    ('plan1.db.example.com', '192.0.2.2') ->
                      'lb-2-1.db.example.com',
                    ('plan1.db.example.com', '192.0.2.3') ->
                      'lb-3-1.db.example.com',
                    ('plan2.db.example.com', '192.0.2.1') ->
                      'lb-1-2.db.example.com',
                    ('plan2.db.example.com', '192.0.2.2') ->
                      'lb-2-2.db.example.com',
                    ('plan2.db.example.com', '192.0.2.3') ->
                      'lb-3-2.db.example.com',
                    ('plan3.db.example.com', '192.0.2.1') ->
                      'lb-1-3.db.example.com',
                    ('plan3.db.example.com', '192.0.2.2') ->
                      'lb-2-3.db.example.com',
                    ('plan3.db.example.com', '192.0.2.3') ->
                      'lb-3-3.db.example.com',
                    ('plan4.db.example.com', '192.0.2.1') ->
                      'lb-1-4.db.example.com',
                    ('plan4.db.example.com', '192.0.2.2') ->
                      'lb-2-4.db.example.com',
                    ('plan4.db.example.com', '192.0.2.3') ->
                      'lb-3-4.db.example.com'
                  )
  DEPLOYERS: Set({'deployer-a', 'deployer-b', 'deployer-c'})
  IPS: Set({'192.0.2.1', '192.0.2.2', '192.0.2.3'})
  MAX_PLAN_AGE: 3
  PLAN_IDS: Set({
              'plan0.db.example.com',
              'plan1.db.example.com',
              'plan2.db.example.com',
              'plan3.db.example.com',
              'plan4.db.example.com'
            })
  WEIGHTS: Set(100, ..., 120)
  deployer_next_plan: Map(
                        'deployer-a' -> 0,
                        'deployer-b' -> 0,
                        'deployer-c' -> 0
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     )
                 )
  ghost_action: Init
  planner_updates: []
  zone_records: Set({
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('genesis', 0)
                  )
                })
[State 1]
  deployer_next_plan: Map(
                        'deployer-a' -> 0,
                        'deployer-b' -> 0,
                        'deployer-c' -> 0
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     )
                 )
  ghost_action: Sync(
                  Record(
                    deployer='deployer-c',
                    lock=Record(
                        kind='TXT',
                        name='lock.example.com',
                        value=('genesis', 0)
                      ),
                    rollback='plan-init.db.example.com',
                    root='plan-init.db.example.com'
                  )
                )
  planner_updates: []
  zone_records: Set({
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('genesis', 0)
                  )
                })
[State 2]
  deployer_next_plan: Map(
                        'deployer-a' -> 0,
                        'deployer-b' -> 0,
                        'deployer-c' -> 0
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     )
                 )
  ghost_action: Sync(
                  Record(
                    deployer='deployer-c',
                    lock=Record(
                        kind='TXT',
                        name='lock.example.com',
                        value=('genesis', 0)
                      ),
                    rollback='plan-init.db.example.com',
                    root='plan-init.db.example.com'
                  )
                )
  planner_updates: []
  zone_records: Set({
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('genesis', 0)
                  )
                })
[State 3]
  deployer_next_plan: Map(
                        'deployer-a' -> 0,
                        'deployer-b' -> 0,
                        'deployer-c' -> 0
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     )
                 )
  ghost_action: GeneratePlan(
                  Record(
                    ips=Set({'192.0.2.2'}),
                    plan_id='plan3.db.example.com',
                    weights=Map('192.0.2.2' -> 114)
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-2-3.db.example.com', 114)
                           )
                         }),
                       plan_id='plan3.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('genesis', 0)
                  )
                })
[State 4]
  deployer_next_plan: Map(
                        'deployer-a' -> 0,
                        'deployer-b' -> 0,
                        'deployer-c' -> 0
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     )
                 )
  ghost_action: Sync(
                  Record(
                    deployer='deployer-c',
                    lock=Record(
                        kind='TXT',
                        name='lock.example.com',
                        value=('genesis', 0)
                      ),
                    rollback='plan-init.db.example.com',
                    root='plan-init.db.example.com'
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-2-3.db.example.com', 114)
                           )
                         }),
                       plan_id='plan3.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('genesis', 0)
                  )
                })
[State 5]
  deployer_next_plan: Map(
                        'deployer-a' -> 0,
                        'deployer-b' -> 0,
                        'deployer-c' -> 0
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     )
                 )
  ghost_action: GeneratePlan(
                  Record(
                    ips=Set({'192.0.2.1', '192.0.2.2', '192.0.2.3'}),
                    plan_id='plan2.db.example.com',
                    weights=Map(
                        '192.0.2.1' -> 111,
                        '192.0.2.2' -> 117,
                        '192.0.2.3' -> 110
                      )
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-2-3.db.example.com', 114)
                           )
                         }),
                       plan_id='plan3.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-1-2.db.example.com', 111)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-2-2.db.example.com', 117)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-3-2.db.example.com', 110)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('genesis', 0)
                  )
                })
[State 6]
  deployer_next_plan: Map(
                        'deployer-a' -> 0,
                        'deployer-b' -> 0,
                        'deployer-c' -> 0
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     )
                 )
  ghost_action: Sync(
                  Record(
                    deployer='deployer-a',
                    lock=Record(
                        kind='TXT',
                        name='lock.example.com',
                        value=('genesis', 0)
                      ),
                    rollback='plan-init.db.example.com',
                    root='plan-init.db.example.com'
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-2-3.db.example.com', 114)
                           )
                         }),
                       plan_id='plan3.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-1-2.db.example.com', 111)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-2-2.db.example.com', 117)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-3-2.db.example.com', 110)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('genesis', 0)
                  )
                })
[State 7]
  deployer_next_plan: Map(
                        'deployer-a' -> 0,
                        'deployer-b' -> 0,
                        'deployer-c' -> 0
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     )
                 )
  ghost_action: Sync(
                  Record(
                    deployer='deployer-b',
                    lock=Record(
                        kind='TXT',
                        name='lock.example.com',
                        value=('genesis', 0)
                      ),
                    rollback='plan-init.db.example.com',
                    root='plan-init.db.example.com'
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-2-3.db.example.com', 114)
                           )
                         }),
                       plan_id='plan3.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-1-2.db.example.com', 111)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-2-2.db.example.com', 117)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-3-2.db.example.com', 110)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('genesis', 0)
                  )
                })
[State 8]
  deployer_next_plan: Map(
                        'deployer-a' -> 1,
                        'deployer-b' -> 0,
                        'deployer-c' -> 0
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-a', 1)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan3.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     )
                 )
  ghost_action: Deploy(
                  Record(
                    deployer='deployer-a',
                    new_epoch=1,
                    new_root='plan3.db.example.com',
                    plan_id='plan3.db.example.com',
                    previous_root='plan-init.db.example.com',
                    rollback='plan-init.db.example.com'
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-2-3.db.example.com', 114)
                           )
                         }),
                       plan_id='plan3.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-1-2.db.example.com', 111)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-2-2.db.example.com', 117)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-3-2.db.example.com', 110)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='A',
                    name='plan3.db.example.com',
                    value=('192.0.2.2', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan3.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan3.db.example.com',
                    value=('lb-2-3.db.example.com', 114)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('deployer-a', 1)
                  )
                })
[State 9]
  deployer_next_plan: Map(
                        'deployer-a' -> 1,
                        'deployer-b' -> 0,
                        'deployer-c' -> 0
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-a', 1)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan3.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     )
                 )
  ghost_action: Backoff(
                  Record(
                    deployer='deployer-c',
                    lock=Record(
                        kind='TXT',
                        name='lock.example.com',
                        value=('genesis', 0)
                      )
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-2-3.db.example.com', 114)
                           )
                         }),
                       plan_id='plan3.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-1-2.db.example.com', 111)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-2-2.db.example.com', 117)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-3-2.db.example.com', 110)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='A',
                    name='plan3.db.example.com',
                    value=('192.0.2.2', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan3.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan3.db.example.com',
                    value=('lb-2-3.db.example.com', 114)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('deployer-a', 1)
                  )
                })
Replay with: wunderspec replay --instance n3_5_3 --max-steps 10 dns_balancer.py --seed 4937772249435845478
```
</details>

### 4.2. Random simulations to find an example

Executing actions at random may help us in finding simple bugs, e.g., invalid
key access.

We can use the simulator to produce examples of reaching certain goals. For
instance, let's look at `epoch5` and then run the simulator:

```sh
uv run wunderspec run dns_balancer.py \
  --instance n3_5_3 --seed=123 --max-steps=10 --property=epoch5
```

<!--pytest-codeblocks:expected-output-->
```text
info: Seed: 123
Rerun the search with: wunderspec run --seed=123 --instance n3_5_3 --property epoch5 --max-steps 10 dns_balancer.py
success: No examples found in 1000 samples
```

It did not find anything. There may be two reasons: (1) the step budget is too
low, or (2) we enumerated too few samples. Let's increase the step budget:

```sh
uv run wunderspec run dns_balancer.py \
  --instance n3_5_3 --seed=123 --max-steps=20 --property=epoch5 || test $? -eq 2
```

This time, we find an example trace.

<details>

<summary>Click to see the output</summary>
<!--pytest-codeblocks:expected-output-->
```text
info: Seed: 123
Rerun the search with: wunderspec run --seed=123 --instance n3_5_3 --property epoch5 dns_balancer.py
Example found at state 16
Trace seed: 5382787838203902085
[State 0]
  BALANCER_NAMES: Map(
                    ('plan0.db.example.com', '192.0.2.1') ->
                      'lb-1-0.db.example.com',
                    ('plan0.db.example.com', '192.0.2.2') ->
                      'lb-2-0.db.example.com',
                    ('plan0.db.example.com', '192.0.2.3') ->
                      'lb-3-0.db.example.com',
                    ('plan1.db.example.com', '192.0.2.1') ->
                      'lb-1-1.db.example.com',
                    ('plan1.db.example.com', '192.0.2.2') ->
                      'lb-2-1.db.example.com',
                    ('plan1.db.example.com', '192.0.2.3') ->
                      'lb-3-1.db.example.com',
                    ('plan2.db.example.com', '192.0.2.1') ->
                      'lb-1-2.db.example.com',
                    ('plan2.db.example.com', '192.0.2.2') ->
                      'lb-2-2.db.example.com',
                    ('plan2.db.example.com', '192.0.2.3') ->
                      'lb-3-2.db.example.com',
                    ('plan3.db.example.com', '192.0.2.1') ->
                      'lb-1-3.db.example.com',
                    ('plan3.db.example.com', '192.0.2.2') ->
                      'lb-2-3.db.example.com',
                    ('plan3.db.example.com', '192.0.2.3') ->
                      'lb-3-3.db.example.com',
                    ('plan4.db.example.com', '192.0.2.1') ->
                      'lb-1-4.db.example.com',
                    ('plan4.db.example.com', '192.0.2.2') ->
                      'lb-2-4.db.example.com',
                    ('plan4.db.example.com', '192.0.2.3') ->
                      'lb-3-4.db.example.com'
                  )
  DEPLOYERS: Set({'deployer-a', 'deployer-b', 'deployer-c'})
  IPS: Set({'192.0.2.1', '192.0.2.2', '192.0.2.3'})
  MAX_PLAN_AGE: 3
  PLAN_IDS: Set({
              'plan0.db.example.com',
              'plan1.db.example.com',
              'plan2.db.example.com',
              'plan3.db.example.com',
              'plan4.db.example.com'
            })
  WEIGHTS: Set(100, ..., 120)
  deployer_next_plan: Map(
                        'deployer-a' -> 0,
                        'deployer-b' -> 0,
                        'deployer-c' -> 0
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     )
                 )
  ghost_action: Init
  planner_updates: []
  zone_records: Set({
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('genesis', 0)
                  )
                })
[State 1]
  deployer_next_plan: Map(
                        'deployer-a' -> 0,
                        'deployer-b' -> 0,
                        'deployer-c' -> 0
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     )
                 )
  ghost_action: Sync(
                  Record(
                    deployer='deployer-c',
                    lock=Record(
                        kind='TXT',
                        name='lock.example.com',
                        value=('genesis', 0)
                      ),
                    rollback='plan-init.db.example.com',
                    root='plan-init.db.example.com'
                  )
                )
  planner_updates: []
  zone_records: Set({
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('genesis', 0)
                  )
                })
[State 2]
  deployer_next_plan: Map(
                        'deployer-a' -> 0,
                        'deployer-b' -> 0,
                        'deployer-c' -> 0
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     )
                 )
  ghost_action: Sync(
                  Record(
                    deployer='deployer-b',
                    lock=Record(
                        kind='TXT',
                        name='lock.example.com',
                        value=('genesis', 0)
                      ),
                    rollback='plan-init.db.example.com',
                    root='plan-init.db.example.com'
                  )
                )
  planner_updates: []
  zone_records: Set({
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('genesis', 0)
                  )
                })
[State 3]
  deployer_next_plan: Map(
                        'deployer-a' -> 0,
                        'deployer-b' -> 0,
                        'deployer-c' -> 0
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     )
                 )
  ghost_action: GeneratePlan(
                  Record(
                    ips=Set({'192.0.2.1'}),
                    plan_id='plan1.db.example.com',
                    weights=Map('192.0.2.1' -> 118)
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan1.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan1.db.example.com',
                             value=('lb-1-1.db.example.com', 118)
                           )
                         }),
                       plan_id='plan1.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('genesis', 0)
                  )
                })
[State 4]
  deployer_next_plan: Map(
                        'deployer-a' -> 1,
                        'deployer-b' -> 0,
                        'deployer-c' -> 0
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-a', 1)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan1.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     )
                 )
  ghost_action: Deploy(
                  Record(
                    deployer='deployer-a',
                    new_epoch=1,
                    new_root='plan1.db.example.com',
                    plan_id='plan1.db.example.com',
                    previous_root='plan-init.db.example.com',
                    rollback='plan-init.db.example.com'
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan1.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan1.db.example.com',
                             value=('lb-1-1.db.example.com', 118)
                           )
                         }),
                       plan_id='plan1.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='A',
                    name='plan1.db.example.com',
                    value=('192.0.2.1', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan1.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan1.db.example.com',
                    value=('lb-1-1.db.example.com', 118)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('deployer-a', 1)
                  )
                })
[State 5]
  deployer_next_plan: Map(
                        'deployer-a' -> 1,
                        'deployer-b' -> 0,
                        'deployer-c' -> 0
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-a', 1)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan1.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-a', 1)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan1.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     )
                 )
  ghost_action: Sync(
                  Record(
                    deployer='deployer-b',
                    lock=Record(
                        kind='TXT',
                        name='lock.example.com',
                        value=('deployer-a', 1)
                      ),
                    rollback='plan-init.db.example.com',
                    root='plan1.db.example.com'
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan1.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan1.db.example.com',
                             value=('lb-1-1.db.example.com', 118)
                           )
                         }),
                       plan_id='plan1.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='A',
                    name='plan1.db.example.com',
                    value=('192.0.2.1', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan1.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan1.db.example.com',
                    value=('lb-1-1.db.example.com', 118)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('deployer-a', 1)
                  )
                })
[State 6]
  deployer_next_plan: Map(
                        'deployer-a' -> 1,
                        'deployer-b' -> 0,
                        'deployer-c' -> 0
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-a', 1)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan1.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-a', 1)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan1.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-a', 1)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan1.db.example.com'
                     )
                 )
  ghost_action: Sync(
                  Record(
                    deployer='deployer-c',
                    lock=Record(
                        kind='TXT',
                        name='lock.example.com',
                        value=('deployer-a', 1)
                      ),
                    rollback='plan-init.db.example.com',
                    root='plan1.db.example.com'
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan1.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan1.db.example.com',
                             value=('lb-1-1.db.example.com', 118)
                           )
                         }),
                       plan_id='plan1.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='A',
                    name='plan1.db.example.com',
                    value=('192.0.2.1', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan1.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan1.db.example.com',
                    value=('lb-1-1.db.example.com', 118)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('deployer-a', 1)
                  )
                })
[State 7]
  deployer_next_plan: Map(
                        'deployer-a' -> 1,
                        'deployer-b' -> 0,
                        'deployer-c' -> 0
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-a', 1)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan1.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-a', 1)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan1.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-a', 1)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan1.db.example.com'
                     )
                 )
  ghost_action: GeneratePlan(
                  Record(
                    ips=Set({'192.0.2.1', '192.0.2.3'}),
                    plan_id='plan4.db.example.com',
                    weights=Map('192.0.2.1' -> 109, '192.0.2.3' -> 116)
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan1.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan1.db.example.com',
                             value=('lb-1-1.db.example.com', 118)
                           )
                         }),
                       plan_id='plan1.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-1-4.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-3-4.db.example.com', 116)
                           )
                         }),
                       plan_id='plan4.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='A',
                    name='plan1.db.example.com',
                    value=('192.0.2.1', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan1.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan1.db.example.com',
                    value=('lb-1-1.db.example.com', 118)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('deployer-a', 1)
                  )
                })
[State 8]
  deployer_next_plan: Map(
                        'deployer-a' -> 1,
                        'deployer-b' -> 0,
                        'deployer-c' -> 0
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-a', 1)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan1.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-a', 1)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan1.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-a', 1)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan1.db.example.com'
                     )
                 )
  ghost_action: GeneratePlan(
                  Record(
                    ips=Set({'192.0.2.1', '192.0.2.2'}),
                    plan_id='plan2.db.example.com',
                    weights=Map('192.0.2.1' -> 115, '192.0.2.2' -> 109)
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan1.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan1.db.example.com',
                             value=('lb-1-1.db.example.com', 118)
                           )
                         }),
                       plan_id='plan1.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-1-4.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-3-4.db.example.com', 116)
                           )
                         }),
                       plan_id='plan4.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-1-2.db.example.com', 115)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-2-2.db.example.com', 109)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='A',
                    name='plan1.db.example.com',
                    value=('192.0.2.1', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan1.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan1.db.example.com',
                    value=('lb-1-1.db.example.com', 118)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('deployer-a', 1)
                  )
                })
[State 9]
  deployer_next_plan: Map(
                        'deployer-a' -> 1,
                        'deployer-b' -> 0,
                        'deployer-c' -> 1
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-a', 1)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan1.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-a', 1)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan1.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-c', 2)
                         ),
                       rollback='plan1.db.example.com',
                       root='plan1.db.example.com'
                     )
                 )
  ghost_action: Deploy(
                  Record(
                    deployer='deployer-c',
                    new_epoch=2,
                    new_root='plan1.db.example.com',
                    plan_id='plan1.db.example.com',
                    previous_root='plan1.db.example.com',
                    rollback='plan1.db.example.com'
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan1.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan1.db.example.com',
                             value=('lb-1-1.db.example.com', 118)
                           )
                         }),
                       plan_id='plan1.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-1-4.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-3-4.db.example.com', 116)
                           )
                         }),
                       plan_id='plan4.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-1-2.db.example.com', 115)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-2-2.db.example.com', 109)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='A',
                    name='plan1.db.example.com',
                    value=('192.0.2.1', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan1.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan1.db.example.com',
                    value=('lb-1-1.db.example.com', 118)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan1.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('deployer-c', 2)
                  )
                })
[State 10]
  deployer_next_plan: Map(
                        'deployer-a' -> 1,
                        'deployer-b' -> 0,
                        'deployer-c' -> 1
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-a', 1)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan1.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-c', 2)
                         ),
                       rollback='plan1.db.example.com',
                       root='plan1.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-c', 2)
                         ),
                       rollback='plan1.db.example.com',
                       root='plan1.db.example.com'
                     )
                 )
  ghost_action: Sync(
                  Record(
                    deployer='deployer-b',
                    lock=Record(
                        kind='TXT',
                        name='lock.example.com',
                        value=('deployer-c', 2)
                      ),
                    rollback='plan1.db.example.com',
                    root='plan1.db.example.com'
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan1.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan1.db.example.com',
                             value=('lb-1-1.db.example.com', 118)
                           )
                         }),
                       plan_id='plan1.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-1-4.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-3-4.db.example.com', 116)
                           )
                         }),
                       plan_id='plan4.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-1-2.db.example.com', 115)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-2-2.db.example.com', 109)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='A',
                    name='plan1.db.example.com',
                    value=('192.0.2.1', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan1.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan1.db.example.com',
                    value=('lb-1-1.db.example.com', 118)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan1.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('deployer-c', 2)
                  )
                })
[State 11]
  deployer_next_plan: Map(
                        'deployer-a' -> 1,
                        'deployer-b' -> 0,
                        'deployer-c' -> 1
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-a', 1)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan1.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-c', 2)
                         ),
                       rollback='plan1.db.example.com',
                       root='plan1.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-c', 2)
                         ),
                       rollback='plan1.db.example.com',
                       root='plan1.db.example.com'
                     )
                 )
  ghost_action: Sync(
                  Record(
                    deployer='deployer-b',
                    lock=Record(
                        kind='TXT',
                        name='lock.example.com',
                        value=('deployer-c', 2)
                      ),
                    rollback='plan1.db.example.com',
                    root='plan1.db.example.com'
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan1.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan1.db.example.com',
                             value=('lb-1-1.db.example.com', 118)
                           )
                         }),
                       plan_id='plan1.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-1-4.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-3-4.db.example.com', 116)
                           )
                         }),
                       plan_id='plan4.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-1-2.db.example.com', 115)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-2-2.db.example.com', 109)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='A',
                    name='plan1.db.example.com',
                    value=('192.0.2.1', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan1.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan1.db.example.com',
                    value=('lb-1-1.db.example.com', 118)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan1.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('deployer-c', 2)
                  )
                })
[State 12]
  deployer_next_plan: Map(
                        'deployer-a' -> 1,
                        'deployer-b' -> 1,
                        'deployer-c' -> 1
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-a', 1)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan1.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-b', 3)
                         ),
                       rollback='plan1.db.example.com',
                       root='plan1.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-c', 2)
                         ),
                       rollback='plan1.db.example.com',
                       root='plan1.db.example.com'
                     )
                 )
  ghost_action: Deploy(
                  Record(
                    deployer='deployer-b',
                    new_epoch=3,
                    new_root='plan1.db.example.com',
                    plan_id='plan1.db.example.com',
                    previous_root='plan1.db.example.com',
                    rollback='plan1.db.example.com'
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan1.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan1.db.example.com',
                             value=('lb-1-1.db.example.com', 118)
                           )
                         }),
                       plan_id='plan1.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-1-4.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-3-4.db.example.com', 116)
                           )
                         }),
                       plan_id='plan4.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-1-2.db.example.com', 115)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-2-2.db.example.com', 109)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='A',
                    name='plan1.db.example.com',
                    value=('192.0.2.1', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan1.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan1.db.example.com',
                    value=('lb-1-1.db.example.com', 118)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan1.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('deployer-b', 3)
                  )
                })
[State 13]
  deployer_next_plan: Map(
                        'deployer-a' -> 1,
                        'deployer-b' -> 1,
                        'deployer-c' -> 1
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-b', 3)
                         ),
                       rollback='plan1.db.example.com',
                       root='plan1.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-b', 3)
                         ),
                       rollback='plan1.db.example.com',
                       root='plan1.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-c', 2)
                         ),
                       rollback='plan1.db.example.com',
                       root='plan1.db.example.com'
                     )
                 )
  ghost_action: Sync(
                  Record(
                    deployer='deployer-a',
                    lock=Record(
                        kind='TXT',
                        name='lock.example.com',
                        value=('deployer-b', 3)
                      ),
                    rollback='plan1.db.example.com',
                    root='plan1.db.example.com'
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan1.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan1.db.example.com',
                             value=('lb-1-1.db.example.com', 118)
                           )
                         }),
                       plan_id='plan1.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-1-4.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-3-4.db.example.com', 116)
                           )
                         }),
                       plan_id='plan4.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-1-2.db.example.com', 115)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-2-2.db.example.com', 109)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='A',
                    name='plan1.db.example.com',
                    value=('192.0.2.1', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan1.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan1.db.example.com',
                    value=('lb-1-1.db.example.com', 118)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan1.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('deployer-b', 3)
                  )
                })
[State 14]
  deployer_next_plan: Map(
                        'deployer-a' -> 1,
                        'deployer-b' -> 1,
                        'deployer-c' -> 1
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-b', 3)
                         ),
                       rollback='plan1.db.example.com',
                       root='plan1.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-b', 3)
                         ),
                       rollback='plan1.db.example.com',
                       root='plan1.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-c', 2)
                         ),
                       rollback='plan1.db.example.com',
                       root='plan1.db.example.com'
                     )
                 )
  ghost_action: Sync(
                  Record(
                    deployer='deployer-b',
                    lock=Record(
                        kind='TXT',
                        name='lock.example.com',
                        value=('deployer-b', 3)
                      ),
                    rollback='plan1.db.example.com',
                    root='plan1.db.example.com'
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan1.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan1.db.example.com',
                             value=('lb-1-1.db.example.com', 118)
                           )
                         }),
                       plan_id='plan1.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-1-4.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-3-4.db.example.com', 116)
                           )
                         }),
                       plan_id='plan4.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-1-2.db.example.com', 115)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-2-2.db.example.com', 109)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='A',
                    name='plan1.db.example.com',
                    value=('192.0.2.1', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan1.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan1.db.example.com',
                    value=('lb-1-1.db.example.com', 118)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan1.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('deployer-b', 3)
                  )
                })
[State 15]
  deployer_next_plan: Map(
                        'deployer-a' -> 1,
                        'deployer-b' -> 2,
                        'deployer-c' -> 1
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-b', 3)
                         ),
                       rollback='plan1.db.example.com',
                       root='plan1.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-b', 4)
                         ),
                       rollback='plan1.db.example.com',
                       root='plan4.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-c', 2)
                         ),
                       rollback='plan1.db.example.com',
                       root='plan1.db.example.com'
                     )
                 )
  ghost_action: Deploy(
                  Record(
                    deployer='deployer-b',
                    new_epoch=4,
                    new_root='plan4.db.example.com',
                    plan_id='plan4.db.example.com',
                    previous_root='plan1.db.example.com',
                    rollback='plan1.db.example.com'
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan1.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan1.db.example.com',
                             value=('lb-1-1.db.example.com', 118)
                           )
                         }),
                       plan_id='plan1.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-1-4.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-3-4.db.example.com', 116)
                           )
                         }),
                       plan_id='plan4.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-1-2.db.example.com', 115)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-2-2.db.example.com', 109)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='A',
                    name='plan1.db.example.com',
                    value=('192.0.2.1', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan4.db.example.com',
                    value=('192.0.2.1', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan4.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan4.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan1.db.example.com',
                    value=('lb-1-1.db.example.com', 118)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan4.db.example.com',
                    value=('lb-1-4.db.example.com', 109)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan4.db.example.com',
                    value=('lb-3-4.db.example.com', 116)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan1.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('deployer-b', 4)
                  )
                })
[State 16]
  deployer_next_plan: Map(
                        'deployer-a' -> 1,
                        'deployer-b' -> 3,
                        'deployer-c' -> 1
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-b', 3)
                         ),
                       rollback='plan1.db.example.com',
                       root='plan1.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-b', 5)
                         ),
                       rollback='plan4.db.example.com',
                       root='plan2.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-c', 2)
                         ),
                       rollback='plan1.db.example.com',
                       root='plan1.db.example.com'
                     )
                 )
  ghost_action: Deploy(
                  Record(
                    deployer='deployer-b',
                    new_epoch=5,
                    new_root='plan2.db.example.com',
                    plan_id='plan2.db.example.com',
                    previous_root='plan4.db.example.com',
                    rollback='plan4.db.example.com'
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan1.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan1.db.example.com',
                             value=('lb-1-1.db.example.com', 118)
                           )
                         }),
                       plan_id='plan1.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-1-4.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-3-4.db.example.com', 116)
                           )
                         }),
                       plan_id='plan4.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-1-2.db.example.com', 115)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-2-2.db.example.com', 109)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='A',
                    name='plan1.db.example.com',
                    value=('192.0.2.1', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan2.db.example.com',
                    value=('192.0.2.1', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan2.db.example.com',
                    value=('192.0.2.2', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan4.db.example.com',
                    value=('192.0.2.1', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan4.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan2.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan1.db.example.com',
                    value=('lb-1-1.db.example.com', 118)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan2.db.example.com',
                    value=('lb-1-2.db.example.com', 115)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan2.db.example.com',
                    value=('lb-2-2.db.example.com', 109)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan4.db.example.com',
                    value=('lb-1-4.db.example.com', 109)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan4.db.example.com',
                    value=('lb-3-4.db.example.com', 116)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan4.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('deployer-b', 5)
                  )
                })
Replay with: wunderspec replay --instance n3_5_3 --property epoch5 --max-steps 20 dns_balancer.py --seed 5382787838203902085
info: Found 1 example trace(s) in 13 samples
```
</details>

### 4.3. Random simulations to find invariant violations

We use the same approach to look for invariant violations:

```sh
uv run wunderspec run dns_balancer.py \
  --instance n3_5_3 --seed=123 --max-steps=20 --property no_inconsistent_root || test $? -eq 1
```

**We get the trace pretty fast!**

<details>

<summary>Click to see the output</summary>
<!--pytest-codeblocks:expected-output-->
```text
info: Seed: 123
Rerun the search with: wunderspec run --seed=123 --instance n3_5_3 --property no_inconsistent_root dns_balancer.py
Invariant violation at state 17
Trace seed: 5259027364429190200
[State 0]
  BALANCER_NAMES: Map(
                    ('plan0.db.example.com', '192.0.2.1') ->
                      'lb-1-0.db.example.com',
                    ('plan0.db.example.com', '192.0.2.2') ->
                      'lb-2-0.db.example.com',
                    ('plan0.db.example.com', '192.0.2.3') ->
                      'lb-3-0.db.example.com',
                    ('plan1.db.example.com', '192.0.2.1') ->
                      'lb-1-1.db.example.com',
                    ('plan1.db.example.com', '192.0.2.2') ->
                      'lb-2-1.db.example.com',
                    ('plan1.db.example.com', '192.0.2.3') ->
                      'lb-3-1.db.example.com',
                    ('plan2.db.example.com', '192.0.2.1') ->
                      'lb-1-2.db.example.com',
                    ('plan2.db.example.com', '192.0.2.2') ->
                      'lb-2-2.db.example.com',
                    ('plan2.db.example.com', '192.0.2.3') ->
                      'lb-3-2.db.example.com',
                    ('plan3.db.example.com', '192.0.2.1') ->
                      'lb-1-3.db.example.com',
                    ('plan3.db.example.com', '192.0.2.2') ->
                      'lb-2-3.db.example.com',
                    ('plan3.db.example.com', '192.0.2.3') ->
                      'lb-3-3.db.example.com',
                    ('plan4.db.example.com', '192.0.2.1') ->
                      'lb-1-4.db.example.com',
                    ('plan4.db.example.com', '192.0.2.2') ->
                      'lb-2-4.db.example.com',
                    ('plan4.db.example.com', '192.0.2.3') ->
                      'lb-3-4.db.example.com'
                  )
  DEPLOYERS: Set({'deployer-a', 'deployer-b', 'deployer-c'})
  IPS: Set({'192.0.2.1', '192.0.2.2', '192.0.2.3'})
  MAX_PLAN_AGE: 3
  PLAN_IDS: Set({
              'plan0.db.example.com',
              'plan1.db.example.com',
              'plan2.db.example.com',
              'plan3.db.example.com',
              'plan4.db.example.com'
            })
  WEIGHTS: Set(100, ..., 120)
  deployer_next_plan: Map(
                        'deployer-a' -> 0,
                        'deployer-b' -> 0,
                        'deployer-c' -> 0
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     )
                 )
  ghost_action: Init
  planner_updates: []
  zone_records: Set({
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('genesis', 0)
                  )
                })
[State 1]
  deployer_next_plan: Map(
                        'deployer-a' -> 0,
                        'deployer-b' -> 0,
                        'deployer-c' -> 0
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     )
                 )
  ghost_action: GeneratePlan(
                  Record(
                    ips=Set({'192.0.2.3'}),
                    plan_id='plan2.db.example.com',
                    weights=Map('192.0.2.3' -> 111)
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-3-2.db.example.com', 111)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('genesis', 0)
                  )
                })
[State 2]
  deployer_next_plan: Map(
                        'deployer-a' -> 0,
                        'deployer-b' -> 0,
                        'deployer-c' -> 0
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     )
                 )
  ghost_action: Sync(
                  Record(
                    deployer='deployer-b',
                    lock=Record(
                        kind='TXT',
                        name='lock.example.com',
                        value=('genesis', 0)
                      ),
                    rollback='plan-init.db.example.com',
                    root='plan-init.db.example.com'
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-3-2.db.example.com', 111)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('genesis', 0)
                  )
                })
[State 3]
  deployer_next_plan: Map(
                        'deployer-a' -> 0,
                        'deployer-b' -> 0,
                        'deployer-c' -> 1
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-c', 1)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan2.db.example.com'
                     )
                 )
  ghost_action: Deploy(
                  Record(
                    deployer='deployer-c',
                    new_epoch=1,
                    new_root='plan2.db.example.com',
                    plan_id='plan2.db.example.com',
                    previous_root='plan-init.db.example.com',
                    rollback='plan-init.db.example.com'
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-3-2.db.example.com', 111)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='A',
                    name='plan2.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan2.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan2.db.example.com',
                    value=('lb-3-2.db.example.com', 111)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('deployer-c', 1)
                  )
                })
[State 4]
  deployer_next_plan: Map(
                        'deployer-a' -> 0,
                        'deployer-b' -> 0,
                        'deployer-c' -> 1
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-c', 1)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan2.db.example.com'
                     )
                 )
  ghost_action: GeneratePlan(
                  Record(
                    ips=Set({'192.0.2.2', '192.0.2.3'}),
                    plan_id='plan4.db.example.com',
                    weights=Map('192.0.2.2' -> 109, '192.0.2.3' -> 119)
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-3-2.db.example.com', 111)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-2-4.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-3-4.db.example.com', 119)
                           )
                         }),
                       plan_id='plan4.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='A',
                    name='plan2.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan2.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan2.db.example.com',
                    value=('lb-3-2.db.example.com', 111)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('deployer-c', 1)
                  )
                })
[State 5]
  deployer_next_plan: Map(
                        'deployer-a' -> 0,
                        'deployer-b' -> 0,
                        'deployer-c' -> 1
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-c', 1)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan2.db.example.com'
                     )
                 )
  ghost_action: Backoff(
                  Record(
                    deployer='deployer-b',
                    lock=Record(
                        kind='TXT',
                        name='lock.example.com',
                        value=('genesis', 0)
                      )
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-3-2.db.example.com', 111)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-2-4.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-3-4.db.example.com', 119)
                           )
                         }),
                       plan_id='plan4.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='A',
                    name='plan2.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan2.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan2.db.example.com',
                    value=('lb-3-2.db.example.com', 111)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('deployer-c', 1)
                  )
                })
[State 6]
  deployer_next_plan: Map(
                        'deployer-a' -> 0,
                        'deployer-b' -> 0,
                        'deployer-c' -> 1
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-c', 1)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan2.db.example.com'
                     )
                 )
  ghost_action: GeneratePlan(
                  Record(
                    ips=Set({'192.0.2.1', '192.0.2.2', '192.0.2.3'}),
                    plan_id='plan3.db.example.com',
                    weights=Map(
                        '192.0.2.1' -> 109,
                        '192.0.2.2' -> 111,
                        '192.0.2.3' -> 107
                      )
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-3-2.db.example.com', 111)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-2-4.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-3-4.db.example.com', 119)
                           )
                         }),
                       plan_id='plan4.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-1-3.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-2-3.db.example.com', 111)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-3-3.db.example.com', 107)
                           )
                         }),
                       plan_id='plan3.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='A',
                    name='plan2.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan2.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan2.db.example.com',
                    value=('lb-3-2.db.example.com', 111)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan-init.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('deployer-c', 1)
                  )
                })
[State 7]
  deployer_next_plan: Map(
                        'deployer-a' -> 0,
                        'deployer-b' -> 0,
                        'deployer-c' -> 2
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-c', 2)
                         ),
                       rollback='plan2.db.example.com',
                       root='plan4.db.example.com'
                     )
                 )
  ghost_action: Deploy(
                  Record(
                    deployer='deployer-c',
                    new_epoch=2,
                    new_root='plan4.db.example.com',
                    plan_id='plan4.db.example.com',
                    previous_root='plan2.db.example.com',
                    rollback='plan2.db.example.com'
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-3-2.db.example.com', 111)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-2-4.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-3-4.db.example.com', 119)
                           )
                         }),
                       plan_id='plan4.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-1-3.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-2-3.db.example.com', 111)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-3-3.db.example.com', 107)
                           )
                         }),
                       plan_id='plan3.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='A',
                    name='plan2.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan4.db.example.com',
                    value=('192.0.2.2', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan4.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan4.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan2.db.example.com',
                    value=('lb-3-2.db.example.com', 111)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan4.db.example.com',
                    value=('lb-2-4.db.example.com', 109)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan4.db.example.com',
                    value=('lb-3-4.db.example.com', 119)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan2.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('deployer-c', 2)
                  )
                })
[State 8]
  deployer_next_plan: Map(
                        'deployer-a' -> 0,
                        'deployer-b' -> 0,
                        'deployer-c' -> 2
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-c', 2)
                         ),
                       rollback='plan2.db.example.com',
                       root='plan4.db.example.com'
                     )
                 )
  ghost_action: Backoff(
                  Record(
                    deployer='deployer-b',
                    lock=Record(
                        kind='TXT',
                        name='lock.example.com',
                        value=('genesis', 0)
                      )
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-3-2.db.example.com', 111)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-2-4.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-3-4.db.example.com', 119)
                           )
                         }),
                       plan_id='plan4.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-1-3.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-2-3.db.example.com', 111)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-3-3.db.example.com', 107)
                           )
                         }),
                       plan_id='plan3.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='A',
                    name='plan2.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan4.db.example.com',
                    value=('192.0.2.2', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan4.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan4.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan2.db.example.com',
                    value=('lb-3-2.db.example.com', 111)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan4.db.example.com',
                    value=('lb-2-4.db.example.com', 109)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan4.db.example.com',
                    value=('lb-3-4.db.example.com', 119)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan2.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('deployer-c', 2)
                  )
                })
[State 9]
  deployer_next_plan: Map(
                        'deployer-a' -> 0,
                        'deployer-b' -> 0,
                        'deployer-c' -> 3
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-c', 3)
                         ),
                       rollback='plan4.db.example.com',
                       root='plan3.db.example.com'
                     )
                 )
  ghost_action: Deploy(
                  Record(
                    deployer='deployer-c',
                    new_epoch=3,
                    new_root='plan3.db.example.com',
                    plan_id='plan3.db.example.com',
                    previous_root='plan4.db.example.com',
                    rollback='plan4.db.example.com'
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-3-2.db.example.com', 111)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-2-4.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-3-4.db.example.com', 119)
                           )
                         }),
                       plan_id='plan4.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-1-3.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-2-3.db.example.com', 111)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-3-3.db.example.com', 107)
                           )
                         }),
                       plan_id='plan3.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='A',
                    name='plan2.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan3.db.example.com',
                    value=('192.0.2.1', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan3.db.example.com',
                    value=('192.0.2.2', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan3.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan4.db.example.com',
                    value=('192.0.2.2', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan4.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan3.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan2.db.example.com',
                    value=('lb-3-2.db.example.com', 111)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan3.db.example.com',
                    value=('lb-1-3.db.example.com', 109)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan3.db.example.com',
                    value=('lb-2-3.db.example.com', 111)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan3.db.example.com',
                    value=('lb-3-3.db.example.com', 107)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan4.db.example.com',
                    value=('lb-2-4.db.example.com', 109)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan4.db.example.com',
                    value=('lb-3-4.db.example.com', 119)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan4.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('deployer-c', 3)
                  )
                })
[State 10]
  deployer_next_plan: Map(
                        'deployer-a' -> 0,
                        'deployer-b' -> 0,
                        'deployer-c' -> 3
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-c', 3)
                         ),
                       rollback='plan4.db.example.com',
                       root='plan3.db.example.com'
                     )
                 )
  ghost_action: GeneratePlan(
                  Record(
                    ips=Set({'192.0.2.2', '192.0.2.3'}),
                    plan_id='plan0.db.example.com',
                    weights=Map('192.0.2.2' -> 113, '192.0.2.3' -> 113)
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-3-2.db.example.com', 111)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-2-4.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-3-4.db.example.com', 119)
                           )
                         }),
                       plan_id='plan4.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-1-3.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-2-3.db.example.com', 111)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-3-3.db.example.com', 107)
                           )
                         }),
                       plan_id='plan3.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan0.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan0.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan0.db.example.com',
                             value=('lb-2-0.db.example.com', 113)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan0.db.example.com',
                             value=('lb-3-0.db.example.com', 113)
                           )
                         }),
                       plan_id='plan0.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='A',
                    name='plan2.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan3.db.example.com',
                    value=('192.0.2.1', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan3.db.example.com',
                    value=('192.0.2.2', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan3.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan4.db.example.com',
                    value=('192.0.2.2', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan4.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan3.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan2.db.example.com',
                    value=('lb-3-2.db.example.com', 111)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan3.db.example.com',
                    value=('lb-1-3.db.example.com', 109)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan3.db.example.com',
                    value=('lb-2-3.db.example.com', 111)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan3.db.example.com',
                    value=('lb-3-3.db.example.com', 107)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan4.db.example.com',
                    value=('lb-2-4.db.example.com', 109)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan4.db.example.com',
                    value=('lb-3-4.db.example.com', 119)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan4.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('deployer-c', 3)
                  )
                })
[State 11]
  deployer_next_plan: Map(
                        'deployer-a' -> 0,
                        'deployer-b' -> 0,
                        'deployer-c' -> 3
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-c', 3)
                         ),
                       rollback='plan4.db.example.com',
                       root='plan3.db.example.com'
                     )
                 )
  ghost_action: Backoff(
                  Record(
                    deployer='deployer-a',
                    lock=Record(
                        kind='TXT',
                        name='lock.example.com',
                        value=('genesis', 0)
                      )
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-3-2.db.example.com', 111)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-2-4.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-3-4.db.example.com', 119)
                           )
                         }),
                       plan_id='plan4.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-1-3.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-2-3.db.example.com', 111)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-3-3.db.example.com', 107)
                           )
                         }),
                       plan_id='plan3.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan0.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan0.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan0.db.example.com',
                             value=('lb-2-0.db.example.com', 113)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan0.db.example.com',
                             value=('lb-3-0.db.example.com', 113)
                           )
                         }),
                       plan_id='plan0.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='A',
                    name='plan2.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan3.db.example.com',
                    value=('192.0.2.1', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan3.db.example.com',
                    value=('192.0.2.2', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan3.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan4.db.example.com',
                    value=('192.0.2.2', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan4.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan3.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan2.db.example.com',
                    value=('lb-3-2.db.example.com', 111)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan3.db.example.com',
                    value=('lb-1-3.db.example.com', 109)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan3.db.example.com',
                    value=('lb-2-3.db.example.com', 111)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan3.db.example.com',
                    value=('lb-3-3.db.example.com', 107)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan4.db.example.com',
                    value=('lb-2-4.db.example.com', 109)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan4.db.example.com',
                    value=('lb-3-4.db.example.com', 119)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan4.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('deployer-c', 3)
                  )
                })
[State 12]
  deployer_next_plan: Map(
                        'deployer-a' -> 0,
                        'deployer-b' -> 0,
                        'deployer-c' -> 4
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-c', 4)
                         ),
                       rollback='plan3.db.example.com',
                       root='plan0.db.example.com'
                     )
                 )
  ghost_action: Deploy(
                  Record(
                    deployer='deployer-c',
                    new_epoch=4,
                    new_root='plan0.db.example.com',
                    plan_id='plan0.db.example.com',
                    previous_root='plan3.db.example.com',
                    rollback='plan3.db.example.com'
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-3-2.db.example.com', 111)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-2-4.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-3-4.db.example.com', 119)
                           )
                         }),
                       plan_id='plan4.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-1-3.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-2-3.db.example.com', 111)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-3-3.db.example.com', 107)
                           )
                         }),
                       plan_id='plan3.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan0.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan0.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan0.db.example.com',
                             value=('lb-2-0.db.example.com', 113)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan0.db.example.com',
                             value=('lb-3-0.db.example.com', 113)
                           )
                         }),
                       plan_id='plan0.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='A',
                    name='plan0.db.example.com',
                    value=('192.0.2.2', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan0.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan2.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan3.db.example.com',
                    value=('192.0.2.1', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan3.db.example.com',
                    value=('192.0.2.2', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan3.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan4.db.example.com',
                    value=('192.0.2.2', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan4.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan0.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan0.db.example.com',
                    value=('lb-2-0.db.example.com', 113)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan0.db.example.com',
                    value=('lb-3-0.db.example.com', 113)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan2.db.example.com',
                    value=('lb-3-2.db.example.com', 111)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan3.db.example.com',
                    value=('lb-1-3.db.example.com', 109)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan3.db.example.com',
                    value=('lb-2-3.db.example.com', 111)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan3.db.example.com',
                    value=('lb-3-3.db.example.com', 107)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan4.db.example.com',
                    value=('lb-2-4.db.example.com', 109)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan4.db.example.com',
                    value=('lb-3-4.db.example.com', 119)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan3.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('deployer-c', 4)
                  )
                })
[State 13]
  deployer_next_plan: Map(
                        'deployer-a' -> 0,
                        'deployer-b' -> 0,
                        'deployer-c' -> 4
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-c', 4)
                         ),
                       rollback='plan3.db.example.com',
                       root='plan0.db.example.com'
                     )
                 )
  ghost_action: Backoff(
                  Record(
                    deployer='deployer-a',
                    lock=Record(
                        kind='TXT',
                        name='lock.example.com',
                        value=('genesis', 0)
                      )
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-3-2.db.example.com', 111)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-2-4.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-3-4.db.example.com', 119)
                           )
                         }),
                       plan_id='plan4.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-1-3.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-2-3.db.example.com', 111)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-3-3.db.example.com', 107)
                           )
                         }),
                       plan_id='plan3.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan0.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan0.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan0.db.example.com',
                             value=('lb-2-0.db.example.com', 113)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan0.db.example.com',
                             value=('lb-3-0.db.example.com', 113)
                           )
                         }),
                       plan_id='plan0.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='A',
                    name='plan0.db.example.com',
                    value=('192.0.2.2', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan0.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan2.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan3.db.example.com',
                    value=('192.0.2.1', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan3.db.example.com',
                    value=('192.0.2.2', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan3.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan4.db.example.com',
                    value=('192.0.2.2', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan4.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan0.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan0.db.example.com',
                    value=('lb-2-0.db.example.com', 113)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan0.db.example.com',
                    value=('lb-3-0.db.example.com', 113)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan2.db.example.com',
                    value=('lb-3-2.db.example.com', 111)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan3.db.example.com',
                    value=('lb-1-3.db.example.com', 109)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan3.db.example.com',
                    value=('lb-2-3.db.example.com', 111)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan3.db.example.com',
                    value=('lb-3-3.db.example.com', 107)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan4.db.example.com',
                    value=('lb-2-4.db.example.com', 109)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan4.db.example.com',
                    value=('lb-3-4.db.example.com', 119)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan3.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('deployer-c', 4)
                  )
                })
[State 14]
  deployer_next_plan: Map(
                        'deployer-a' -> 0,
                        'deployer-b' -> 0,
                        'deployer-c' -> 4
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-c', 4)
                         ),
                       rollback='plan3.db.example.com',
                       root='plan0.db.example.com'
                     )
                 )
  ghost_action: Sync(
                  Record(
                    deployer='deployer-c',
                    lock=Record(
                        kind='TXT',
                        name='lock.example.com',
                        value=('deployer-c', 4)
                      ),
                    rollback='plan3.db.example.com',
                    root='plan0.db.example.com'
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-3-2.db.example.com', 111)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-2-4.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-3-4.db.example.com', 119)
                           )
                         }),
                       plan_id='plan4.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-1-3.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-2-3.db.example.com', 111)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-3-3.db.example.com', 107)
                           )
                         }),
                       plan_id='plan3.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan0.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan0.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan0.db.example.com',
                             value=('lb-2-0.db.example.com', 113)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan0.db.example.com',
                             value=('lb-3-0.db.example.com', 113)
                           )
                         }),
                       plan_id='plan0.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='A',
                    name='plan0.db.example.com',
                    value=('192.0.2.2', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan0.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan2.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan3.db.example.com',
                    value=('192.0.2.1', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan3.db.example.com',
                    value=('192.0.2.2', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan3.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan4.db.example.com',
                    value=('192.0.2.2', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan4.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan0.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan0.db.example.com',
                    value=('lb-2-0.db.example.com', 113)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan0.db.example.com',
                    value=('lb-3-0.db.example.com', 113)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan2.db.example.com',
                    value=('lb-3-2.db.example.com', 111)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan3.db.example.com',
                    value=('lb-1-3.db.example.com', 109)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan3.db.example.com',
                    value=('lb-2-3.db.example.com', 111)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan3.db.example.com',
                    value=('lb-3-3.db.example.com', 107)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan4.db.example.com',
                    value=('lb-2-4.db.example.com', 109)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan4.db.example.com',
                    value=('lb-3-4.db.example.com', 119)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan3.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('deployer-c', 4)
                  )
                })
[State 15]
  deployer_next_plan: Map(
                        'deployer-a' -> 0,
                        'deployer-b' -> 0,
                        'deployer-c' -> 4
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-c', 4)
                         ),
                       rollback='plan3.db.example.com',
                       root='plan0.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-c', 4)
                         ),
                       rollback='plan3.db.example.com',
                       root='plan0.db.example.com'
                     )
                 )
  ghost_action: Sync(
                  Record(
                    deployer='deployer-b',
                    lock=Record(
                        kind='TXT',
                        name='lock.example.com',
                        value=('deployer-c', 4)
                      ),
                    rollback='plan3.db.example.com',
                    root='plan0.db.example.com'
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-3-2.db.example.com', 111)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-2-4.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-3-4.db.example.com', 119)
                           )
                         }),
                       plan_id='plan4.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-1-3.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-2-3.db.example.com', 111)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-3-3.db.example.com', 107)
                           )
                         }),
                       plan_id='plan3.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan0.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan0.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan0.db.example.com',
                             value=('lb-2-0.db.example.com', 113)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan0.db.example.com',
                             value=('lb-3-0.db.example.com', 113)
                           )
                         }),
                       plan_id='plan0.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='A',
                    name='plan0.db.example.com',
                    value=('192.0.2.2', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan0.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan2.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan3.db.example.com',
                    value=('192.0.2.1', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan3.db.example.com',
                    value=('192.0.2.2', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan3.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan4.db.example.com',
                    value=('192.0.2.2', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan4.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan0.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan0.db.example.com',
                    value=('lb-2-0.db.example.com', 113)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan0.db.example.com',
                    value=('lb-3-0.db.example.com', 113)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan2.db.example.com',
                    value=('lb-3-2.db.example.com', 111)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan3.db.example.com',
                    value=('lb-1-3.db.example.com', 109)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan3.db.example.com',
                    value=('lb-2-3.db.example.com', 111)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan3.db.example.com',
                    value=('lb-3-3.db.example.com', 107)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan4.db.example.com',
                    value=('lb-2-4.db.example.com', 109)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan4.db.example.com',
                    value=('lb-3-4.db.example.com', 119)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan3.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('deployer-c', 4)
                  )
                })
[State 16]
  deployer_next_plan: Map(
                        'deployer-a' -> 0,
                        'deployer-b' -> 1,
                        'deployer-c' -> 4
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-b', 5)
                         ),
                       rollback='plan0.db.example.com',
                       root='plan2.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-c', 4)
                         ),
                       rollback='plan3.db.example.com',
                       root='plan0.db.example.com'
                     )
                 )
  ghost_action: Deploy(
                  Record(
                    deployer='deployer-b',
                    new_epoch=5,
                    new_root='plan2.db.example.com',
                    plan_id='plan2.db.example.com',
                    previous_root='plan0.db.example.com',
                    rollback='plan0.db.example.com'
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-3-2.db.example.com', 111)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-2-4.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-3-4.db.example.com', 119)
                           )
                         }),
                       plan_id='plan4.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-1-3.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-2-3.db.example.com', 111)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-3-3.db.example.com', 107)
                           )
                         }),
                       plan_id='plan3.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan0.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan0.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan0.db.example.com',
                             value=('lb-2-0.db.example.com', 113)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan0.db.example.com',
                             value=('lb-3-0.db.example.com', 113)
                           )
                         }),
                       plan_id='plan0.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='A',
                    name='plan0.db.example.com',
                    value=('192.0.2.2', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan0.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan2.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan3.db.example.com',
                    value=('192.0.2.1', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan3.db.example.com',
                    value=('192.0.2.2', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan3.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan4.db.example.com',
                    value=('192.0.2.2', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan4.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan2.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan0.db.example.com',
                    value=('lb-2-0.db.example.com', 113)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan0.db.example.com',
                    value=('lb-3-0.db.example.com', 113)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan2.db.example.com',
                    value=('lb-3-2.db.example.com', 111)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan3.db.example.com',
                    value=('lb-1-3.db.example.com', 109)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan3.db.example.com',
                    value=('lb-2-3.db.example.com', 111)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan3.db.example.com',
                    value=('lb-3-3.db.example.com', 107)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan4.db.example.com',
                    value=('lb-2-4.db.example.com', 109)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan4.db.example.com',
                    value=('lb-3-4.db.example.com', 119)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan0.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('deployer-b', 5)
                  )
                })
[State 17]
  deployer_next_plan: Map(
                        'deployer-a' -> 0,
                        'deployer-b' -> 1,
                        'deployer-c' -> 4
                      )
  deployer_view: Map(
                   'deployer-a' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('genesis', 0)
                         ),
                       rollback='plan-init.db.example.com',
                       root='plan-init.db.example.com'
                     ),
                   'deployer-b' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-b', 5)
                         ),
                       rollback='plan0.db.example.com',
                       root='plan2.db.example.com'
                     ),
                   'deployer-c' ->
                     Record(
                       lock=Record(
                           kind='TXT',
                           name='lock.example.com',
                           value=('deployer-c', 4)
                         ),
                       rollback='plan3.db.example.com',
                       root='plan0.db.example.com'
                     )
                 )
  ghost_action: Cleanup(
                  Record(
                    deployer='deployer-c',
                    next_plan=4,
                    old_indices=filter(Set({0, 1, 2, 3}))
                  )
                )
  planner_updates: [
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan2.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan2.db.example.com',
                             value=('lb-3-2.db.example.com', 111)
                           )
                         }),
                       plan_id='plan2.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan4.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-2-4.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan4.db.example.com',
                             value=('lb-3-4.db.example.com', 119)
                           )
                         }),
                       plan_id='plan4.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.1', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan3.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-1-3.db.example.com', 109)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-2-3.db.example.com', 111)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan3.db.example.com',
                             value=('lb-3-3.db.example.com', 107)
                           )
                         }),
                       plan_id='plan3.db.example.com'
                     ),
                     Record(
                       creates=Set({
                           Record(
                             kind='A',
                             name='plan0.db.example.com',
                             value=('192.0.2.2', 1)
                           ),
                           Record(
                             kind='A',
                             name='plan0.db.example.com',
                             value=('192.0.2.3', 1)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan0.db.example.com',
                             value=('lb-2-0.db.example.com', 113)
                           ),
                           Record(
                             kind='CNAME',
                             name='plan0.db.example.com',
                             value=('lb-3-0.db.example.com', 113)
                           )
                         }),
                       plan_id='plan0.db.example.com'
                     )
                   ]
  zone_records: Set({
                  Record(
                    kind='A',
                    name='plan0.db.example.com',
                    value=('192.0.2.2', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan0.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan3.db.example.com',
                    value=('192.0.2.1', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan3.db.example.com',
                    value=('192.0.2.2', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan3.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan4.db.example.com',
                    value=('192.0.2.2', 1)
                  ),
                  Record(
                    kind='A',
                    name='plan4.db.example.com',
                    value=('192.0.2.3', 1)
                  ),
                  Record(
                    kind='CNAME',
                    name='db.us-east-1.example.com',
                    value=('plan2.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan-init.db.example.com',
                    value=('lb-1-init.db.example.com', 100)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan0.db.example.com',
                    value=('lb-2-0.db.example.com', 113)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan0.db.example.com',
                    value=('lb-3-0.db.example.com', 113)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan3.db.example.com',
                    value=('lb-1-3.db.example.com', 109)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan3.db.example.com',
                    value=('lb-2-3.db.example.com', 111)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan3.db.example.com',
                    value=('lb-3-3.db.example.com', 107)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan4.db.example.com',
                    value=('lb-2-4.db.example.com', 109)
                  ),
                  Record(
                    kind='CNAME',
                    name='plan4.db.example.com',
                    value=('lb-3-4.db.example.com', 119)
                  ),
                  Record(
                    kind='CNAME',
                    name='rollback.db.example.com',
                    value=('plan0.db.example.com', 1)
                  ),
                  Record(
                    kind='TXT',
                    name='lock.example.com',
                    value=('deployer-b', 5)
                  )
                })
Replay with: wunderspec replay --instance n3_5_3 --property no_inconsistent_root --max-steps 20 dns_balancer.py --seed 5259027364429190200
```
</details>

### 4.4. Replay the trace

The last command gave us a hint about replay the trace without doing the search
again:

```sh
uv run wunderspec replay --instance n3_5_3 --property no_inconsistent_root \
  --max-steps 20 dns_balancer.py --seed 5259027364429190200 || test $? -eq 1
```

We use this command to save the trace in machine-readable JSON:

```sh
uv run wunderspec replay --instance n3_5_3 --property no_inconsistent_root \
  --max-steps 20 dns_balancer.py --seed 5259027364429190200 --out-itf=t.itf.json || test $? -eq 1
```

<!--pytest-codeblocks:expected-output-->
```text
info: Wrote ITF trace to t.itf.json
Invariant violation at state 17
```

Inspect `t.itf.json` with `jq <t.itf.json`. Obviously, it is not meant for
humans to read.

Since this format is designed for easy parsing, we ask an AI tool to generate a
visualizer for the traces that are generated from the specification:

```sh
./visualize_dns_trace.py t.itf.json
```

<!--pytest-codeblocks:expected-output-->
```text
Wrote t.itf.trace.html
```

Open it in your browser and replay the trace:

<!--pytest.mark.skip-->
```
open t.itf.trace.html
```

**This approach enables model-based testing! We talk about it later.**

### 4.5. Checking a larger instance

Having the cleanup window of 3 is probably too tight. What if we take
a more realistic instance of the cleanup window of 20?

```sh
uv run wunderspec run dns_balancer.py \
  --instance n3_30_20 --seed=123 --max-samples=1000 --max-steps=50 \
  --property no_inconsistent_root
```

<!--pytest-codeblocks:expected-output-->
```text
info: Seed: 123
Rerun the search with: wunderspec run --seed=123 --instance n3_30_20 --property no_inconsistent_root --max-steps 50 dns_balancer.py
success: No invariant violations in 1000 samples
```

We can bump `--max-samples` to higher values, but the chances of finding a
violation there are quite slim. There are many reasons for that. One of them is
using uniform random sampling.

We can also give the simulator a bigger step budget, e.g., by increasing
`--max-steps` to 500. Try it!

## 5. Enumerating states

Instead of randomly firing events, we can enumerate states systematically.
**Check the DFS slide!**

### 5.1. Model checking the small instance

```sh
uv run wunderspec check dns_balancer.py --instance n3_5_3 \
  --property no_inconsistent_root --seed=123 --no-progress || test $? -eq 1
```

### 5.2. Model checking the large instance

**Step 1.** Run the model checker:

```sh
uv run wunderspec check dns_balancer.py --instance n3_30_20 \
  --property no_inconsistent_root --seed=123 --no-progress --timeout=15 || test $? -eq 1
```

Here we are lucky. Our DFS search randomizes the choice of successors and we hit
a violation very quickly. With other seeds, the search may end up looking for
violations for hours.

**Step 2.** Again, we use `wunderspec replay` to convert the trace to
`t.itf.json` and run `visualize_dns_trace.py` to produce a new visualization. We
do not give precise commands here, as the schedule name changes in the output.

## 6. Check other commands

We stop here. If you are curious, look at `wunderspec with-tlc` and `wunderspec
with-apalache`. These commands call two model checkers for TLA<sup>+</sup>: TLC
and [Apalache][]. Notably, these commands remove a lot of boilerplate related to
these tools.

[TLC]: https://github.com/tlaplus/tlaplus/
[Apalache]: https://apalache-mc.org/
