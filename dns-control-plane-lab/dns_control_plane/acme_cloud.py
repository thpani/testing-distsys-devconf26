from __future__ import annotations

import asyncio
import html
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .constants import DEPLOYERS, DNS_CLOUDDB_LOCK_NAME, DNS_CLOUDDB_ROLLBACK_NAME, DNS_CLOUDDB_ROOT_NAME
from .deployer import Deployer, deployer_loop
from .planner import Planner, planner_loop
from .wormhole53 import Wormhole53Store

BASE_DIR = Path(os.environ.get("DNS_LAB_BASE_DIR", Path(__file__).resolve().parent.parent))
S3_PERSISTENCE_DIR = BASE_DIR / "s3-persistence"

wormhole53 = Wormhole53Store(S3_PERSISTENCE_DIR / "current_dns_zone.json")
planner = Planner(S3_PERSISTENCE_DIR / "plans")
deployers = {name: Deployer(name, wormhole53, planner) for name in DEPLOYERS}
_tasks: list[asyncio.Task] = []


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    if os.environ.get("DNS_LAB_DISABLE_BACKGROUND", "0") != "1":
        _tasks.append(asyncio.create_task(planner_loop(planner)))
        for name in DEPLOYERS:
            _tasks.append(asyncio.create_task(deployer_loop(deployers[name])))
    try:
        yield
    finally:
        for task in _tasks:
            task.cancel()
        if _tasks:
            await asyncio.gather(*_tasks, return_exceptions=True)
        _tasks.clear()


