"""JSON bridge for the Business Research Assistant LangGraph backend."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from agent import BusinessResearchGraph  # noqa: E402


def _load_payload() -> dict[str, Any]:
    raw_input = sys.stdin.read().strip()
    if not raw_input:
        return {}

    try:
        payload = json.loads(raw_input)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON payload: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object payload")

    return payload


def main() -> int:
    payload = _load_payload()
    query = str(payload.get("query", "")).strip()
    state = payload.get("state")

    assistant = BusinessResearchGraph()
    result = assistant.process_query(query, state)

    sys.stdout.write(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())