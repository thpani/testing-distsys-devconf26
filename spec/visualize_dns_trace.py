#!/usr/bin/env python3
"""Generate an SVG/HTML animation for dns_balancer.py WunderSpec ITF traces."""

from __future__ import annotations

import argparse
import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_ROOT_NAME = "db.us-east-1.example.com"
DEFAULT_ROLLBACK_NAME = "rollback.db.example.com"


@dataclass(frozen=True)
class DnsRecord:
    kind: str
    name: str
    target: str
    weight: int

    def diff_key(self, entry_names: set[str]) -> tuple[str, str, str]:
        if self.kind == "TXT":
            return (self.kind, self.name, "lock")
        if self.kind == "CNAME":
            if self.name in entry_names:
                return (self.kind, self.name, "entry")
            return (self.kind, self.name, self.target)
        return (self.kind, self.name, self.target)

    @property
    def canonical(self) -> tuple[str, str, str, int]:
        return (self.kind, self.name, self.target, self.weight)

    def label(self) -> str:
        if self.kind == "CNAME":
            return f"CNAME {short_name(self.name)} -> {short_name(self.target)} (w={self.weight})"
        if self.kind == "A":
            return f"A {short_name(self.name)} -> {self.target}"
        if self.kind == "TXT":
            return f"TXT {short_name(self.name)} = {self.target}/{self.weight}"
        return f"{self.kind} {short_name(self.name)} -> {self.target}"


def unwrap(value: Any) -> Any:
    if isinstance(value, dict):
        if "#bigint" in value:
            return int(value["#bigint"])
        if "#tup" in value:
            return tuple(unwrap(item) for item in value["#tup"])
        if "#set" in value:
            return [unwrap(item) for item in value["#set"]]
        if "#map" in value:
            return [(unwrap(key), unwrap(val)) for key, val in value["#map"]]
        return {key: unwrap(val) for key, val in value.items()}
    if isinstance(value, list):
        return [unwrap(item) for item in value]
    return value


def short_name(value: str) -> str:
    return (
        value.replace(".db.example.com", ".ddb")
        .replace(".example.com", "")
        .replace("db.us-east-1", "db.us-east-1")
    )


def record_from_itf(raw: dict[str, Any]) -> DnsRecord:
    target, weight = unwrap(raw["value"])
    return DnsRecord(
        kind=str(raw["kind"]),
        name=str(raw["name"]),
        target=str(target),
        weight=int(weight),
    )


def normalize_records(state: dict[str, Any]) -> list[DnsRecord]:
    records = [record_from_itf(record) for record in state["zone_records"]["#set"]]
    return sorted(records, key=lambda rec: rec.canonical)


