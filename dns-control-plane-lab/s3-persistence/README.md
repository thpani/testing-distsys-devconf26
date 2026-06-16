# S3 Persistence

This directory mimics a tiny S3 bucket used by the lab control plane.

Runtime files written here:

- `current_dns_zone.json` — persisted Wormhole53 hosted-zone records
- `plans/plan-*.json` — immutable generated deployment plans

These files are generated at runtime and ignored by git. The README and `.gitkeep` keep the bucket-shaped directory visible in the workshop repo.
