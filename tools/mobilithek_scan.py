#!/usr/bin/env python3
"""List Mobilithek roadworks offers and show which ones are openly accessible.

Usage (from the repo root):
    uv run --python 3.13 --no-project tools/mobilithek_scan.py

Offers with `providerApprovalRequired` need a subscription, provider approval
and a client certificate per data consumer - unusable for a HACS integration.
Offers without approval and with a direct access URL are candidates for new
providers (see docs/DATENQUELLEN.md). Standard library only.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from dataclasses import dataclass

UA = "Streckenwacht/0.1 (+https://github.com/streckenwacht/integration)"
BASE = "https://mobilithek.info/mdp-api/mdp-msa-metadata/v2/offers"
TERMS = [
    "Baustellen",
    "Baustelle",
    "Arbeitsstellen",
    "Sperrungen",
    "Roadworks",
    "Verkehrsmeldungen",
]
CATEGORIES = {"ROAD_WORK_INFORMATION", "TRAFFIC_INFORMATION", "TRAFFIC_MESSAGES"}


@dataclass
class Offer:
    title: str
    publisher: str
    category: str
    approval: bool | None
    access_url: str | None

    @property
    def open(self) -> bool:
        return not self.approval or self.access_url is not None


def _request(url: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"User-Agent": UA, "Content-Type": "application/json"},
        method="POST" if body is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def search_ids() -> dict[str, str]:
    ids: dict[str, str] = {}
    for term in TERMS:
        page = 0
        while True:
            offers = _request(
                f"{BASE}/search", {"searchString": term, "page": page, "size": 100}
            ).get("dataOffers", {})
            content = offers.get("content", [])
            for offer in content:
                ids[offer["publicationId"]] = offer.get("title", "")
            page += 1
            if not content or page >= (offers.get("totalPages") or 1):
                break
    return ids


def details(publication_id: str) -> Offer:
    data = _request(f"{BASE}/{publication_id}")
    urls = [c["accessUrl"] for c in data.get("contentData") or [] if c.get("accessUrl")]
    publisher = ((data.get("agents") or {}).get("publisher") or {}).get("name") or ""
    return Offer(
        title=data.get("title") or "",
        publisher=publisher,
        category=(data.get("dataCategory") or "").rsplit("#", 1)[-1],
        approval=(data.get("contractOffer") or {}).get("providerApprovalRequired"),
        access_url=urls[0] if urls else None,
    )


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ids = search_ids()
    print(f"{len(ids)} Angebote gefunden, prüfe Zugang …")
    offers = []
    for publication_id in ids:
        try:
            offers.append(details(publication_id))
        except OSError as err:
            print(f"  ! {publication_id}: {err}")
        time.sleep(0.2)
    relevant = sorted(
        (o for o in offers if o.category in CATEGORIES), key=lambda o: o.publisher
    )
    open_offers = [o for o in relevant if o.open]
    print(
        f"\n{len(relevant)} Baustellen-/Verkehrsinfo-Angebote, davon offen: {len(open_offers)}\n"
    )
    for o in open_offers:
        print(f"  OFFEN  {o.publisher[:40]:40} | {o.title[:60]:60} | {o.access_url}")
    print()
    for o in relevant:
        if not o.open:
            print(f"  Freigabe nötig  {o.publisher[:40]:40} | {o.title[:60]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
