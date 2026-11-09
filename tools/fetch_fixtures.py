#!/usr/bin/env python3
"""Lädt echte Beispielantworten der Streckenwacht-Datenquellen als Test-Fixtures.

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
import io
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
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
STUTTGART_WFS = "https://geoserver.stuttgart.de/gdc/Verkehr_Mobilitaet/ows"
STUTTGART_LAYERS = {
    "geplant": "Verkehr_Mobilitaet:A66_BAUM_BAUSTELLEN_DATE_WEB_geplant_EPSG25832",
    "im_bau": "Verkehr_Mobilitaet:A66_BAUM_BAUSTELLEN_DATE_WEB_im_Bau_EPSG25832",
}

# Norddeutscher WFS (LBV.SH, CC BY 4.0): je Layer ein kleiner Ausschnitt per BBOX
# (Süd, West, Nord, Ost), damit die Fixtures klein bleiben.
NORD_WFS = "https://dienste.gdi-sh.de/WFS_SH_Baustelleninformationen"
NORD_LAYERS = {
    "Baustellen_SH": (54.25, 9.95, 54.45, 10.30),  # Kiel
    "Verkehrsstoerungen": (53.35, 7.8, 55.1, 11.4),  # ganz SH
    "Baustellen_FHH": (53.53, 9.95, 53.58, 10.05),  # Hamburg-Mitte
    "Baustellen_MV": (53.45, 11.20, 53.80, 11.60),  # Schwerin
    "Baustellen_Niedersachsen": (52.0, 9.0, 53.0, 10.5),  # Raum Hannover
}

# Ostdeutsche Quellen: Berlin komplett (mit ETag), Brandenburg per Ausschnitt
# (Raum Potsdam), Sachsen-Anhalt komplett (klein).
BERLIN_URL = "https://api.viz.berlin.de/daten/baustellen_sperrungen_viz.json"
BRANDENBURG_URL = (
    "https://isk.geobasis-bb.de/ows/baustelleninfo_wfs?SERVICE=WFS&VERSION=2.0.0"
    "&REQUEST=GetFeature&TYPENAMES=app:baustelleninfo"
    "&OUTPUTFORMAT=application/geo%2Bjson&SRSNAME=EPSG:4326"
    "&BBOX=52.0,12.5,52.6,13.5,urn:ogc:def:crs:EPSG::4326"
)
SACHSEN_ANHALT_URL = (
    "https://service.ifak.eu/sperrinfo/wfs?SERVICE=WFS&VERSION=2.0.0"
    "&REQUEST=GetFeature&TYPENAMES=ms:roadworks&OUTPUTFORMAT=geojson"
    "&SRSNAME=EPSG:4326"
)

# Sachsen: ZIP mit GeoJSON in UTM 33N; gespeichert wird nur ein Auszug der
# Sperrungen rund um Leipzig (unverändert in UTM), damit die Fixture klein bleibt.
SACHSEN_URL = "https://www.list.smwa.sachsen.de/gdi/download/baustelleninfo/Baustelleninfo_Sachsen_geojson.zip"
SACHSEN_EXCERPT = (300_000, 5_665_000, 330_000, 5_700_000)  # UTM: Ost/Nord min/max

# Rheinland-Pfalz: nur die Meldungen der Landesbehörden (CQL-Filter), davon
# ein Auszug rund um Mainz und Koblenz.
RLP_URL = (
    "https://maps.mobilitaetsatlas.de/geoserver/ows?service=WFS&version=2.0.0"
    "&request=GetFeature&typeNames=mwvlw:baustelle&outputFormat=application/json"
    "&srsName=EPSG:4326&CQL_FILTER="
    + urllib.parse.quote("quelle='Verkehrsbehörden in Rheinland-Pfalz'")
)
RLP_EXCERPT = (49.9, 7.4, 50.5, 8.4)  # Süd, West, Nord, Ost

# Großstädte: München (nur Fahrbahn-Baustellen, Ausschnitt Innenstadt),
# Frankfurt (Ausschnitt Innenstadt), Dortmund.
MUENCHEN_URL = (
    "https://geoportal.muenchen.de/geoserver/mor_wfs/ows?service=WFS&version=2.0.0"
    "&request=GetFeature&typeNames=mor_wfs:baustellen_opendata"
    "&outputFormat=application/json&srsName=EPSG:4326&CQL_FILTER="
    + urllib.parse.quote("art='Baumaßnahme' AND betroffene_bereiche LIKE '%Fahrbahn%'")
)
FRANKFURT_URL = (
    "https://geowebdienste.frankfurt.de/Baustellen?SERVICE=WFS&VERSION=2.0.0"
    "&REQUEST=GetFeature&TYPENAMES=opendata_verkehr:{}"
    "&OUTPUTFORMAT=application/json&SRSNAME=EPSG:4326"
)
DORTMUND_URL = (
    "https://open-data.dortmund.de/api/v2/catalog/datasets/{}/exports/geojson"
)
AACHEN_URL = (
    "https://bsis.aachen.de/geoserver/ows?service=WFS&version=2.0.0&request=GetFeature"
    "&typeNames=BSIS:PUNKTE_ALLE&outputFormat=application/json&srsName=EPSG:4326"
)
DUISBURG_URL = (
    "https://geoportal2.duisburg.de/arcgisserver/rest/services/Masterportal/"
    "MP_Verkehrsportal/MapServer/2/query?where=1%3D1&outFields=*&f=geojson&outSR=4326"
)
CITY_EXCERPTS = {
    "aachen": (50.765, 6.07, 50.785, 6.10),
    "muenchen": (48.134, 11.566, 48.142, 11.582),
    "frankfurt": (50.09, 8.64, 50.13, 8.71),
}

# Luxemburg (Ponts et Chaussées, CC0): DATEX II, gekürzt auf die ersten
# Situationen, damit die Fixture klein bleibt.
LUXEMBURG_URLS = {
    "luxemburg_aktuell.xml": "https://www.cita.lu/info_trafic/datex/chantierActuelDatex.xml",
    "luxemburg_geplant.xml": "https://www.cita.lu/info_trafic/datex/chantierFuturDatex.xml",
}
LUXEMBURG_SITUATIONS = 20

# Weitere Städte (0.4.0): Karlsruhe (Ausschnitt Innenstadt), Rostock,
# Kiel (Linien, aktuell), Ingolstadt (UTM 32N, unverändert).
KARLSRUHE_URL = (
    "https://mobil.trk.de/geoserver/TBA/ows?service=WFS&version=2.0.0&request=GetFeature"
    "&typeNames=TBA:baustellen&outputFormat=application/json&srsName=EPSG:4326&CQL_FILTER="
    + urllib.parse.quote(
        "sperrung IN ('mit Vollsperrung', 'mit Sperrung in eine Fahrtrichtung', "
        "'mit Verkehrsbehinderung')"
    )
)
ROSTOCK_URL = "https://geo.sv.rostock.de/download/opendata/baustellen/baustellen.json"
KIEL_URL = (
    "https://ims.kiel.de/geodatenextern/services/Stadtplan/LHKielWmsWfs/MapServer/WFSServer"
    "?service=WFS&version=2.0.0&request=GetFeature&typeNames=lhkiel:Baustellen_L_-_Aktuell"
    "&outputFormat=geoJSON&srsName=EPSG:4326"
)
INGOLSTADT_URL = (
    "https://www.ingolstadt.de/openbydata/VMS/Baustellen_14_Tage_Ingolstadt.geojson"
)
KARLSRUHE_EXCERPT = (48.995, 8.38, 49.02, 8.43)
# Freiburg (WFS, ~20 Baustellen) und Verkehrsmeldungen der Landesmeldestelle BW
# (DATEX II, redaktionell, keine INRIX-Daten).
FREIBURG_URL = (
    "https://geoportal.freiburg.de/wfs/gut_baustellen/gut_baustellen?service=WFS"
    "&version=2.0.0&request=GetFeature&typeNames=baustellenumgriffe"
    "&outputFormat=GEOJSON&srsName=EPSG:4326"
)
LMS_BW_URL = (
    "https://api.mobidata-bw.de/datasets/traffic/incidents/incidents_lmsbw.datex2.xml"
)

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
            # wie im Provider: "im Bau" scheitert sonst an VERKEHRSAUSWIRKUNG
            "propertyName": "SHAPE,STRASSENNAME,DETAILS_STANDORT,ANFANG,ENDE,"
            "ZEITL_REGELUNG,ART_ARBEIT,STATUS",
        }
        url = STUTTGART_WFS + "?" + urllib.parse.urlencode(params)
        s, b, c = get(url)
        save(f"stuttgart_{key}.geojson.json", url, s, b, c)


def norddeutschland() -> None:
    print("Norddeutscher WFS")
    for layer, (south, west, north, east) in NORD_LAYERS.items():
        params = {
            "SERVICE": "WFS",
            "VERSION": "2.0.0",
            "REQUEST": "GetFeature",
            "TYPENAMES": f"Baustelleninformationen:{layer}",
            "OUTPUTFORMAT": "GEOJSON",
            "SRSNAME": "EPSG:4326",
            "BBOX": f"{south},{west},{north},{east},urn:ogc:def:crs:EPSG::4326",
        }
        url = NORD_WFS + "?" + urllib.parse.urlencode(params)
        s, b, c = get(url)
        save(f"norddeutschland_{layer}.geojson.json", url, s, b, c)


def osten() -> None:
    print("Berlin, Brandenburg, Sachsen-Anhalt")
    for name, url in (
        ("berlin_viz.geojson.json", BERLIN_URL),
        ("brandenburg_potsdam.geojson.json", BRANDENBURG_URL),
        ("sachsen_anhalt_roadworks.geojson.json", SACHSEN_ANHALT_URL),
    ):
        s, b, c = get(url)
        save(name, url, s, b, c)


def sachsen() -> None:
    print("Sachsen")
    s, b, c = get(SACHSEN_URL)
    if s != 200:
        save("sachsen_sperrungen_leipzig.geojson.json", SACHSEN_URL, s, b, c)
        return
    with zipfile.ZipFile(io.BytesIO(b)) as archive:
        name = next(n for n in archive.namelist() if "Sperrungen" in n)
        data = json.loads(archive.read(name))
    e0, n0, e1, n1 = SACHSEN_EXCERPT

    def inside(feature: dict) -> bool:
        x, y = feature["geometry"]["coordinates"][0][:2]
        return e0 <= x <= e1 and n0 <= y <= n1

    data["features"] = [f for f in data["features"] if inside(f)]
    body = json.dumps(data, ensure_ascii=False).encode()
    save("sachsen_sperrungen_leipzig.geojson.json", SACHSEN_URL, s, body, c)


def rheinland_pfalz() -> None:
    print("Rheinland-Pfalz")
    s, b, c = get(RLP_URL)
    if s == 200:
        data = json.loads(b)
        south, west, north, east = RLP_EXCERPT
        data["features"] = [
            f
            for f in data["features"]
            if south <= f["geometry"]["coordinates"][1] <= north
            and west <= f["geometry"]["coordinates"][0] <= east
        ]
        b = json.dumps(data, ensure_ascii=False).encode()
    save("rheinland_pfalz_mainz_koblenz.geojson.json", RLP_URL, s, b, c)


def _first_lon_lat(geometry: dict) -> tuple[float, float]:
    coords = geometry["coordinates"]
    while isinstance(coords[0], list):
        coords = coords[0]
    return coords[0], coords[1]


def _excerpt(body: bytes, bounds: tuple[float, float, float, float]) -> bytes:
    data = json.loads(body)
    south, west, north, east = bounds
    data["features"] = [
        f
        for f in data["features"]
        if f.get("geometry")
        and west <= _first_lon_lat(f["geometry"])[0] <= east
        and south <= _first_lon_lat(f["geometry"])[1] <= north
    ]
    return json.dumps(data, ensure_ascii=False).encode()


def staedte() -> None:
    print("Großstädte")
    s, b, c = get(MUENCHEN_URL)
    if s == 200:
        b = _excerpt(b, CITY_EXCERPTS["muenchen"])
    save("muenchen_innenstadt.geojson.json", MUENCHEN_URL, s, b, c)
    for layer in ("Baustellen", "Verkehrsmeldungen"):
        url = FRANKFURT_URL.format(layer)
        s, b, c = get(url)
        if s == 200:
            b = _excerpt(b, CITY_EXCERPTS["frankfurt"])
        save(f"frankfurt_{layer.lower()}.geojson.json", url, s, b, c)
    for name in ("fb66-baustellen-tagesaktuell", "fb66-baustellen-geplant"):
        url = DORTMUND_URL.format(name)
        s, b, c = get(url)
        save(f"dortmund_{name.removeprefix('fb66-')}.geojson.json", url, s, b, c)
    s, b, c = get(AACHEN_URL)
    if s == 200:
        b = _excerpt(b, CITY_EXCERPTS["aachen"])
    save("aachen_innenstadt.geojson.json", AACHEN_URL, s, b, c)
    s, b, c = get(DUISBURG_URL)
    save("duisburg_baustellen.geojson.json", DUISBURG_URL, s, b, c)


def luxemburg() -> None:
    import gzip
    import xml.etree.ElementTree as ET

    print("Luxemburg")
    for name, url in LUXEMBURG_URLS.items():
        s, b, c = get(url)
        if s == 200:
            if b[:2] == b"\x1f\x8b":
                b = gzip.decompress(b)
            ET.register_namespace("", "http://datex2.eu/schema/2/2_0")
            ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
            root = ET.fromstring(b)
            for publication in root.iter():
                situations = [e for e in publication if e.tag.endswith("}situation")]
                for situation in situations[LUXEMBURG_SITUATIONS:]:
                    publication.remove(situation)
            b = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        save(name, url, s, b, c)


def staedte_2() -> None:
    print("Weitere Städte")
    s, b, c = get(KARLSRUHE_URL)
    if s == 200:
        b = _excerpt(b, KARLSRUHE_EXCERPT)
    save("karlsruhe_innenstadt.geojson.json", KARLSRUHE_URL, s, b, c)
    for name, url in (
        ("rostock_baustellen.geojson.json", ROSTOCK_URL),
        ("kiel_linien_aktuell.geojson.json", KIEL_URL),
    ):
        s, b, c = get(url)
        save(name, url, s, b, c)
    s, b, c = get(INGOLSTADT_URL)
    if s == 200:
        # Contact addresses are not needed for the tests.
        data = json.loads(b)
        for feature in data["features"]:
            feature["properties"]["AUFTRAGGEBER_EMAIL"] = ""
        b = json.dumps(data, ensure_ascii=False).encode()
    save("ingolstadt_baustellen.geojson.json", INGOLSTADT_URL, s, b, c)


def bw_meldungen() -> None:
    import gzip
    import re
    import xml.etree.ElementTree as ET

    print("Freiburg und LMS BW")
    s, b, c = get(FREIBURG_URL)
    save("freiburg_baustellen.geojson.json", FREIBURG_URL, s, b, c)
    s, b, c = get(LMS_BW_URL)
    if s == 200 and b[:2] == b"\x1f\x8b":
        b = gzip.decompress(b)
    if s == 200:
        # Klein halten: die ersten 6 Meldungen plus erledigte und Autobahn-
        # Meldungen (beide werden im Provider ausgefiltert).
        ET.register_namespace("", "http://datex2.eu/schema/2/2_0")
        ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
        root = ET.fromstring(b)
        for publication in root.iter():
            situations = [e for e in publication if e.tag.endswith("}situation")]
            for index, situation in enumerate(situations):
                xml = ET.tostring(situation, encoding="unicode")
                keep = (
                    index < 6
                    or "suspended" in xml
                    or re.search(r'lang="de-DE">A\d+ ', xml)
                )
                if not keep:
                    publication.remove(situation)
        b = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    save("lms_bw_meldungen.datex2.xml", LMS_BW_URL, s, b, c)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    autobahn()
    mobidata()
    stuttgart()
    norddeutschland()
    osten()
    sachsen()
    rheinland_pfalz()
    staedte()
    luxemburg()
    staedte_2()
    bw_meldungen()
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
