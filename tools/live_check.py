#!/usr/bin/env python3
"""Run the providers against the live APIs, outside Home Assistant.

Usage (from the repo root):
    uv run tools/live_check.py --lat 48.7758 --lon 9.1829 --radius 15 --roads A8 A81

Prints every event within the area. Nothing is written anywhere.
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import sys
from datetime import UTC, datetime
from pathlib import Path

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from custom_components.streckenwacht.model import (
    ObservationArea,
    StreckenwachtEvent,
)
from custom_components.streckenwacht.providers import ProviderError
from custom_components.streckenwacht.providers.autobahn import (
    AutobahnProvider,
)


def fmt(moment: datetime | None) -> str:
    return moment.astimezone().strftime("%d.%m.%y %H:%M") if moment else "offen"


def show(events: list[StreckenwachtEvent], area: ObservationArea) -> None:
    now = datetime.now(UTC)
    inside = [e for e in events if area.contains(e)]
    counts = collections.Counter(e.event_type.value for e in inside)
    print(
        f"  {len(events)} Meldungen geladen, {len(inside)} im Bereich: {dict(counts)}"
    )
    for e in sorted(inside, key=lambda e: (not e.is_active(now), e.start or now)):
        state = "AKTIV" if e.is_active(now) else "     "
        delay = f" | +{e.delay_minutes} min" if e.delay_minutes else ""
        print(
            f"  {state} {e.event_type.value:11} {e.title[:48]:48} "
            f"{fmt(e.start)} -> {fmt(e.end)} ({len(e.periods)} Fenster){delay}"
        )


async def main(args: argparse.Namespace) -> int:
    area = ObservationArea(
        "Live-Check", args.lat, args.lon, args.radius, frozenset(args.roads)
    )
    # Windows: aiodns (installed with Home Assistant) cannot find the DNS servers.
    connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
    failed = False
    async with aiohttp.ClientSession(connector=connector) as session:
        for provider in (AutobahnProvider(session),):
            print(f"{provider.source}:")
            try:
                show(await provider.async_fetch([area]), area)
            except ProviderError as err:
                print(f"  FEHLER: {err}")
                failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    # Windows consoles default to a legacy code page: umlauts would break.
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--radius", type=float, default=15, help="km")
    parser.add_argument("--roads", nargs="*", default=[], help="z. B. A8 A81")
    sys.exit(asyncio.run(main(parser.parse_args())))
