# Weitere Datenquellen – Recherche (Stand 2026-10-02)

Planungsgrundlage für die Erweiterung **nach v0.1.0**. Ziel: mehr Abdeckung außerhalb von Baden-Württemberg.

**„Geprüft“** heißt: am 2026-10-02 live ohne Anmeldung abgerufen, Format und Lizenz bestätigt. **Noch nicht** analysiert: Datenfelder, Datumsformate, tatsächlicher Aktualisierungsrhythmus. Vor jeder Zusage wie bei Stuttgart zuerst Fixtures ziehen (`tools/fetch_fixtures.py` erweitern) und gegen die Daten entwickeln (CLAUDE.md, Regel 1).

## Kernerkenntnisse

1. **Bundesländer liefern fast nur über die Mobilithek (DATEX II).** Der Abruf dort erfordert meist Abonnement + **eigenes X.509-Client-Zertifikat je Datenabnehmer** ([Technische Schnittstellenbeschreibung](https://mobilithek.info/cms/assets/1e4c3f3d-e6c5-4844-a11d-7dd589bb9133?download=)). Für eine HACS-Integration nicht praktikabel: Jeder Nutzer müsste sich selbst registrieren; ein mitgeliefertes Zertifikat weiterzugeben wäre unzulässig. Ausnahme nur, wenn ein Angebot ausdrücklich ohne Registrierung abrufbar ist – pro Angebot prüfen.
2. **Städte sind ergiebiger.** Viele veröffentlichen offen – oft wie Stuttgart über GeoServer/WFS mit GeoJSON-Ausgabe. Das spricht für einen **generischen Stadt-Provider** mit einer kleinen, deklarativen Feldzuordnung je Stadt statt eigenem Code pro Stadt (Felder für Titel, Straße, Start/Ende, Auswirkung, ID; Datums-Parser wiederverwenden aus `providers/stuttgart.py`).

## Bundesländer

| Land | Offen ohne Anmeldung? | Details / Endpunkt |
|---|---|---|
| Baden-Württemberg | ✅ umgesetzt | MobiData BW |
| **Sachsen** | ✅ geprüft | Landesweit (Autobahn bis Kreisstraße), Vollsperrungen > 1 Tag, halbseitige Sperrungen, Einbahnregelungen. GeoJSON als ZIP: `http://www.list.smwa.sachsen.de/gdi/download/baustelleninfo/Baustelleninfo_Sachsen_geojson.zip`, WMS: `https://geodienste.sachsen.de/wms_list_baustellen/guest?` ([Datendienste](https://www.baustellen.sachsen.de/baustellendaten-dienste-3997.html), [LASuV](https://www.lasuv.sachsen.de/baustelleninfosys-7937.html)). Grenzgebiet inkl. Thüringer Daten. **Bester Kandidat für ein weiteres Land.** |
| Berlin, Hamburg | ✅ geprüft | siehe Städte |
| Bayern | ❌ Mobilithek | BayernInfo (VIZ-BY) führt Autobahn, Bundes-, Staats-, Kreis- und Gemeindestraßen zusammen – sehr gute Daten, aber DATEX II nur über Mobilithek ([BayernInfo](https://www.bayerninfo.de/en/about-bayerninfo-1/data-offer/private-transport-data), [GovData](https://www.govdata.de/suche/daten/baustellenmeldungen-in-bayern), [Mobilithek-Praxisbeispiel](https://mobilithek.info/blog/praxisbeispiel-verkehrsmanagement-bayern)) |
| Hessen | ❌ Mobilithek | Hessen Mobil; keine offene Direktschnittstelle gefunden |
| Rheinland-Pfalz | ❌ Mobilithek | SperrinfoSys → Mobilithek ([Mobilitätsatlas](https://lbm.rlp.de/themen/verkehrssteuerung/mobilitaetsatlas)) |
| Niedersachsen | ❌ Mobilithek | NLStBV-Datensätze zu Langzeitbaustellen bei GovData gelistet – Zugang prüfen ([NLStBV](https://www.strassenbau.niedersachsen.de/startseite/service/downloads/), [GovData](https://data.gov.de/suche?publisher=Nieders%C3%A4chsische+Landesbeh%C3%B6rde+f%C3%BCr+Stra%C3%9Fenbau+und+Verkehr)) |
| NRW (Landesstraßen) | ❌ / unklar | Straßen.NRW koordiniert über TIC Kommunal; offen sind vor allem Städte ([Open.NRW](https://ckan-open-nrw.nrw.de/en/dataset/baustellen-ms)) |
| Brandenburg | ❌ Karte / Mobilithek | [Baustellen-Informationssystem](https://service.brandenburg.de/service/de/aktuelles/detail/~19-02-2025-baustellen-informationssystem) |
| Schleswig-Holstein | ❌ Karte | DANord ([LBV.SH](https://www.schleswig-holstein.de/DE/landesregierung/ministerien-behoerden/LBVSH/Service/Baustellen)) |
| Mecklenburg-Vorpommern | ❌ Mobilithek | [LS M-V Mobilitätsdaten](https://www.strassen-mv.de/de/verkehrsinfos/mobilit%C3%A4tsdaten/), [GeoPortal M-V](https://www.geoportal-mv.de/portal/Suche/Metadatenuebersicht/Details/Verkehrsinformationen%20Landesamt%20f%C3%BCr%20Stra%C3%9Fenbau%20und%20Verkehr%20M-V/351b7557-8f54-4989-aa72-f4727d0ed59e) |
| Thüringen, Sachsen-Anhalt, Saarland, Bremen | ❌ nichts Offenes gefunden | Webseiten bzw. Mobilithek ([VMZ Bremen](https://vmz.bremen.de/baustellen/aktuell)) |

## Städte (die größten zuerst)

| Stadt | Stand | Lizenz | Endpunkt / Details |
|---|---|---|---|
| **Berlin** | ✅ geprüft (GeoJSON live) | DL-DE-BY 2.0 | `https://api.viz.berlin.de/geoserver/mdhwfs/wfs?service=WFS&version=1.1.0&request=GetFeature&typename=baustellen_sperrungen&outputFormat=application/json&srsName=EPSG:4326` – nur Meldungen „von besonderem verkehrlichem Interesse“ (redaktionell, VIZ) ([GovData](https://www.govdata.de/suche/daten/baustellen-sperrungen-und-sonstige-storungen-von-besonderem-verkehrlichem-interesse)) |
| **Hamburg** | ✅ geprüft (WFS) | prüfen | `https://geodienste.hamburg.de/hh_wfs_baustellen` – Baustellenprofile aus „Bauweiser“, GeoJSON-Ausgabe verfügbar ([Metaver](https://metaver.de/trefferanzeige?docuuid=F67E2668-DD51-4BE1-B176-7719FFB946CD)) |
| **München** | ✅ geprüft | DL-DE-BY 2.0 | WFS `https://geoportal.muenchen.de/geoserver/mor_wfs/ows` (GeoJSON/CSV/GML), täglich, Vorschau 4 Wochen; Schwerpunkt Innenstadt + Hauptstraßen ([Open Data](https://opendata.muenchen.de/dataset/baustellen_4_weeks_opendata)) |
| **Köln** | ✅ geprüft | DL-DE-Zero 2.0 | WFS `https://geoportal.stadt-koeln.de/wss/service/baustellen_wfs/guest`; zusätzlich „Verkehrsbeeinträchtigungen“ als JSON ([Offene Daten Köln](https://offenedaten-koeln.de/dataset/baustellen-koeln)) |
| Frankfurt | ⚠️ ungeprüft | prüfen | „Verkehrsmeldungen“ (XML/API) im Portal; DATEX II über die Mobilitätsdatenplattform der Verkehrszentrale ([Offene Daten](https://www.offenedaten.frankfurt.de/dataset?tags=Verkehrsdaten), [Mainziel](https://mz.firmazwei.de/wir-fuer-sie/datenweitergabe)) |
| Stuttgart | ✅ umgesetzt | CC BY 4.0 | |
| Düsseldorf | ❓ | | nichts gefunden |
| **Leipzig** | ✅ geprüft | prüfen | WFS `https://geodienste.leipzig.de/l3/OpenData/...` (GeoJSON/CSV), Verkehrsraumeinschränkungen als Punkte, laufend ([Open Data](https://opendata.leipzig.de/dataset/verkehrsraumeinschrankungen-punkte-stadt-leipzig)) |
| Dortmund, Essen | ❓ | | nichts gefunden; Ruhr-Portal enthält nur Herne/Duisburg |
| Dresden | ⚠️ ungeprüft | | Verkehrseinschränkungen im Themenstadtplan, WFS-Infrastruktur vorhanden ([Themenstadtplan](https://www.dresden.de/de/rathaus/dienstleistungen/TSP-Themenuebersicht.php)) |
| Hannover, Nürnberg, Bremen | ❌ | | nur Webseiten/Karten |
| Duisburg | ⚠️ ungeprüft | | [opendata.rvr.ruhr](https://opendata.rvr.ruhr/dataset/baustellen-in-duisburg) |

Kleinere Städte mit offenen GeoJSON-Daten:

- **Karlsruhe** ✅ geprüft – CC BY 4.0; WFS `https://mobil.trk.de/geoserver/TBA/ows` (aktuell + Vorschau), DATEX II `https://mobil.trk.de/datex/datex.xml`, GraphQL `https://mobil.trk.de/graphiql` ([Transparenzportal](https://transparenz.karlsruhe.de/dataset/baustellen)). Liegt in BW – prüfen, ob schon in MobiData enthalten.
- **Münster** – GeoJSON ([Open Data](https://opendata.stadt-muenster.de/dataset/baustellen))
- **Bonn** – GeoJSON, tagesaktuell + Planung 30 Tage/1 Jahr ([Open.NRW](https://ckan.open.nrw.de/dataset/baustellen-tagesaktuell-mit-ortsangabe-in-bonn-bn))
- **Herne** ✅ geprüft – WFS `https://geodaten.herne.de/geoserver/verkehr/baustellen` ([opendata.ruhr](https://opendata.ruhr/dataset/baustellen))
- **Rostock** – GeoJSON ([OpenData.HRO](https://www.opendata-hro.de/dataset/baustellen))

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

## Empfohlene Reihenfolge (nach v0.1.0)

1. **Generischer Stadt-Provider** (WFS/GeoJSON + Feldzuordnung je Stadt) mit **Berlin, Hamburg, München** – größte Reichweite. Danach Köln, Leipzig, Münster, Bonn u. a. überwiegend per Konfiguration.
2. **Sachsen** als zweites Bundesland (GeoJSON-ZIP; Download-Größe und Aktualisierungsrhythmus prüfen, ETag/Last-Modified nutzen).
3. **Mobilithek-Länder** (Bayern, Hessen, …) erst, wenn ein Zugang ohne Zertifikat je Nutzer existiert – Anfrage beim Mobilithek-Betreiber bzw. den Ländern wäre der nächste Schritt.

Querschnittsthemen bei mehr Quellen: Deduplizierung nur bei gleicher Straße (Handover Abschnitt 6), Attribution je Quelle (`const.ATTRIBUTION`), Quellenauswahl im Config-Flow gruppieren (Länder/Städte), Standardauswahl nach HA-Standort.
