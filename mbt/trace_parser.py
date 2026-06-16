"""Helpers for loading WunderSpec ITF traces for MBT replay."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def unwrap_itf(value: Any) -> Any:
    """Convert ITF-encoded values into plain Python containers and scalars."""
    if isinstance(value, dict):
        if "#bigint" in value:
            return int(value["#bigint"])
        if "#set" in value:
            return [unwrap_itf(item) for item in value["#set"]]
        if "#map" in value:
            return [(unwrap_itf(key), unwrap_itf(val)) for key, val in value["#map"]]
        if "#tup" in value:
            return tuple(unwrap_itf(item) for item in value["#tup"])
        return {key: unwrap_itf(val) for key, val in value.items()}
    if isinstance(value, list):
        return [unwrap_itf(item) for item in value]
    return value


def load_itf_traces(path: Path) -> list[dict[str, Any]]:
    """Load one or more ITF traces from single-trace JSON or NDJSON."""
    return parse_itf_traces(path.read_text(), source=str(path))


def parse_itf_traces(text: str, *, source: str) -> list[dict[str, Any]]:
    """Parse one or more ITF traces from JSON or NDJSON text."""
    if not text.strip():
        raise AssertionError(f"ITF input is empty: {source}")

    try:
        trace = json.loads(text)
    except json.JSONDecodeError:
        traces = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                traces.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise AssertionError(
                    f"invalid ITF NDJSON at {source}:{line_number}: {exc.msg}"
                ) from exc
        if not traces:
            raise AssertionError(f"ITF NDJSON contains no traces: {source}")
        return traces

    if isinstance(trace, list):
        return trace
    return [trace]
