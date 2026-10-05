#!/usr/bin/env python3
"""Lädt echte Beispielantworten der drei Streckenwacht-Datenquellen als Test-Fixtures.

Aufruf (aus dem Repo-Root):
    uv run --python 3.13 --no-project tools/fetch_fixtures.py
    (oder mit installiertem Python: python tools/fetch_fixtures.py)

Ergebnis: Dateien in tests/fixtures/ plus eine Übersicht tests/fixtures/_index.json.
Nur Python-Standardbibliothek, keine Abhängigkeiten.

Endpoints und Layernamen sind gegen die Live-APIs verifiziert (Stand 2026-10-02,
siehe docs/ENTWICKLUNG.md Abschnitt 2).
"""

from __future__ import annotations

import contextlib
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

USER_AGENT = "Streckenwacht/0.1 (+https://github.com/streckenwacht/integration)"
OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
TIMEOUT = 30

AUTOBAHN_BASE = "https://verkehr.autobahn.de/o/autobahn"
AUTOBAHN_ROADS = ["A8", "A81"]  # Testfall: A8/A81 im Raum Stuttgart
AUTOBAHN_SERVICES = ["roadworks", "closure", "warning"]

MOBIDATA_URL = (
    "https://api.mobidata-bw.de/datasets/traffic/roadworks/roadworks_geojson.json"
)

# GeoServer liefert die Layer direkt als GeoJSON in WGS84 – kein GML-Parsing, keine Reprojektion.
STUTTGART_WFS = "https://geoserver.stuttgart.de/geoserver/wfs"
STUTTGART_LAYERS = {
    "geplant": "GEOLINE_FLEX:A66_BAUM_BAUSTELLEN_DATE_geplant_EPSG25832",
    "im_bau": "GEOLINE_FLEX:A66_BAUM_BAUSTELLEN_DATE_im_Bau_EPSG25832",
}

index: list[dict] = []


def get(url: str) -> tuple[int, bytes, str]:
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"}
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.read(), r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, e.read() if hasattr(e, "read") else b"", ""
    except Exception as e:
        print(f"  ! {url}: {e}")
        return 0, b"", ""


def save(name: str, url: str, status: int, body: bytes, ctype: str) -> None:
    path = OUT / name
    if "json" in ctype or name.endswith(".json"):
        with contextlib.suppress(ValueError):
            body = json.dumps(json.loads(body), ensure_ascii=False, indent=2).encode()
    path.write_bytes(body)
    index.append(
        {
            "file": name,
            "url": url,
            "status": status,
            "content_type": ctype,
            "bytes": len(body),
        }
    )
    print(f"  {status} {len(body):>9} B  {name}")


def autobahn() -> None:
    print("Autobahn-API")
    s, b, c = get(AUTOBAHN_BASE + "/")
    save("autobahn_roads.json", AUTOBAHN_BASE + "/", s, b, c)
    for road in AUTOBAHN_ROADS:
        for svc in AUTOBAHN_SERVICES:
            url = f"{AUTOBAHN_BASE}/{road}/services/{svc}"
            s, b, c = get(url)
            save(f"autobahn_{road}_{svc}.json", url, s, b, c)


def mobidata() -> None:
    print("MobiData BW")
    s, b, c = get(MOBIDATA_URL)
    save("mobidata_bw_roadworks.geojson.json", MOBIDATA_URL, s, b, c)


def stuttgart() -> None:
    print("Stuttgart WFS")
    for key, layer in STUTTGART_LAYERS.items():
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": layer,
            "outputFormat": "application/json",
            "srsName": "EPSG:4326",
        }
        url = STUTTGART_WFS + "?" + urllib.parse.urlencode(params)
        s, b, c = get(url)
        save(f"stuttgart_{key}.geojson.json", url, s, b, c)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    autobahn()
    mobidata()
    stuttgart()
    (OUT / "_index.json").write_text(
        json.dumps(
            {
                "fetched_at": datetime.now(UTC).isoformat(),
                "user_agent": USER_AGENT,
                "files": index,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    failed = [i for i in index if i["status"] != 200]
    print(f"\n{len(index) - len(failed)} ok, {len(failed)} fehlgeschlagen -> {OUT}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