app = FastAPI(title="ACME Cloud DNS Control Plane Lab", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Public-facing API
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict:
    ips = wormhole53.resolve(DNS_CLOUDDB_ROOT_NAME)
    return {"ok": bool(ips), "name": DNS_CLOUDDB_ROOT_NAME, "ips": ips}


@app.get("/wormhole53/resolve/{name}")
def wormhole53_resolve(name: str) -> dict:
    ips = wormhole53.resolve(name)
    return {"name": name, "ips": ips}


# ----------------------------------------------------------------------------
# HTML frontend
# ----------------------------------------------------------------------------


def _record_value_html(value: object) -> str:
    if isinstance(value, list):
        targets = []
        for target in value:
            targets.append(f"{html.escape(target['name'])} <small>weight={target['weight']}</small>")
        return "<br>".join(targets)
    return html.escape(str(value))


def _resolver_tree_html(name: str, visited: set[str] | None = None, weight: int | None = None) -> str:
    visited = visited or set()
    escaped_name = html.escape(name)
    weight_suffix = f' <span class="edge">(weight={weight})</span>' if weight is not None else ""
    if name in visited:
        return f'<li><code>{escaped_name}</code>{weight_suffix} <span class="broken">cycle</span></li>'
    visited.add(name)

    arec = wormhole53.get(name, "A")
    if arec and isinstance(arec.value, str):
        return f'<li><code>{escaped_name}</code> <span class="record-type">A</span> {html.escape(arec.value)}{weight_suffix}</li>'

    alias = wormhole53.get(name, "ALIAS")
    if not alias:
        return f'<li><code>{escaped_name}</code>{weight_suffix} <span class="broken">missing</span></li>'

    if isinstance(alias.value, str):
        return f'<li><code>{escaped_name}</code>{weight_suffix} <span class="record-type">ALIAS</span><ul>{_resolver_tree_html(alias.value, visited)}</ul></li>'

    branches = []
    for target in alias.value:
        branches.append(_resolver_tree_html(target.name, set(visited), weight=target.weight))
    return f'<li><code>{escaped_name}</code>{weight_suffix} <span class="record-type">ALIAS</span><ul>{"".join(branches)}</ul></li>'


@app.get("/", response_class=HTMLResponse)
def dns_layout() -> str:
    records = sorted(wormhole53._internal__list_records(), key=lambda r: (r.name, r.type))
    root_health = health()
    root_ips = root_health["ips"]
    rows = "".join(
        f"<tr><td>{html.escape(record.name)}</td><td>{record.type}</td><td>{_record_value_html(record.model_dump(mode='json')['value'])}</td></tr>"
        for record in records
    )
    if not rows:
        rows = '<tr><td colspan="3"><em>No DNS records installed yet.</em></td></tr>'

    root = wormhole53.get(DNS_CLOUDDB_ROOT_NAME, "ALIAS")
    rollback = wormhole53.get(DNS_CLOUDDB_ROLLBACK_NAME, "ALIAS")
    lock = wormhole53.get(DNS_CLOUDDB_LOCK_NAME, "TXT")

    def value(record: object) -> str:
        if record is None:
            return "<em>missing</em>"
        return _record_value_html(record.model_dump(mode="json")["value"])

    resolver_tree = _resolver_tree_html(DNS_CLOUDDB_ROOT_NAME)
    status_class = "healthy" if root_health["ok"] else "broken"
    status_text = "healthy" if root_health["ok"] else "BROKEN: root resolves to zero IPs"
    return f"""
<!doctype html>
<html>
<head>
  <title>ACME CloudDB DNS Control Plane</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1f2937; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
    th, td {{ border: 1px solid #d1d5db; padding: 0.5rem; text-align: left; vertical-align: top; }}
    th {{ background: #f3f4f6; }}
    code {{ background: #f3f4f6; padding: 0.1rem 0.25rem; border-radius: 0.25rem; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr)); gap: 0.5rem; }}
    .card {{ border: 1px solid #d1d5db; border-radius: 0.5rem; padding: 0.6rem 0.75rem; }}
    .card h2 {{ font-size: 1rem; margin: 0 0 0.35rem 0; }}
    .card p {{ margin: 0.25rem 0; }}
    .healthy {{ color: #047857; font-weight: 700; }}
    .broken {{ color: #b91c1c; font-weight: 700; }}
    .record-type, .edge {{ color: #6b7280; font-size: 0.875rem; }}
    .tree {{ border: 1px solid #d1d5db; border-radius: 0.5rem; padding: 1rem; background: #fafafa; }}
    .tree ul {{ margin: 0.25rem 0 0.25rem 1.25rem; padding-left: 1rem; }}
    .tree li {{ margin: 0.25rem 0; }}
    small {{ color: #6b7280; }}
    button {{ border: 1px solid #d1d5db; border-radius: 0.35rem; background: #fff; padding: 0.35rem 0.6rem; cursor: pointer; }}
  </style>
  <script>
    let refreshPaused = false;
    function setRefreshButton() {{
      const button = document.getElementById('refresh-toggle');
      if (button) button.textContent = refreshPaused ? 'Resume refresh' : 'Pause refresh';
    }}
    function toggleRefresh() {{
      refreshPaused = !refreshPaused;
      setRefreshButton();
    }}
    window.addEventListener('load', () => {{
      setRefreshButton();
      setInterval(() => {{ if (!refreshPaused) window.location.reload(); }}, 2000);
    }});
  </script>
</head>
<body>
  <h1>ACME CloudDB DNS Control Plane</h1>
  <p>
    Auto-refreshes every 2 seconds.
    <button id="refresh-toggle" type="button" onclick="toggleRefresh()">Pause refresh</button>
    Public resolver endpoint: <code>/wormhole53/resolve/{{name}}</code>.
  </p>

  <div class="cards">
    <div class="card"><h2>Root</h2><p><code>{html.escape(DNS_CLOUDDB_ROOT_NAME)}</code></p><p>{value(root)}</p></div>
    <div class="card"><h2>Rollback</h2><p><code>{html.escape(DNS_CLOUDDB_ROLLBACK_NAME)}</code></p><p>{value(rollback)}</p></div>
    <div class="card"><h2>Lock</h2><p><code>{html.escape(DNS_CLOUDDB_LOCK_NAME)}</code></p><p>{value(lock)}</p></div>
    <div class="card"><h2>Resolution</h2><p class="{status_class}">{status_text}</p><p>{html.escape(', '.join(root_ips) or '[]')}</p></div>
  </div>

  <h2>Current Wormhole53 records</h2>
  <h3>Resolver tree from root</h3>
  <div class="tree"><ul>{resolver_tree}</ul></div>

  <h3>Raw records</h3>
  <table>
    <thead><tr><th>Name</th><th>Type</th><th>Value</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</body>
</html>
"""
