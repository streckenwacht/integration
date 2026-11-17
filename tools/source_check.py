#!/usr/bin/env python3
"""Check every data source against its live API with the real providers.

Usage (from the repo root):
    uv run tools/source_check.py [--markdown report.md]

Each source is fetched for a test area inside its region (the Autobahn API
for A8/A81 around Stuttgart). A source counts as a problem if it fails twice,
returns nothing, nothing lies in its own region (positions no longer parsed)
or no record has a time (date fields changed). Candidates (sources not built
in because they did not deliver, docs/DATENQUELLEN.md) are fetched too: one
that delivers again counts as a finding, so the weekly issue says it is time
to build it in (then move it from CANDIDATES to the providers) or to drop
it. Exit code 1 if any source has a problem or any candidate delivers. Run
weekly by .github/workflows/source-check.yml; nothing is written except the
report.
"""

from __future__ import annotations

import argparse
import asyncio
import math
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from custom_components.streckenwacht import PROVIDERS
from custom_components.streckenwacht.const import SOURCE_REGIONS, Source
from custom_components.streckenwacht.geo import haversine_km
from custom_components.streckenwacht.model import ObservationArea, StreckenwachtEvent
from custom_components.streckenwacht.providers import ProviderError

MAX_RADIUS_KM = 50
RETRY_AFTER_S = 60
CANDIDATE_TIMEOUT_S = 30


@dataclass(frozen=True)
class Candidate:
    """A source not built in yet: delivers once `url` answers 200 over a
    verified TLS connection with `marker` in the body."""

    name: str
    url: str
    marker: str
    why: str  # why it is not built in (shown in the report)


CANDIDATES: tuple[Candidate, ...] = (
    Candidate(
        "Heidelberg",
        "https://www.heidelberg.de/site/Heidelberg2021/BSTXC/1254509/data.json",
        "{",
        "Katalog-Adresse liefert 404 (seit 2026-10-18)",
    ),
)


def test_area(source: Source) -> ObservationArea:
    """A circle covering (most of) the first region of the source."""
    if source not in SOURCE_REGIONS:  # the Autobahn API: no region, but roads
        return ObservationArea("Test", 48.7758, 9.1829, 30, frozenset({"A8", "A81"}))
    south, west, north, east = SOURCE_REGIONS[source][0]
    lat, lon = (south + north) / 2, (west + east) / 2
    radius = min(MAX_RADIUS_KM, haversine_km(lat, lon, north, east))
    return ObservationArea("Test", lat, lon, math.floor(radius))


@dataclass
class Result:
    source: Source
    events: list[StreckenwachtEvent] | None = None
    inside: int = 0
    error: str | None = None

    @property
    def problem(self) -> str | None:
        if self.error:
            return f"Fehler: {self.error}"
        if not self.events:
            return "keine Meldungen (Quelle leer oder Format geändert?)"
        if not self.inside:
            return "keine Meldung im eigenen Gebiet (Positionen nicht erkannt?)"
        # Every source gives times for (nearly) all records; none at all
        # means the date fields changed. Roads are missing in some sources.
        if not any(e.periods for e in self.events):
            return "keine Zeiträume erkannt (Datumsfelder geändert?)"
        return None

    def share(self, test: Callable[[StreckenwachtEvent], bool]) -> str:
        if not self.events:
            return "–"
        return f"{round(100 * sum(map(test, self.events)) / len(self.events))} %"


async def check(session: aiohttp.ClientSession, source: Source) -> Result:
    area = test_area(source)
    provider = PROVIDERS[source](session)
    for attempt in range(2):
        try:
            events = await provider.async_fetch([area])
        except ProviderError as err:
            if attempt == 0:
                await asyncio.sleep(RETRY_AFTER_S)
                continue
            return Result(source, error=str(err) or type(err).__name__)
        inside = sum(1 for e in events if area.contains(e))
        return Result(source, events, inside)
    raise AssertionError("unreachable")


async def check_candidate(
    session: aiohttp.ClientSession, candidate: Candidate
) -> str | None:
    """None while the candidate does not deliver, else what it gave."""
    try:
        async with session.get(
            candidate.url, timeout=aiohttp.ClientTimeout(total=CANDIDATE_TIMEOUT_S)
        ) as response:
            if response.status != 200:
                return None
            body = await response.text(errors="replace")
    except aiohttp.ClientError, TimeoutError:
        return None
    if candidate.marker not in body:
        return None
    return f"HTTP 200, {len(body) // 1024} KB"


def report(
    results: list[Result], candidates: list[tuple[Candidate, str | None]]
) -> str:
    problems = [r for r in results if r.problem]
    delivering = [c for c, found in candidates if found]
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"## Quellen-Check {now}",
        "",
        f"**{len(problems)} von {len(results)} Quellen mit Problemen.**"
        if problems
        else f"Alle {len(results)} Quellen liefern Daten.",
        "",
        "| Quelle | Meldungen | im Testgebiet | mit Zeitraum | mit Straße | Befund |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for r in results:
        lines.append(
            f"| {r.source.value} | {len(r.events) if r.events is not None else '–'}"
            f" | {r.inside if r.events is not None else '–'}"
            f" | {r.share(lambda e: bool(e.periods))}"
            f" | {r.share(lambda e: bool(e.road))}"
            f" | {r.problem or 'ok'} |"
        )
    if candidates:
        lines += [
            "",
            "### Kandidaten (noch nicht eingebaut)",
            "",
            f"**{len(delivering)} Kandidat(en) liefern: einbauen oder aus `CANDIDATES` nehmen.**"
            if delivering
            else "Kein Kandidat liefert.",
            "",
            "| Kandidat | Stand | Warum nicht eingebaut |",
            "|---|---|---|",
        ]
        lines += [
            f"| {c.name} | {found or 'liefert nicht'} | {c.why} |"
            for c, found in candidates
        ]
    return "\n".join(lines) + "\n"


async def check_all() -> tuple[list[Result], list[tuple[Candidate, str | None]]]:
    # Windows: aiodns (installed with Home Assistant) cannot find the DNS servers.
    connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
    async with aiohttp.ClientSession(connector=connector) as session:
        results = list(await asyncio.gather(*(check(session, s) for s in Source)))
        found = await asyncio.gather(*(check_candidate(session, c) for c in CANDIDATES))
        return results, list(zip(CANDIDATES, found, strict=True))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--markdown", help="also write the report to this file")
    args = parser.parse_args()
    results, candidates = asyncio.run(check_all())
    text = report(results, candidates)
    print(text)
    if args.markdown:
        Path(args.markdown).write_text(text, encoding="utf-8")
    attention = any(r.problem for r in results) or any(f for _, f in candidates)
    sys.exit(1 if attention else 0)
