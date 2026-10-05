# Weitere Datenquellen – Recherche (Stand 2026-10-05)

Planungsgrundlage für die Erweiterung **nach v0.1.0**. Ziel: mehr Abdeckung außerhalb von Baden-Württemberg.

**Legende:** ✅ geprüft = live ohne Anmeldung abgerufen, Format bestätigt · 🔎 Probe analysiert = zusätzlich Felder/Umfang ausgewertet · ⚠️ teilweise/ungeprüft · ❌ nicht nutzbar (nur Mobilithek mit Freigabe bzw. nur Webseite) · ❓ nichts gefunden (Suche nicht abschließend).

Vor jeder Zusage wie bei Stuttgart zuerst Fixtures ziehen (`tools/fetch_fixtures.py` erweitern) und gegen die Daten entwickeln (CLAUDE.md, Regel 1). Rohproben liegen bisher nur lokal.

## Kernerkenntnisse

1. **Mobilithek: überwiegend für HACS ungeeignet, aber nicht vollständig.** Vollständiger Katalog-Scan am 2026-10-05 (Suche per `POST https://mobilithek.info/mdp-api/mdp-msa-metadata/v2/offers/search` mit `{"searchString": …, "page": 0, "size": 100}`, Details per `GET …/v2/offers/<id>`): **76** Baustellen-/Verkehrsinfo-Angebote, davon **47 mit `providerApprovalRequired=True`** und ohne direkte `accessUrl` (Abruf nur mit Abonnement, Freigabe und X.509-Client-Zertifikat, [Schnittstellenbeschreibung](https://mobilithek.info/cms/assets/1e4c3f3d-e6c5-4844-a11d-7dd589bb9133?download=)) – darunter Bayern, Hessen Mobil, Thüringen, Bremen, Saarland, NRW/LVZ, Düsseldorf, Hannover, Kassel, Köln-DATEX, Leipzig-DATEX. **29 Angebote sind ohne Freigabe mit direkter Adresse** gelistet – daraus stammen die Funde Schleswig-Holstein-Nord-WFS, Rheinland-Pfalz, Kiel, Rhein-Main (ivm), Landkreis Lüneburg. Das Skript dazu kann die Recherche jederzeit wiederholen.
2. **Offene, landesweite Schnittstellen gibt es für neun weitere Bundesländer:** Sachsen (GeoJSON-ZIP), Brandenburg (WFS), Sachsen-Anhalt (WFS), Rheinland-Pfalz (WFS Mobilitätsatlas) sowie über **einen norddeutschen Gemeinschafts-WFS** Schleswig-Holstein, Mecklenburg-Vorpommern, Niedersachsen und Hamburg; Berlin über die VIZ. Ohne offene Landesquelle bleiben **Bayern, Hessen, NRW, Thüringen, Bremen, Saarland** (dort nur einzelne Städte).
3. **Viele Städte veröffentlichen offen**, überwiegend per GeoServer-WFS mit GeoJSON-Ausgabe, einige per ArcGIS-REST. Für Streckenwacht naheliegend: **ein generischer WFS/GeoJSON-Provider** mit deklarativer Feldzuordnung je Quelle, später ein zweiter Adapter für ArcGIS-REST.
4. **Fundstelle:** Die GovData-CKAN-API (`https://www.govdata.de/ckan/api/3/action/package_search?q=baustellen&rows=1000`) bündelt viele kommunale Portale – gut zum Wiederholen der Recherche.

## Bundesländer

| Land | Stand | Details |
|---|---|---|
| Baden-Württemberg | ✅ umgesetzt | MobiData BW |
| **Sachsen** | ✅ | Landesweit (Autobahn bis Kreisstraße), GeoJSON-ZIP `http://www.list.smwa.sachsen.de/gdi/download/baustelleninfo/Baustelleninfo_Sachsen_geojson.zip`, WMS `https://geodienste.sachsen.de/wms_list_baustellen/guest` ([Datendienste](https://www.baustellen.sachsen.de/baustellendaten-dienste-3997.html)). Grenzgebiet inkl. Thüringer Daten. |
| **Brandenburg** | ✅ 🔎 | WFS `https://isk.geobasis-bb.de/ows/baustelleninfo_wfs`, Layer `app:baustelleninfo`, `OUTPUTFORMAT=application/geo+json`. Bundes-, Landes- und Kreisstraßen. Probe: 417 Abschnitte (LineString), 1,3 MB, ISO-Daten. |
| **Sachsen-Anhalt** | ✅ 🔎 | WFS `https://service.ifak.eu/sperrinfo/wfs` (Sperrinfo LSA), Layer `ms:roadworks` (Flächen), `ms:roadwork_symbols` (Punkte), `ms:diversions` (Umleitungen); **`OUTPUTFORMAT=geojson`** (nicht `application/json`). Probe: 105 Baustellen inkl. Gemeindestraßen, ISO-Daten, Umleitungstext. |
| **Norddeutscher WFS** (SH, MV, NI, HH) | ✅ 🔎 | `https://dienste.gdi-sh.de/WFS_SH_Baustelleninformationen`, `OUTPUTFORMAT=GEOJSON`, `SRSNAME=EPSG:4326`. Layer (Präfix `Baustelleninformationen:`): `Baustellen_SH` (796), `Baustellenpunkte_SH` (1521), `Baustellen_MV` (182), `Baustellen_Niedersachsen` (134, **landesweit**, v. a. Bundesstraßen), `Baustellenpunkte_Niedersachsen`, `Baustellen_FHH` (Hamburg, 202), `Baustellen_Autobahn` (195, Norden), `Umleitungsstrecken` (189), `Verkehrsstoerungen` (8), `Verkehrslagen` (3354), `Baustellenpunkte_Norderstedt`. Zeiten teils als Freitext („18.05.2026 17:04 Uhr bis 20.12.2026 17:04 Uhr“), MV mit `Baubeginn`/`Bauende`. **Größter Einzelfund: vier Länder über eine Schnittstelle.** |
| **Rheinland-Pfalz** | ✅ 🔎 | WFS `https://maps.mobilitaetsatlas.de/geoserver/ows`, Layer `mwvlw:baustelle` (+ `mwvlw:umleitung`), `outputFormat=application/json`. 3669 Einträge, aber gemischte Quellen (`quelle`): Autobahn GmbH 1774, **Verkehrsbehörden in RLP 988**, Verkehrsministerium BW 551, Stadt Karlsruhe 209, Straßenbauverwaltung Luxemburg 147 → nach `quelle` filtern. ISO-Zeiten (`von`/`bis`), `sperrungstyp` (roadClosed, maintenanceWork …), Straßenklasse. |
| Berlin, Hamburg | ✅ 🔎 | siehe Städte (Stadtstaaten); Hamburg zusätzlich im norddeutschen WFS |
| Bayern | ❌ | Nur Mobilithek, Lizenz „eingeschränkte Nutzung, kostenfrei“. Die BayernInfo-ZIP-Datei bei open.bydata ist nur eine Referenzdatei, kein aktueller Datenstand. |
| Niedersachsen | ✅ | über den norddeutschen WFS (s. o.); das NLStBV-Angebot in der Mobilithek braucht Freigabe |
| Thüringen, Bremen | ❌ | nur Mobilithek mit Freigabe |
| NRW (Landesstraßen) | ❌ | LVZ.NRW nur Mobilithek mit Freigabe; offen sind viele Städte |
| Hessen | ❌ | Hessen Mobil nur C-ITS-Angebot in der Mobilithek; offen ist Frankfurt |
| Saarland | ❌ | LfS-Angebote nur Mobilithek mit Freigabe |
| Region Frankfurt RheinMain | ⚠️ | ivm, Mobilithek ohne Freigabe: `https://ivm.traff-x.de/gip-service/rest/xb/export/TrafficMessages_IVM` (+ `StrategicRouting_IVM` für Umleitungen) – beim Test keine Verbindung (Timeout), erneut prüfen |
| Landkreis Lüneburg | ⚠️ | Mobilithek ohne Freigabe, verweist nur auf `https://geoportal.lklg.net` |

## Die 50 größten Städte

BW-Städte sind teilweise schon über MobiData BW abgedeckt (Gemeindestraßen nur vereinzelt).

| # | Stadt | Stand | Quelle / Endpunkt |
|---|---|---|---|
| 1 | **Berlin** | ✅ 🔎 | VIZ: WFS `https://api.viz.berlin.de/geoserver/mdhwfs/wfs` (`baustellen_sperrungen`) oder direkt `https://api.viz.berlin.de/daten/baustellen_sperrungen_viz.json`; DL-DE-BY 2.0 |
| 2 | **Hamburg** | ✅ 🔎 | WFS `https://geodienste.hamburg.de/hh_wfs_baustellen` (`de.hh.up:baustelle`); außerdem `Baustellen_FHH` im norddeutschen WFS |
| 3 | **München** | ✅ 🔎 | WFS `https://geoportal.muenchen.de/geoserver/mor_wfs/ows` (`mor_wfs:baustellen_opendata`); DL-DE-BY 2.0 |
| 4 | **Köln** | ✅ | WFS `https://geoportal.stadt-koeln.de/wss/service/baustellen_wfs/guest` (DL-DE-Zero); zusätzlich ArcGIS „Verkehrskalender“ `https://geoportal.stadt-koeln.de/arcgis/rest/services/verkehr/verkehrskalender/MapServer/0/query?where=1%3D1&outFields=*&f=geojson` |
| 5 | **Frankfurt** | ✅ 🔎 | WFS `https://geowebdienste.frankfurt.de/Baustellen`, Layer `opendata_verkehr:Baustellen` und `opendata_verkehr:Verkehrsmeldungen` |
| 6 | Stuttgart | ✅ umgesetzt | |
| 7 | Düsseldorf | ❓ | |
| 8 | **Leipzig** | ✅ | WFS `https://geodienste.leipzig.de/l3/OpenData/wfs` (`OpenData:verkehrsraumeinschraenkungen`, `…_point`) |
| 9 | **Dortmund** | ✅ 🔎 | `https://open-data.dortmund.de/api/v2/catalog/datasets/fb66-baustellen-tagesaktuell/exports/geojson` (+ `…-geplant`, Flächen-Varianten); DL-DE-Zero |
| 10 | Essen | ❓ | |
| 11 | Bremen | ❌ | nur Mobilithek / Webseite VMZ (Umland über Niedersachsen-Layer) |
| 12 | Dresden | ⚠️ | über Sachsen landesweit (Bundes- bis Kreisstraßen); städtische Daten nur im Themenstadtplan |
| 13 | Hannover | ⚠️ | städtische Verkehrsmeldungen nur Mobilithek; Bundesstraßen über den norddeutschen WFS (Niedersachsen) |
| 14 | Nürnberg | ❓ | nur Webseite |
| 15 | **Duisburg** | ✅ | ArcGIS-REST `https://geoportal2.duisburg.de/arcgisserver/rest/services/Masterportal/MP_Verkehrsportal/MapServer/2/query` („nächste 7 Tage“) |
| 16 | **Bochum** | ✅ | ArcGIS-REST `https://geoservicekkm.bochum.de/arcgis/rest/services/maponline/Baustellen/MapServer` |
| 17 | Wuppertal | ❓ | |
| 18 | Bielefeld | ⚠️ | „Verkehrsmeldungen“ (CSV/XML) bei open-data.bielefeld.de, ungeprüft |
| 19 | **Bonn** | ⚠️ | GeoJSON tagesaktuell + Planung ([Open.NRW](https://ckan.open.nrw.de/dataset/baustellen-tagesaktuell-mit-ortsangabe-in-bonn-bn)), Endpunkt ungeprüft |
| 20 | **Münster** | ✅ | GeoJSON ([Open Data](https://opendata.stadt-muenster.de/dataset/baustellen)) |
| 21 | Mannheim | ⚠️ | nur über MobiData BW (teilweise) |
| 22 | **Karlsruhe** | ✅ | WFS `https://mobil.trk.de/geoserver/TBA/ows` (aktuell + Vorschau), DATEX, GraphQL; CC BY 4.0 |
| 23–26 | Augsburg, Wiesbaden, Mönchengladbach, Gelsenkirchen | ❓ | |
| 27 | **Aachen** | ✅ | WFS `https://bsis.aachen.de/geoserver/ows` (`BSIS:PUNKTE_ALLE`, GeoJSON) |
| 28 | Braunschweig | ❓ | |
| 29 | **Kiel** | ✅ | ArcGIS-WFS `https://ims.kiel.de/geodatenextern/services/Stadtplan/LHKielWmsWfs/MapServer/WFSServer`, Layer `Baustellen`, `Baustellen_L_-_Aktuell`, `…_Zukunft` u. a., `outputFormat=geoJSON` (Layer `Baustellen` beim Test leer – Teil-Layer prüfen); zusätzlich im norddeutschen WFS |
| 30 | Chemnitz | ⚠️ | über Sachsen landesweit |
| 31 | **Halle (Saale)** | ✅ | über Sachsen-Anhalt landesweit (inkl. Gemeindestraßen) |
| 32 | **Magdeburg** | ✅ | über Sachsen-Anhalt landesweit (inkl. Gemeindestraßen) |
| 33 | Freiburg | ⚠️ | nur über MobiData BW (teilweise) |
| 34–35 | Krefeld, Mainz | ❓ | |
| 36 | Lübeck | ⚠️ | Datensatz „Baustellen/Maßnahmen“ erwähnt, maschinenlesbarer Zugang nicht bestätigt |
| 37 | Erfurt | ❌ | Thüringen nur Mobilithek |
| 38 | Oberhausen | ❓ | |
| 39 | **Rostock** | ✅ | `https://geo.sv.rostock.de/download/opendata/baustellen/baustellen.json` (auch CSV/GML) |
| 40–41 | Kassel, Hagen | ❓ | |
| 42 | Potsdam | ⚠️ | über Brandenburg landesweit (nur Bundes-/Landes-/Kreisstraßen); Stadt nur Webseite |
| 43 | Saarbrücken | ❓ | |
| 44–49 | Hamm, Ludwigshafen, Oldenburg, Mülheim, Osnabrück, Leverkusen | ❓ | |
| 50 | Heidelberg / Darmstadt | ⚠️ / ❓ | Heidelberg-JSON-Adresse aus dem Katalog liefert 404 |

Weitere offene Quellen kleinerer Städte: **Ingolstadt** (GeoJSON, 14 Tage, **EPSG:25832** – Umrechnung nötig), **Herne** (WFS), **Soest** (GeoJSON), **Wesel** (CSV/Shape), **Norderstedt** (WFS `https://geoservice.norderstedt.de/geoserver/vms/ows`, `vms:stvkinfoweb`), Trebbin (WFS).

## Vorerkundung Berlin, Hamburg, München (2026-10-05)

Echte Antworten abgerufen (nur lokal im Scratchpad, noch keine Fixtures im Repo). Alle drei: GeoServer-WFS, GeoJSON in WGS84 per `srsName=EPSG:4326`, **keine ETags** (bedingte Abrufe wie bei Autobahn/MobiData nicht möglich), Datumsangaben überwiegend `dd.mm.yyyy`.

| | Berlin (VIZ) | Hamburg (Bauweiser) | München |
|---|---|---|---|
| Abruf | `typename=baustellen_sperrungen`, `outputFormat=application/json` | `typeNames=de.hh.up:baustelle`, `outputFormat=application/geo+json` (WFS 2.0) | `typeName=mor_wfs:baustellen_opendata`, `outputFormat=application/json` |
| Umfang | 387 Meldungen, ~90 KB gzip (500 KB roh) | 148 Maßnahmen, 355 KB (kein gzip) | 5542 Einträge, ~860 KB gzip (**5,3 MB roh**) |
| Geometrie | `GeometryCollection` (Punkte/Linien) | `Point` | `Polygon` / `MultiPolygon` |
| Art | `subtype`: Baustelle 207, Sperrung 124, Bauarbeiten 20, Gefahr 17, Störung 14, Unfall 3, Fahrstreifensperrung 2 | keine Typisierung; Flags `isthotspot`, `istoepnveingeschraenkt`, `istparkraumeingeschraenkt` | `art`: Baumaßnahme 3048, **Vorübergehendes Haltverbot 2494** |
| Schwere | `severity`: Vollsperrung 54, Fahrtrichtungssperrung 44, keine Sperrung 227 | nur Freitext (`umfang`, `umleitungsbeschreibung`) | `betroffene_bereiche` (Gehweg/Fahrbahn/Radweg), `beeintraechtigung` (Freitext) |
| Zeiten | `validity` = JSON-String `{"from": "dd.mm.yyyy HH:MM", "to": … \| null}` | `baubeginn`, `bauende` (`dd.mm.yyyy`) | `beginn_datum_kombiniert`, `ende_datum_kombiniert` (`dd.mm.yyyy`) |
| Stabile ID | `id` (numerisch) | keine eigene – `titel` ist eindeutig, Feature-ID prüfen | `fachliche_id` nur bei 309 Einträgen; sonst Feature-ID prüfen |
| Charakter | redaktionell kuratiert, verkehrsrelevant, inkl. Unfälle/Störungen; **enthält auch 75 Autobahn-Meldungen** (Berlin + Brandenburger Umland) → Überschneidung mit der Autobahn-API | Großprojekte mit langen Laufzeiten (ähnlich Stuttgart), viel Beschreibungstext | sehr feinkörnig inkl. Gehweg-Baustellen und Halteverbote; nur 1132 Baumaßnahmen betreffen die Fahrbahn |

**Wichtige Befunde:**
- **WFS kann serverseitig filtern** – anders als die Autobahn-API. München getestet: `CQL_FILTER=art='Baumaßnahme'` halbiert die Daten; `BBOX(shape, lon_min, lat_min, lon_max, lat_max, 'EPSG:4326')` liefert nur den Ausschnitt (Achsenreihenfolge **Länge, Breite**; Geometriefeld heißt je Server anders, z. B. `shape`, steht in `geometry_name`). Ein Stadt-Provider sollte pro Bereich nur dessen Begrenzungsrechteck abfragen.
- **Berlin passt am besten** zum Streckenwacht-Modell: klare Arten und Sperrgrade, Zeitfenster mit Uhrzeit, kompakt. Erster Kandidat.
- **München** braucht einen Relevanzfilter (nur `Baumaßnahme` mit `Fahrbahn`, Halteverbote weglassen), sonst überflutet es Bereiche mit Gehweg- und Parkmeldungen.
- **Hamburg** ist gröber (Projektebene) und eher eine Ergänzung.
- Ein **generischer Provider** ist realistisch: gleiche Technik (WFS/GeoJSON), Unterschiede nur in Feldzuordnung, Typ-/Schwere-Abbildung und optionalem Vorfilter.

## Vorerkundung Brandenburg, Sachsen-Anhalt, Frankfurt, Dortmund (2026-10-05)

| | Brandenburg | Sachsen-Anhalt | Frankfurt | Dortmund |
|---|---|---|---|---|
| Umfang | 417 Abschnitte, 1,3 MB | 105 Baustellen, 65 KB | 269 Baustellen (316 KB) + 5 Verkehrsmeldungen | 164 tagesaktuell, 12 KB |
| Geometrie | `LineString` | `Point` (Flächen im Layer `ms:roadworks`) | `MultiPolygon` / `MultiLineString` | `Point` |
| Art / Schwere | `Art` (Bauabschnitt/Sperrung), `Status_Fahrstreifen`, `Anzahl_Fahrstreifen_gesperrt` | `kind_description`: Vollsperrung, halbseitige Sperrung, Verkehrsraumeinschränkung …; `street_class` (L/K/G …) | `sperrung` 0/1, `meldung` (Baustelle/Wanderbaustelle), englische Texte vorhanden | Freitext im Titel („// Vollsperrung“) |
| Zeiten | `Baustellen_Beginn`/`_Ende` (ISO) | `from_date`/`to_date` (ISO) | `startevent`/`endevent` (ISO mit Uhrzeit, UTC) | `von`/`bis` (ISO) |
| ID | `ID` | `feature_id` | `baustellennummer` | – (prüfen) |
| Extras | Straßennummer, Länge, Netzknoten | Ort, Ursache, **Umleitung** | Verkehrsmeldungen inkl. Veranstaltungen (z. B. Marathon) | Auftraggeber, Stadtbezirk |

Alle vier sind sauber strukturiert und kommen ohne Freitext-Datumsparsing aus.

## Empfohlene Reihenfolge (nach v0.1.0)

1. **Generischer WFS/GeoJSON-Provider** mit Feldzuordnung je Quelle und optionalem Vorfilter (CQL) bzw. Begrenzungsrechteck je Bereich. Erste Quellen nach Reichweite: **norddeutscher WFS (SH, MV, NI, HH – vier Länder auf einmal)**, **Rheinland-Pfalz** (nach `quelle` filtern), **Berlin, Brandenburg, Sachsen-Anhalt, Frankfurt**, dann **München** (mit Relevanzfilter), Dortmund, Leipzig, Köln, Aachen, Karlsruhe, Münster, Rostock, Kiel.
2. **Sachsen** (GeoJSON-ZIP; Größe und Rhythmus prüfen, `Last-Modified` nutzen).
3. **ArcGIS-REST-Adapter** für Duisburg, Bochum und Kölns Verkehrskalender.
4. **Mobilithek-Länder mit Freigabepflicht** (Bayern, Hessen, NRW, Thüringen, Bremen, Saarland) erst, wenn ein Zugang ohne Zertifikat und Freigabe je Nutzer existiert. Alternativen für diese Lücken siehe nächster Abschnitt.

## Weitere Ideen für mehr Abdeckung

- **Eigener API-Schlüssel des Nutzers für kommerzielle Verkehrsdienste** (z. B. TomTom Traffic Incidents, HERE Traffic): bundesweit inkl. Staus, Sperrungen und Baustellen per Umkreisabfrage; kostenlose Kontingente vorhanden; viele HA-Nutzer haben durch die Fahrzeit-Integrationen bereits einen Schlüssel. Wäre der größte Hebel für Bayern, Hessen, NRW und Thüringen – Lizenz- und Nutzungsbedingungen je Anbieter prüfen, optionaler Provider.
- **Nachbarländer für Grenzpendler:** Luxemburg ist im RLP-Layer bereits enthalten; Niederlande (NDW, offene DATEX-II-Feeds), Österreich, Schweiz, Frankreich, Dänemark haben nationale Open-Data-Zugangspunkte – je Land prüfen.
- **Landkreise:** einzelne offene Quellen (Lüneburg); andere (Böblingen, Heidekreis, Hohenlohekreis, Kreis Unna) nur Mobilithek mit Freigabe.
- **Verworfen:** OpenStreetMap-Baustellentags (statisch, unvollständig), Polizei-Verkehrsmeldungen (unstrukturiert), eigener Server als Mobilithek-Abnehmer zum Weiterverteilen (Serverbetrieb, rechtliche und organisatorische Pflichten – widerspricht dem Ansatz ohne Server).

Querschnittsthemen bei mehr Quellen: Überschneidungen (Berlin enthält Autobahnmeldungen, MobiData einzelne A-Abschnitte) – Deduplizierung nur bei gleicher Straße (`ENTWICKLUNG.md` Abschnitt 3); Attribution je Quelle (`const.ATTRIBUTION`); Quellenauswahl im Config-Flow gruppieren (Länder/Städte) und nach HA-Standort vorauswählen; keine der neuen Quellen liefert ETags – Abrufintervall bzw. Serverfilter beachten.
