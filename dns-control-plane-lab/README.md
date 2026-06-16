# ACME Cloud DNS Control Plane Lab

This is a prompted implementation of **ACME Cloud**, generated with **gpt-5.5**.

The lab models a single ACME region: **us-east-1**.

The lab has three conceptual services:

- **CloudDB** — the load-balanced customer-facing service. CloudDB itself is **not implemented**; it is represented only by the DNS name `clouddb.us-east-1.api.acme` and fake load-balancer IPs.
- **Wormhole53** — a lab DNS service used to resolve the CloudDB name. It stores DNS records, resolves names, and applies transactional `DnsBatchChange` updates to a persisted DNS hosted zone.
- **DNS control plane** — the part we actually care about. It generates plans, has three autonomous deployers apply those plans, runs deployer cleanup, and updates Wormhole53.

Persistence is implemented on disk. The `s3-persistence/` directory mimics a tiny S3 bucket containing generated plans and the persisted Wormhole53 DNS zone.

CloudDB load balancing is represented as a Wormhole53 DNS tree:

```text
clouddb.us-east-1.api.acme
  └─ ALIAS plan-004.cdb.acme
       ├─ ALIAS lb-004-1.cdb.acme  (weight=103)
       │    └─ A 192.0.4.1
       ├─ ALIAS lb-004-2.cdb.acme  (weight=97)
       │    └─ A 192.0.4.2
       └─ ALIAS lb-004-3.cdb.acme  (weight=115)
            └─ A 192.0.4.3
```

The DNS control plane is the system under test. A planner creates immutable JSON files describing the intended DNS tree from a list of load balancer plan entries. In the autonomous workshop simulation, planner work mimics growing load by increasing the number of load balancers over time and assigning random weights. Three deployers run for redundancy; each independently polls for plans and tries to enact them in Wormhole53 DNS by installing plan records, flipping the stable CloudDB root alias, and updating rollback metadata. In the autonomous loop, a deployer runs a separate cleanup pass after a successful install.

```text
                 DNS control plane

              planner
                │ writes immutable plans
                ▼
        s3-persistence/plans
                │ polled independently
       ┌────────┼────────┐
       ▼        ▼        ▼
   deployer-a deployer-b deployer-c
       │        │        │
       └────────┼────────┘
                │ batch updates, then cleanup
                ▼
       Wormhole53 hosted zone
                │ resolve
                ▼
 clouddb.us-east-1.api.acme → load balancer IPs

 CloudDB service implementation: intentionally absent
```

## Make targets

```bash
make run    # run the workshop app on http://localhost:8000
make test   # run tests
make clean  # remove generated local state
```

`make run` serves an HTML control plane at:

```text
http://localhost:8000/
```

## Cloud API endpoints

Public ACME Cloud / Wormhole53 API:

- `GET /`
- `GET /health`
- `GET /wormhole53/resolve/{name}`

MBT workshop harness API:

- `POST /mbt/reset`
- `POST /mbt/planner/generate`
- `POST /mbt/deployers/{name}/sync`
- `POST /mbt/deployers/{name}/deploy`
- `POST /mbt/deployers/{name}/cleanup`
