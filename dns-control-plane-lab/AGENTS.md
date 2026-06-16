# Agent instructions

This directory contains a realistic DNS cloud control-plane lab system.

## Project context

- The prompted system description is in `PROMPT.md`.
- The lab service README is in `README.md`.
- The important control-plane modules are:
  - `dns_control_plane/wormhole53.py`
  - `dns_control_plane/planner.py`
  - `dns_control_plane/deployer.py`

## Code conventions

- This is a workshop/model-based-testing target. Keep the system small, readable, and lab-friendly.
- Do **not** fix the latent race/outage bug unless explicitly asked.
- cloud-internal routes may use internal methods like `_internal__list_records()`; public APIs should remain minimal.

## Documentation sync

When changing implementation behavior, endpoint shape, persistence layout, workshop invariants, or running/testing instructions, keep these documents in sync:

- `README.md`
- `s3-persistence/README.md`
- `PROMPT.md`

Do not leave code and workshop documentation describing different behavior.

## Testing and dependencies

- This lab is a uv project and is also included in the repository-level uv workspace.
- The lab's development tools live in the default `dev` dependency group in `pyproject.toml`; do not add back a `dev` extra just to run tests.
- From this directory, run tests with:

  ```bash
  make test
  ```
  or, if make is unavailable:

  ```bash
  uv run python -m pytest -q
  ```

- `uv run` will create/sync the virtual environment automatically. When the repository-level workspace is present, uv may use the top-level `.venv`; that is expected.
- Use `httpx2` for FastAPI/Starlette test clients to avoid the `httpx` deprecation warning. Test code can import it as:

  ```python
  import httpx2 as httpx
  ```

- Do not add `requests` unless code actually imports it.
- Generated packaging metadata such as `*.egg-info/` should not be committed.

## Git hygiene

- Make regular commits with clear messages.
- Commit only relevant tracked project changes.
- Leave unrelated untracked workspace files alone unless explicitly asked.