def balancer_ip_map(state: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, balancer in unwrap(state.get("BALANCER_NAMES", {"#map": []})):
        if isinstance(key, tuple) and len(key) == 2:
            _plan, ip = key
            result[str(balancer)] = str(ip)
    return result


def diff_records(
    previous: list[DnsRecord] | None,
    current: list[DnsRecord],
    entry_names: set[str],
) -> dict[str, list[str]]:
    if previous is None:
        return {
            "added": [record.label() for record in current],
            "removed": [],
            "changed": [],
        }

    old = {record.diff_key(entry_names): record for record in previous}
    new = {record.diff_key(entry_names): record for record in current}
    added = [new[key].label() for key in sorted(new.keys() - old.keys())]
    removed = [old[key].label() for key in sorted(old.keys() - new.keys())]
    changed = [
        f"{old[key].label()} -> {new[key].label()}"
        for key in sorted(old.keys() & new.keys())
        if old[key].canonical != new[key].canonical
    ]
    return {"added": added, "removed": removed, "changed": changed}


def entry_target(records: list[DnsRecord], entry_name: str) -> tuple[str | None, int | None]:
    matches = [record for record in records if record.kind == "CNAME" and record.name == entry_name]
    if not matches:
        return None, None
    return matches[0].target, matches[0].weight


def child_edges(records: list[DnsRecord], plan_name: str) -> list[dict[str, Any]]:
    edges = [
        {"source": record.name, "target": record.target, "weight": record.weight}
        for record in records
        if record.kind == "CNAME" and record.name == plan_name
    ]
    return sorted(edges, key=lambda edge: (edge["target"], edge["weight"]))


def format_dns_record(value: Any) -> str:
    if not isinstance(value, dict):
        return str(value)
    if not {"kind", "name", "value"}.issubset(value):
        return str(value)
    target, weight = value["value"]
    return DnsRecord(
        kind=str(value["kind"]),
        name=str(value["name"]),
        target=str(target),
        weight=int(weight),
    ).label()


def format_weight_map(value: Any) -> str:
    if not isinstance(value, list):
        return str(value)
    pairs = [(str(key), int(weight)) for key, weight in value]
    return ", ".join(f"{ip}={weight}" for ip, weight in sorted(pairs))


def format_string_set(value: Any) -> str:
    if not isinstance(value, list):
        return str(value)
    return ", ".join(str(item) for item in sorted(value))


def format_int_set(value: Any) -> str:
    if not isinstance(value, list):
        return str(value)
    return ", ".join(str(item) for item in sorted(value))


def decode_ghost_action(state: dict[str, Any]) -> dict[str, Any]:
    raw = state["ghost_action"]
    if not isinstance(raw, dict) or "tag" not in raw or "value" not in raw:
        raise ValueError("ghost_action must be an ITF variant with tag and value")
    tag = str(raw["tag"])
    payload = unwrap(raw["value"])
    details: list[dict[str, str]] = []

    if tag == "Init":
        summary = "Init"
    elif tag == "GeneratePlan":
        summary = f"GeneratePlan {short_name(payload['plan_id'])} ({len(payload['ips'])} IPs)"
        details = [
            {"label": "Plan", "value": short_name(payload["plan_id"])},
            {"label": "IPs", "value": format_string_set(payload["ips"])},
            {"label": "Weights", "value": format_weight_map(payload["weights"])},
        ]
    elif tag == "Sync":
        summary = (
            f"Sync {payload['deployer']} root {short_name(payload['root'])} "
            f"rollback {short_name(payload['rollback'])}"
        )
        details = [
            {"label": "Deployer", "value": str(payload["deployer"])},
            {"label": "Lock", "value": format_dns_record(payload["lock"])},
            {"label": "Root", "value": short_name(payload["root"])},
            {"label": "Rollback", "value": short_name(payload["rollback"])},
        ]
    elif tag == "Deploy":
        summary = (
            f"Deploy {payload['deployer']} -> {short_name(payload['new_root'])} "
            f"epoch {payload['new_epoch']}"
        )
        details = [
            {"label": "Deployer", "value": str(payload["deployer"])},
            {"label": "Plan", "value": short_name(payload["plan_id"])},
            {"label": "Previous", "value": short_name(payload["previous_root"])},
            {"label": "New Root", "value": short_name(payload["new_root"])},
            {"label": "Rollback", "value": short_name(payload["rollback"])},
            {"label": "Epoch", "value": str(payload["new_epoch"])},
        ]
    elif tag == "Backoff":
        summary = f"Backoff {payload['deployer']}"
        details = [
            {"label": "Deployer", "value": str(payload["deployer"])},
            {"label": "Lock", "value": format_dns_record(payload["lock"])},
        ]
    elif tag == "Cleanup":
        summary = f"Cleanup {payload['deployer']} indices {format_int_set(payload['old_indices'])}"
        details = [
            {"label": "Deployer", "value": str(payload["deployer"])},
            {"label": "Next Plan", "value": str(payload["next_plan"])},
            {"label": "Indices", "value": format_int_set(payload["old_indices"])},
        ]
    else:
        summary = tag

    return {
        "tag": tag,
        "summary": summary,
        "details": details,
    }


def collect_reachable(
    records: list[DnsRecord],
    root_target: str | None,
    rollback_target: str | None,
    ips_by_balancer: dict[str, str],
) -> dict[str, Any]:
    plan_names = sorted({target for target in (root_target, rollback_target) if target})
    a_by_name: dict[str, list[str]] = {}
    for record in records:
        if record.kind == "A":
            a_by_name.setdefault(record.name, []).append(record.target)

    plans = []
    leaves = []
    edges = []
    for plan_name in plan_names:
        children = child_edges(records, plan_name)
        plans.append(
            {
                "id": plan_name,
                "label": short_name(plan_name),
                "full": plan_name,
                "missing": not children,
            }
        )
        for edge in children:
            leaf_id = edge["target"]
            ip = ips_by_balancer.get(leaf_id)
            if ip is None:
                ips = sorted(a_by_name.get(leaf_id, []) or a_by_name.get(plan_name, []))
                ip = ips[0] if len(ips) == 1 else ", ".join(ips)
            leaves.append(
                {
                    "id": leaf_id,
                    "label": short_name(leaf_id),
                    "full": leaf_id,
                    "ip": ip,
                    "parent": plan_name,
                }
            )
            edges.append(
                {
                    "source": plan_name,
                    "target": leaf_id,
                    "weight": edge["weight"],
                    "kind": "plan",
                }
            )
    return {"plans": plans, "leaves": leaves, "edges": edges}


def build_frames(
    trace: dict[str, Any],
    root_name: str = DEFAULT_ROOT_NAME,
    rollback_name: str = DEFAULT_ROLLBACK_NAME,
) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    previous_records: list[DnsRecord] | None = None

    for index, state in enumerate(trace["states"]):
        records = normalize_records(state)
        root_target, root_weight = entry_target(records, root_name)
        rollback_target, rollback_weight = entry_target(records, rollback_name)
        reachable = collect_reachable(records, root_target, rollback_target, balancer_ip_map(state))
        lock_records = [record for record in records if record.kind == "TXT" and record.name == "lock.example.com"]
        meta = state.get("#meta", {})
        frames.append(
            {
                "index": index,
                "step": meta.get("step", index),
                "actionTrace": meta.get("action_trace", []),
                "rootName": root_name,
                "rootLabel": short_name(root_name),
                "rootTarget": root_target,
                "rootWeight": root_weight,
                "rollbackName": rollback_name,
                "rollbackLabel": short_name(rollback_name),
                "rollbackTarget": rollback_target,
                "rollbackWeight": rollback_weight,
                "plans": reachable["plans"],
                "leaves": reachable["leaves"],
                "edges": reachable["edges"],
                "diff": diff_records(previous_records, records, {root_name, rollback_name}),
                "action": decode_ghost_action(state),
                "recordCount": len(records),
                "lock": lock_records[0].label() if lock_records else "",
            }
        )
        previous_records = records
    return frames


def parse_trace_objects(text: str, source: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        traces = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                traces.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid ITF NDJSON at {source}:{line_number}: {exc.msg}"
                ) from exc
        if not traces:
            raise ValueError(f"{source} contains no ITF traces")
    else:
        traces = payload if isinstance(payload, list) else [payload]

    for index, trace in enumerate(traces):
        if not isinstance(trace, dict) or "states" not in trace:
            raise ValueError(
                f"{source}[{index}] is not an ITF trace object with a top-level states array"
            )
    return traces


def load_trace(path: Path, trace_index: int = 0) -> dict[str, Any]:
    traces = parse_trace_objects(path.read_text(encoding="utf-8"), path)
    if trace_index < 0 or trace_index >= len(traces):
        raise ValueError(
            f"{path} contains {len(traces)} trace(s); trace index {trace_index} is out of range"
        )
    return traces[trace_index]


def render_html(trace: dict[str, Any], frames: list[dict[str, Any]], source: Path) -> str:
    payload = {
        "source": str(source),
        "meta": trace.get("#meta", {}),
        "frames": frames,
    }
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    title = f"Wunderspec Trace for DNS Balancer - {source.name}"
    return HTML_TEMPLATE.replace("__TITLE__", html.escape(title)).replace("__TRACE_DATA__", data)


def write_html(
    input_path: Path,
    output_path: Path,
    root_name: str,
    rollback_name: str,
    trace_index: int = 0,
) -> None:
    trace = load_trace(input_path, trace_index=trace_index)
    frames = build_frames(trace, root_name=root_name, rollback_name=rollback_name)
    output_path.write_text(render_html(trace, frames, input_path), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path, help="WunderSpec ITF JSON trace")
    parser.add_argument(
        "--trace-index",
        type=int,
        default=0,
        help="Trace index to visualize when input is NDJSON or a JSON array.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output HTML file. Defaults to <trace>.trace.html.",
    )
    parser.add_argument("--root-name", default=DEFAULT_ROOT_NAME, help="Root DNS CNAME owner")
    parser.add_argument(
        "--rollback-name",
        default=DEFAULT_ROLLBACK_NAME,
        help="Rollback DNS CNAME owner",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = args.output or args.trace.with_suffix(".trace.html")
    write_html(
        args.trace,
        output,
        args.root_name,
        args.rollback_name,
        trace_index=args.trace_index,
    )
    print(f"Wrote {output}")


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>__TITLE__</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #071018;
      --panel: #111923;
      --panel-2: #172230;
      --line: #758293;
      --text: #e7edf4;
      --muted: #98a5b5;
      --root: #4cc9f0;
      --rollback: #f2a65a;
      --added: #48c78e;
      --removed: #ff6b6b;
      --changed: #ffd166;
      --broken: #ff5c7c;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.4 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    main {
      display: grid;
      grid-template-rows: auto 1fr;
      min-height: 100vh;
      padding-bottom: 64px;
    }

    header, footer {
      background: var(--panel);
      border-bottom: 1px solid #263345;
      padding: 12px 18px;
    }

    footer {
      position: fixed;
      right: 0;
      bottom: 0;
      left: 0;
      z-index: 20;
      border-top: 1px solid #263345;
      border-bottom: 0;
      box-shadow: 0 -10px 24px rgba(0, 0, 0, 0.32);
    }

    h1 {
      margin: 0 0 4px;
      font-size: 18px;
      font-weight: 700;
      letter-spacing: 0;
    }

    .meta {
      color: var(--muted);
      display: flex;
      gap: 16px;
      flex-wrap: wrap;
    }

    .workspace {
      min-height: 0;
      height: calc(100vh - 124px);
      display: grid;
      grid-template-columns: minmax(0, 1fr) 320px;
      overflow: hidden;
    }

    .canvas {
      min-width: 0;
      min-height: 0;
      padding: 16px;
    }

    svg {
      width: 100%;
      height: calc(100vh - 188px);
      min-height: 460px;
      display: block;
      background: #071018;
      border: 1px solid #263345;
    }

    aside {
      min-width: 0;
      min-height: 0;
      border-left: 1px solid #263345;
      background: #0d151f;
      padding: 14px;
      overflow: auto;
    }

    .controls {
      display: grid;
      grid-template-columns: auto auto auto 1fr auto auto;
      gap: 10px;
      align-items: center;
    }

    button, select {
      min-height: 34px;
      border: 1px solid #34465d;
      background: var(--panel-2);
      color: var(--text);
      padding: 0 11px;
      border-radius: 6px;
      font: inherit;
    }

    button {
      min-width: 38px;
      cursor: pointer;
    }

    input[type="range"] {
      width: 100%;
    }

    .legend {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      margin-top: 8px;
      color: var(--muted);
      font-size: 12px;
    }

    .legend span::before {
      content: "";
      display: inline-block;
      width: 10px;
      height: 10px;
      margin-right: 6px;
      border-radius: 50%;
      vertical-align: -1px;
      background: var(--line);
    }

    .legend .root::before { background: var(--root); }
    .legend .rollback::before { background: var(--rollback); }
    .legend .broken::before { background: var(--broken); }

    h2 {
      margin: 0 0 8px;
      font-size: 13px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }

    .panel {
      margin-bottom: 18px;
    }

    .kv {
      display: grid;
      grid-template-columns: 92px 1fr;
      gap: 4px 10px;
      color: var(--muted);
    }

    .kv strong {
      color: var(--text);
      font-weight: 600;
      word-break: break-word;
    }

    .diff-list {
      list-style: none;
      margin: 0;
      padding: 0;
      display: grid;
      gap: 6px;
    }

    .diff-list li {
      border-left: 3px solid var(--line);
      background: #111923;
      padding: 6px 8px;
      color: var(--text);
      font-size: 12px;
      word-break: break-word;
    }

    .diff-list .added { border-color: var(--added); }
    .diff-list .removed { border-color: var(--removed); }
    .diff-list .changed { border-color: var(--changed); }

    .empty {
      color: var(--muted);
      font-size: 12px;
    }

    .action-summary {
      margin: 0 0 8px;
      color: var(--text);
      font-size: 15px;
      font-weight: 700;
      word-break: break-word;
    }

    .node rect {
      fill: #111923;
      stroke: #5b6878;
      stroke-width: 1.5;
    }

    .node text {
      fill: var(--text);
      font-size: 15px;
      text-anchor: middle;
      dominant-baseline: middle;
      letter-spacing: 0;
    }

    .node .sub {
      fill: var(--muted);
      font-size: 12px;
    }

    .entry.root rect { stroke: var(--root); }
    .entry.rollback rect { stroke: var(--rollback); }
    .plan.missing rect {
      stroke: var(--broken);
      stroke-width: 2.5;
      stroke-dasharray: 7 4;
    }

    .edge {
      fill: none;
      stroke: var(--line);
      stroke-width: 1.8;
      marker-end: url(#arrow);
    }

    .edge.root {
      stroke: var(--root);
      stroke-width: 2.5;
    }

    .edge.rollback {
      stroke: var(--rollback);
      stroke-width: 2.5;
      stroke-dasharray: 7 5;
    }

    .edge-label {
      fill: var(--muted);
      font-size: 12px;
      text-anchor: middle;
      paint-order: stroke;
      stroke: var(--bg);
      stroke-width: 5px;
      stroke-linejoin: round;
    }

    @media (max-width: 900px) {
      .workspace {
        grid-template-columns: 1fr;
      }

      aside {
        border-left: 0;
        border-top: 1px solid #263345;
      }

      svg {
        height: 58vh;
        min-height: 360px;
      }

      .controls {
        grid-template-columns: auto auto auto 1fr;
      }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Wunderspec Trace for DNS Balancer</h1>
      <div class="meta">
        <span id="source"></span>
        <span id="predicate"></span>
        <span id="violation"></span>
      </div>
    </header>
    <section class="workspace">
      <div class="canvas">
        <svg id="graph" viewBox="0 0 1100 620" role="img" aria-label="DNS state graph"></svg>
        <div class="legend">
          <span class="root">root CNAME</span>
          <span class="rollback">rollback CNAME</span>
          <span>plan edge</span>
          <span class="broken">missing plan records</span>
        </div>
      </div>
      <aside>
        <section class="panel">
          <h2>Action</h2>
          <p id="actionSummary" class="action-summary"></p>
          <div id="actionDetails" class="kv"></div>
        </section>
        <section class="panel">
          <h2>Frame</h2>
          <div class="kv">
            <span>Step</span><strong id="stepValue"></strong>
            <span>Records</span><strong id="recordCount"></strong>
            <span>Lock</span><strong id="lockValue"></strong>
            <span>Root</span><strong id="rootValue"></strong>
            <span>Rollback</span><strong id="rollbackValue"></strong>
          </div>
        </section>
        <section class="panel">
          <h2>Record Changes</h2>
          <ul id="diffList" class="diff-list"></ul>
        </section>
      </aside>
    </section>
    <footer>
      <div class="controls">
        <button id="previous" type="button" title="Previous frame">&lsaquo;</button>
        <button id="playPause" type="button" title="Play or pause">Play</button>
        <button id="next" type="button" title="Next frame">&rsaquo;</button>
        <input id="scrubber" type="range" min="0" value="0" step="1" aria-label="Frame">
        <span id="frameLabel"></span>
        <select id="speed" aria-label="Playback speed">
          <option value="1600">0.5x</option>
          <option value="900" selected>1x</option>
          <option value="450">2x</option>
          <option value="90">10x</option>
        </select>
      </div>
    </footer>
  </main>
  <script>
    const TRACE_DATA = __TRACE_DATA__;
    const frames = TRACE_DATA.frames;
    const graph = document.getElementById("graph");
    const scrubber = document.getElementById("scrubber");
    const playPause = document.getElementById("playPause");
    const previous = document.getElementById("previous");
    const next = document.getElementById("next");
    const speed = document.getElementById("speed");
    let frameIndex = 0;
    let timer = null;

    document.getElementById("source").textContent = TRACE_DATA.source;
    document.getElementById("predicate").textContent =
      TRACE_DATA.meta.predicate_kind ? `${TRACE_DATA.meta.predicate_kind}: ${TRACE_DATA.meta.predicate_name}` : "";
    document.getElementById("violation").textContent =
      TRACE_DATA.meta.violation_step !== undefined ? `violation step: ${TRACE_DATA.meta.violation_step}` : "";
    scrubber.max = Math.max(frames.length - 1, 0);

    function esc(value) {
      return String(value ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      })[c]);
    }

    function nodeMarkup(node, cls, x, y, w, h, sub) {
      const title = esc(node.full || node.id || node.label);
      const subtitle = sub ? `<text class="sub" x="${x}" y="${y + 17}">${esc(sub)}</text>` : "";
      const mainY = sub ? y - 8 : y;
      const missing = node.missing ? " missing" : "";
      return `<g class="node ${cls}${missing}">
        <title>${title}</title>
        <rect x="${x - w / 2}" y="${y - h / 2}" width="${w}" height="${h}" rx="6"></rect>
        <text x="${x}" y="${mainY}">${esc(node.label)}</text>
        ${subtitle}
      </g>`;
    }

    function edgeMarkup(from, to, cls, label) {
      const midX = (from.x + to.x) / 2;
      const midY = (from.y + to.y) / 2 - 8;
      const startY = from.y + from.h / 2;
      const endY = to.y - to.h / 2;
      return `<path class="edge ${cls}" d="M ${from.x} ${startY} C ${from.x} ${startY + 45}, ${to.x} ${endY - 45}, ${to.x} ${endY}"></path>
        <text class="edge-label" x="${midX}" y="${midY}">${esc(label)}</text>`;
    }

    function spread(count, width, margin) {
      if (count <= 1) return [width / 2];
      const step = (width - margin * 2) / (count - 1);
      return Array.from({ length: count }, (_, i) => margin + step * i);
    }

    function layout(frame) {
      const positions = new Map();
      positions.set("__root__", { x: 320, y: 70, w: 280, h: 54 });
      positions.set("__rollback__", { x: 780, y: 70, w: 280, h: 54 });

      const planXs = spread(frame.plans.length, 900, 220);
      frame.plans.forEach((plan, i) => positions.set(plan.id, { x: planXs[i], y: 235, w: 230, h: 60 }));

      const leavesByParent = new Map();
      frame.leaves.forEach(leaf => {
        if (!leavesByParent.has(leaf.parent)) leavesByParent.set(leaf.parent, []);
        leavesByParent.get(leaf.parent).push(leaf);
      });

      frame.plans.forEach(plan => {
        const leaves = leavesByParent.get(plan.id) || [];
        const planPos = positions.get(plan.id);
        const xs = spread(leaves.length, Math.min(360, leaves.length * 170), 70);
        const offset = planPos.x - (xs.length ? (xs[0] + xs[xs.length - 1]) / 2 : 0);
        leaves.forEach((leaf, i) => {
          positions.set(leaf.id, { x: xs[i] + offset, y: 440, w: 230, h: 68 });
        });
      });
      return positions;
    }

    function render(frame) {
      const positions = layout(frame);
      const rootNode = { label: frame.rootLabel, full: frame.rootName };
      const rollbackNode = { label: frame.rollbackLabel, full: frame.rollbackName };
      const parts = [
        `<defs>
          <marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">
            <path d="M 0 0 L 10 4 L 0 8 z" fill="#758293"></path>
          </marker>
        </defs>`
      ];

      if (frame.rootTarget && positions.has(frame.rootTarget)) {
        parts.push(edgeMarkup(positions.get("__root__"), positions.get(frame.rootTarget), "root", `root w=${frame.rootWeight}`));
      }
      if (frame.rollbackTarget && positions.has(frame.rollbackTarget)) {
        parts.push(edgeMarkup(positions.get("__rollback__"), positions.get(frame.rollbackTarget), "rollback", `rollback w=${frame.rollbackWeight}`));
      }
      frame.edges.forEach(edge => {
        if (positions.has(edge.source) && positions.has(edge.target)) {
          parts.push(edgeMarkup(positions.get(edge.source), positions.get(edge.target), "plan", `w=${edge.weight}`));
        }
      });

      parts.push(nodeMarkup(rootNode, "entry root", 320, 70, 280, 54));
      parts.push(nodeMarkup(rollbackNode, "entry rollback", 780, 70, 280, 54));
      frame.plans.forEach(plan => {
        const pos = positions.get(plan.id);
        parts.push(nodeMarkup(plan, "plan", pos.x, pos.y, pos.w, pos.h, plan.missing ? "no plan CNAMEs" : ""));
      });
      frame.leaves.forEach(leaf => {
        const pos = positions.get(leaf.id);
        parts.push(nodeMarkup(leaf, "leaf", pos.x, pos.y, pos.w, pos.h, leaf.ip ? `A ${leaf.ip}` : ""));
      });
      graph.innerHTML = parts.join("\n");
    }

    function renderDiff(diff) {
      const list = document.getElementById("diffList");
      const items = [];
      ["added", "removed", "changed"].forEach(kind => {
        diff[kind].forEach(label => items.push(`<li class="${kind}">${kind}: ${esc(label)}</li>`));
      });
      list.innerHTML = items.length ? items.join("") : `<li class="empty">No record changes in this frame.</li>`;
    }

    function renderAction(action) {
      document.getElementById("actionSummary").textContent = action.summary;
      const details = document.getElementById("actionDetails");
      details.innerHTML = action.details
        .map(item => `<span>${esc(item.label)}</span><strong>${esc(item.value)}</strong>`)
        .join("");
    }

    function show(index) {
      frameIndex = Math.max(0, Math.min(index, frames.length - 1));
      const frame = frames[frameIndex];
      scrubber.value = frameIndex;
      document.getElementById("frameLabel").textContent = `${frameIndex + 1} / ${frames.length}`;
      document.getElementById("stepValue").textContent = frame.step;
      document.getElementById("recordCount").textContent = frame.recordCount;
      document.getElementById("lockValue").textContent = frame.lock || "none";
      document.getElementById("rootValue").textContent = frame.rootTarget || "missing";
      document.getElementById("rollbackValue").textContent = frame.rollbackTarget || "missing";
      renderAction(frame.action);
      render(frame);
      renderDiff(frame.diff);
    }

    function stop() {
      if (timer) clearInterval(timer);
      timer = null;
      playPause.textContent = "Play";
    }

    function play() {
      stop();
      playPause.textContent = "Pause";
      timer = setInterval(() => {
        if (frameIndex >= frames.length - 1) {
          stop();
          return;
        }
        show(frameIndex + 1);
      }, Number(speed.value));
    }

    previous.addEventListener("click", () => { stop(); show(frameIndex - 1); });
    next.addEventListener("click", () => { stop(); show(frameIndex + 1); });
    scrubber.addEventListener("input", event => { stop(); show(Number(event.target.value)); });
    speed.addEventListener("change", () => { if (timer) play(); });
    playPause.addEventListener("click", () => timer ? stop() : play());
    document.addEventListener("keydown", event => {
      if (event.key === "ArrowLeft") { stop(); show(frameIndex - 1); }
      if (event.key === "ArrowRight") { stop(); show(frameIndex + 1); }
      if (event.key === " ") { event.preventDefault(); timer ? stop() : play(); }
    });

    show(0);
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
