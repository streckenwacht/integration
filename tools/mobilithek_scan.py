"""List all Mobilithek roadworks offers and check whether any is openly accessible."""

import json
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
UA = "Streckenwacht/0.1.0b5 (+https://github.com/streckenwacht/integration)"
BASE = "https://mobilithek.info/mdp-api/mdp-msa-metadata/v2/offers"


def post(body: dict) -> dict:
    req = urllib.request.Request(
        BASE + "/search",
        data=json.dumps(body).encode(),
        headers={"User-Agent": UA, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def get(pid: str) -> dict:
    req = urllib.request.Request(f"{BASE}/{pid}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


ids: dict[str, str] = {}
for term in ["Baustellen", "Baustelle", "Arbeitsstellen", "Sperrungen", "Roadworks", "Verkehrsmeldungen"]:
    page = 0
    while True:
        data = post({"searchString": term, "page": page, "size": 100})
        offers = data.get("dataOffers", {})
        content = offers.get("content", [])
        for o in content:
            ids[o["publicationId"]] = o.get("title", "")
        total_pages = offers.get("totalPages") or offers.get("page", {}).get("totalPages") or 1
        page += 1
        if page >= total_pages or not content:
            break
print(f"{len(ids)} Angebote gefunden, prüfe Zugang …", flush=True)

rows = []
for pid, title in ids.items():
    try:
        d = get(pid)
    except Exception as err:  # noqa: BLE001
        rows.append((pid, title, "FEHLER", repr(err)))
        continue
    category = (d.get("dataCategory") or "").rsplit("#", 1)[-1]
    contract = d.get("contractOffer") or {}
    urls = [c.get("accessUrl") for c in d.get("contentData") or [] if c.get("accessUrl")]
    approval = contract.get("providerApprovalRequired")
    broker = d.get("mdpBrokering")
    pub = ((d.get("agents") or {}).get("publisher") or {}).get("name") or ""
    rows.append((pid, title, category, approval, broker, urls[:1], pub))
    time.sleep(0.2)

relevant = [r for r in rows if len(r) > 4 and r[2] in ("ROAD_WORK_INFORMATION", "TRAFFIC_INFORMATION", "TRAFFIC_MESSAGES")]
other_cats = sorted({r[2] for r in rows if len(r) > 4})
print("Kategorien:", other_cats)
print(f"\nBaustellen/Verkehrsinfo-Angebote: {len(relevant)}")
open_ = [r for r in relevant if (not r[3]) or r[5]]
print(f"davon OHNE Freigabe oder MIT direkter URL: {len(open_)}\n")
for pid, title, cat, approval, broker, urls, pub in sorted(open_, key=lambda r: r[6]):
    print(f"  OFFEN? {pub[:40]:40} | {title[:60]:60} | Freigabe={approval} Broker={broker} | {urls}")
print("\nAlle (Herausgeber | Titel | Freigabe):")
for pid, title, cat, approval, broker, urls, pub in sorted(relevant, key=lambda r: r[6]):
    print(f"  {pub[:42]:42} | {title[:58]:58} | {cat[:22]:22} | Freigabe={approval}")
