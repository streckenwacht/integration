"""Shared test helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> Any:
    """Load a JSON fixture recorded by tools/fetch_fixtures.py."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


try:
    import pytest_socket  # noqa: F401  # installed with the HA test harness (CI)
except ImportError:

    @pytest.fixture
    def socket_enabled() -> None:
        """Stand-in for pytest-socket's fixture when sockets are not blocked.

        In CI the HA test harness blocks sockets; tests that run a local aiohttp
        test server request socket_enabled, as Home Assistant's own fixtures do.
        """
