"""Shared test helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> Any:
    """Load a JSON fixture recorded by tools/fetch_fixtures.py."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))
