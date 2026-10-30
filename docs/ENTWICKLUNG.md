# Streckenwacht – Entwicklerdokumentation

Wie Streckenwacht gebaut ist, was man über die Datenquellen wissen muss und warum Dinge so entschieden wurden. **Maßgeblich ist der Code**; dieses Dokument erklärt, was dort nicht steht. Weitere Dokumente: [`DATENQUELLEN.md`](DATENQUELLEN.md) (Recherche zu neuen Quellen), [`BRAND.md`](BRAND.md) (Bilder, Farben).

## 1. Architektur

### Konfiguration

- **Ein Config-Entry** „Streckenwacht“ (`single_config_entry`): Abrufintervall (10–60 min, Standard 15), Option „Staumeldungen (INRIX) einbeziehen“ (Standard an). Nur UI, kein YAML. Abgefragt werden die Quellen, die irgendein Bereich nutzt.
- **Ein Config-Subentry `area` je Beobachtungsbereich**, eingerichtet als Assistent `user`/`reconfigure` → `sources` → `roads` → `directions`:
  - Mittelpunkt und Radius per Karte (Standard 10 km, höchstens 100 km – `geo.py` rechnet flach, das ist bis ~100 km genau).
  - Meldungsarten (`types`, seit 0.3.0): gefiltert wird in `ObservationArea.contains()`, also für alle Entities des Bereichs; alle gewählt wird als `None` gespeichert, damit später hinzukommende Arten automatisch dabei sind.
  - Quellen pro Bereich: angeboten werden die Autobahn und die Quellen, deren Region (`const.SOURCE_REGIONS`, je Land ein paar Rechtecke) den Kreis berührt (`model.sources_for_circle`), alle vorausgewählt; beim Ändern bleiben gespeicherte Quellen wählbar. Nur Autobahn verfügbar → Schritt entfällt.
  - **Migration (Entry-Minor-Version 2, ab 0.2.1):** Bis 0.2.0 hielt der Entry eine globale Quellenliste und Bereiche ohne eigene Liste zeigten alle. `async_migrate_entry` schreibt diese Liste in solche Bereiche und entfernt sie aus den Optionen. Der Fingerprint der Ereignisänderung ändert sich dadurch einmal → still neu gelernt.
  - Autobahnen (nur wenn die Autobahn-Quelle aktiv ist) und Stau-Schwelle in Minuten (nur mit INRIX, Standard 10).
  - Optional Fahrtrichtungen: Auswahl aus den real vorkommenden „Start -> Ziel“-Richtungen; Anschlussstellen und Meldungen ohne Richtung bleiben immer sichtbar.
- `area_subentries()` ersetzt `get_subentries_of_type()`, das es in HA 2026.3 noch nicht gibt. Mindestversion ist 2026.3 (`hacs.json`), weil HA erst ab dort die Brand-Bilder aus `custom_components/streckenwacht/brand/` lädt.

### Datenfluss

- **Ein `DataUpdateCoordinator` pro Quelle** (`coordinator.py`), `always_update=False`. Er lädt einmal pro Abruf alles, was alle Bereiche zusammen brauchen (Autobahn: Vereinigungsmenge der gewählten Autobahnen; MobiData: eine landesweite Datei; Stuttgart: zwei Layer; Norddeutschland: nur die Layer, deren Region einen Bereich berührt, per `BBOX` auf einen Ausschnitt begrenzt). Jeder Bereich filtert lokal über `ObservationArea.contains()`; Abstand zu Linien wird zum Segment gemessen, nicht nur zu den Stützpunkten.
- **Provider** (`providers/`) sind reines Python ohne HA-Importe, bekommen nur eine `aiohttp`-Session und werfen bei jedem Fehler `ProviderError`. Bedingte Abrufe per ETag (`If-None-Match`/304) stecken in der Basisklasse. WFS-Quellen ohne ETag erben von `providers/wfs.py`: Abruf je Layer mit Ausschnitt, auf ein 0,5°-Raster gerundet (etwa 55 × 35 km), damit der Server nur die grobe Region erfährt – Entscheidung des Projektinhabers 2026-10-14 statt genauem Ausschnitt (weniger Daten, aber Bereich erkennbar) oder ganzen Layern (bis 100 MB/Tag).
- **Fehler** betreffen nie andere Quellen. Nach 3 Fehlschlägen in Folge entsteht ein Hinweis unter *Reparaturen*, beim nächsten Erfolg verschwindet er. Entities behalten die letzten Daten und nennen ausgefallene Quellen im Attribut `unavailable_sources`.
- Alle Requests mit User-Agent `Streckenwacht/<version> (+https://github.com/streckenwacht/integration)`.

### Module

| Datei | Inhalt |
|---|---|
| `model.py` | `StreckenwachtEvent`, `Period`, `ObservationArea`, `EventType` (`roadworks`, `closure`, `traffic_jam`, `accident`, `warning`) |
| `geo.py` | Abstände Punkt ↔ GeoJSON |
| `summary.py` | Zeitabhängige Sichten für die Entities (aktiv, Störungen, Kalendereinträge, größter Reisezeitverlust) |
| `changes.py` | „neu/beendet“-Erkennung inkl. Stau-Glättung (Abschnitt 2, Autobahn) |
| `known_events.py` | Speichert pro Bereich die bekannten Meldungen (`streckenwacht.<entry_id>.known_events`), damit Neustarts nichts erneut melden |
| `providers/*.py` | Abruf und Umwandlung je Quelle |
| `providers/wfs.py` | Basis für WFS-Quellen: Ausschnitt je Layer, inhaltsbasierte Kennungen, Helfer für verklebte Texte, Sperr-Erkennung und deutsche Datumsangaben |
| `diagnostics.py` | Diagnose-Download; Koordinaten der Bereiche geschwärzt (landet in öffentlichen Issues) |

`model.py`, `geo.py`, `summary.py`, `changes.py` und die Provider importieren nichts aus HA und werden lokal getestet.

### Entities (je Bereich ein Gerät)

| Entity | Beispiel-ID | Verhalten |
|---|---|---|
| Kalender | `calendar.streckenwacht_arbeitsweg` | Jedes Zeitfenster ein Eintrag (Tagesbaustellen mit mehreren Fenstern → mehrere Einträge). Stau/Unfall/Warnung ohne Ende reichen bis jetzt + 30 min (`LIVE_SPAN`), sonst würden sie über den ganzen sichtbaren Zeitraum gestreckt. |
| Störung aktiv | `binary_sensor.streckenwacht_arbeitsweg_disruption_active` | An bei aktiver Sperrung, Unfall oder Stau ab Stau-Schwelle. Dauerbaustellen zählen bewusst nicht; Sperrungen mit einem Zeitfenster über 30 Tage nur in ihren ersten 7 Tagen (`summary.LONG_CLOSURE`/`NEW_CLOSURE`). Keine `device_class` (Anzeige Ein/Aus). |
| Ereignisse | `sensor.streckenwacht_arbeitsweg_events` | Anzahl aktiver Meldungen; Attribute je Typ, `by_source`, `events` (bis zu 20, schwerste zuerst) |
| Reisezeitverlust | `sensor.streckenwacht_arbeitsweg_travel_time_loss` | Größter aktueller Verlust in Minuten; nur mit INRIX |
| Ereignisänderung | `event.streckenwacht_arbeitsweg_event_change` | `new`/`ended`. Erste Daten einer Quelle und alles nach einer Bereichsänderung (Fingerprint der Einstellungen) werden still gelernt; ein Ausfall löst kein `ended` aus. Pro Ereignis ein State-Write, damit Automationen jedes sehen. |
| Nächste Sperrung | `sensor.streckenwacht_arbeitsweg_next_closure` | Zeitstempel des Beginns der nächsten geplanten Sperrung (14 Tage); Grundlage des Blueprints „Vorwarnung“. |
| Kartenpunkte | `geo_location.<titel>` (Quelle `streckenwacht`) | Je aktive Meldung aller Bereiche eine Entity (ohne Registry-Eintrag, wie Feed-Integrationen), höchstens 150, schwerste und nächste zuerst (`summary.map_events`); Zustand = Entfernung zum nächsten Bereichsmittelpunkt in km. Verwaltet von `geo_location.MarkerManager` (Coordinator-Updates + alle 5 min). |

Entity-IDs sind englisch, weil HA sie aus den englischen Namen bildet. Zwei Blueprints liegen unter `blueprints/automation/streckenwacht/`.

## 2. Datenquellen – verifizierte Eigenheiten

Die Fixtures in `tests/fixtures/` (`tools/fetch_fixtures.py`) sind die Wahrheit über Formate. Weicht die Live-API ab, gilt die API – und sie wird hier nachgetragen.

### Autobahn GmbH (`https://verkehr.autobahn.de/o/autobahn`)

- Pro Autobahn und Dienst ein Endpoint (`/{road}/services/roadworks|closure|warning`). **Keine Umkreissuche** → der Nutzer wählt Autobahnen, gefiltert wird lokal. Straßenliste `GET /` enthält einen Datenfehler (`"A60 "` neben `"A60"`) → trimmen, deduplizieren.
- **Kein Endfeld.** Das Ende steht nur im Freitext `description`: `"Ende: 01.05.27 um 00:00 Uhr"`, `"06.10.26 15:30 bis zum 07.10.26 05:00 Uhr."` oder mehrere Zeilen `"05.10.26 von 10:00 bis 16:30 Uhr"` (→ mehrere Zeitfenster). `startTimestamp` fehlt bei etwa der Hälfte (allen `SHORT_TERM_ROADWORKS`) und ist uneinheitlich formatiert.
- Feldtypen: `isBlocked`, `delayTimeValue`, `averageSpeed` sind Strings; Koordinate `coordinate.lat`/`coordinate.long`; `impact` ist Fahrstreifen-Symbolik, kein Schweregrad. `future: true` = noch nicht begonnen.
- Eine Abfrage enthält auch andere Straßen (z. B. A995-Baustelle unter `A8`).
- **Staus kommen praktisch ausschließlich von INRIX** (`source: "inrix"`, nur bei `warning`). Stau = jeder `abnormalTrafficType` (gesehen: `QUEUING_TRAFFIC`, `SLOW_TRAFFIC`, `HEAVY_TRAFFIC`, `UNSPECIFIED_ABNORMAL_TRAFFIC`) oder Reisezeitverlust > 0. **Unfälle** haben keine Kategorie und werden am Wort „Unfall“ erkannt.
- **INRIX vergibt für denselben Stau neue Kennungen** (Messung 2026-10-05, 14 Autobahnen, 12 Abrufe im 5-Minuten-Takt): 202 neu aufgetauchte Kennungen, davon 37 % nur ein Kennungswechsel (auf derselben Straße und Richtung verschwand im selben Abruf wenige km entfernt ein Stau). Echtes Flackern nur 2-mal; viele Kennungen leben nur einen Abruf. Im 15-Minuten-Takt 27–38 % Kennungswechsel, bei Staus ab 10 min Verlust etwa die Hälfte.
  → **Glättung in `changes.py`:** Ein „neuer“ Stau auf derselben Straße und Richtung höchstens 5 km neben einem im selben Abruf verschwundenen gilt als Fortsetzung. „Neu“ erst ab der Stau-Schwelle des Bereichs, „beendet“ nur für gemeldete Staus. Gespeichert werden dafür Straße, Richtung, Position und ob gemeldet; ältere Speicherformate (nur Titel bzw. `[Titel, Typ]`) werden weiter gelesen.
- Datenmenge: A8-Baustellen ≈ 700 KB (vor allem Geometrie). Qualität: am stärksten der drei Quellen; ein kommerzieller Anbieter pollt dieselbe API alle 10 min.

### MobiData BW (`https://api.mobidata-bw.de/datasets/traffic/roadworks/roadworks_geojson.json`)

- Eine landesweite GeoJSON-Datei in WGS84 (~1000 Features, 2,6 MB) → ein Download pro Abruf, kein API-Key; Bereitstellung beruht auf der EU-Verordnung 2022/670.
- Straßenklassen laut `street`: Gemeinde-, Landes-, Bundes-, Kreisstraßen, vereinzelt Autobahnabschnitte (mögliche Doppelungen mit der Autobahn-API).
- `type` nur `CONSTRUCTION`/`ROAD_CLOSED`; `starttime`/`endtime` ISO 8601.
- **`Point`-Features haben vertauschte Koordinaten** (`[lat, lon]`) → der Provider repariert sie über die Wertebereiche.
- `description` oft generisch („Bauphase“, „keine Beschreibung vorhanden“) → Titel aus `street` + `description`. Viele Langläufer (2015–2037). Webcams sind nicht öffentlich.

### Stadt Stuttgart (WFS `https://geoserver.stuttgart.de/gdc/Verkehr_Mobilitaet/ows`)

- **Umzug (bemerkt 2026-10-18):** Der alte Endpunkt `…/geoserver/wfs` (Layer `GEOLINE_FLEX:…`) antwortet nicht mehr (Timeout); das Open-Data-Portal nennt seit 2026-09-16 den neuen. Dort fehlen `BAUSTELLENNUMMER`, `BEGINN_UHRZEIT`/`ENDE_UHRZEIT`, `STADTTEIL`, `ZUSAETZL_INFO` und jede Angabe zur Verkehrsauswirkung → keine Sperrungen mehr erkennbar, alles `roadworks`. Der Layer „im Bau“ deklariert `VERKEHRSAUSWIRKUNG`, scheitert aber daran („Attribute not found“) → Abfrage mit `propertyName` (nur gemeinsame Felder). Der Parser versteht die alten Felder weiterhin, falls sie zurückkommen.
- Layer `Verkehr_Mobilitaet:A66_BAUM_BAUSTELLEN_DATE_WEB_im_Bau_EPSG25832` und `…_geplant_EPSG25832`; mit `outputFormat=application/json&srsName=EPSG:4326` liefert der Server GeoJSON in WGS84 – kein GML, kein `pyproj`.
- Nur „Vorbehaltsstraßennetz“, ~60 Punkte. Ohne `BAUSTELLENNUMMER` ist die Kennung ein Hash aus Straße, Standort und Art der Arbeit (Feature-IDs enthalten den Layernamen und ändern sich beim Baubeginn). Gleiche Kennung in beiden Layern → „im Bau“ gewinnt.
- `ANFANG`/`ENDE` sind Freitext: meist `dd.mm.yyyy`, daneben „Ende Dez. 2026“, „Mitte Okt. 2026“ (Anfang = 1., Mitte = 15., Ende = Monatsletzter). Bei Fehlschlag bleibt die Meldung erhalten. `BEGINN_UHRZEIT`/`ENDE_UHRZEIT` ergänzen Start bzw. Ende zu einem durchgehenden Zeitraum; `ZEITL_REGELUNG: werktags` wird nicht in Einzeltage zerlegt, sondern in der Beschreibung genannt. „Vollsperrung“ in der Auswirkung → `closure`.
- Qualität: am schwächsten (nur Hauptachsen, bekannte Koordinationsprobleme mit Versorgern).

### Norddeutschland (WFS `https://dienste.gdi-sh.de/WFS_SH_Baustelleninformationen`)

Betrieben vom LBV.SH, Lizenz laut GDI-DE-Metadatenkatalog CC BY 4.0 („© Geokompetenz/LVermGeo SH/CC BY 4.0“; der Dienst selbst nennt keine). `OUTPUTFORMAT=GEOJSON`, `SRSNAME=EPSG:4326`; `BBOX` mit `urn:ogc:def:crs:EPSG::4326` erwartet Breite zuerst. Kein ETag, keine Kompression. Geprüft am 2026-10-14.

- **Keine stabilen Kennungen:** `OBJECTID` läuft je Layer 1…n. Kennung daher aus dem Inhalt (Position, Beginn, Maßnahme, …); exakte Dubletten fallen weg, gleiche Schlüssel werden nummeriert (`parse_layer`). Verlängert die Quelle eine Baustelle, bleibt die Kennung meist erhalten (Ende nicht im Schlüssel).
- **Texte ohne Trennzeichen:** Felder sind teils direkt aneinandergehängt („Knooper Weg**zwischen**“, „herstellen**S**perrung“, „Niemannstraße**gesperrt**“) → `unglue()`.
- **Zeitzonen je Layer verschieden:** SH = Ortszeit minus 1 h ohne Sommerzeit (Mitternacht steht ganzjährig als „23:00“ des Vortags), Hamburg = UTC, MV/NI/Störungen = Ortszeit.
- `Baustellen_SH` (Linien, alle Straßenklassen, `Straßenname` „G“ = Gemeindestraße): „Vollsperrung“ → `closure`; Halteverbote und Geh-/Radweg-/Parkplatzsperrungen werden ausgelassen. Titel aus Straße, Ort (Anfang der Hinweise) und Maßnahme.
- `Baustellen_FHH` (Hamburg, Punkte): Kopf „Baustelle“/„Sperrung“ plus Freitext; `closure` bei „Sperrung“ oder wenn die Fahrbahn „gesperrt“ ist (nicht nur ein Fahrstreifen, `closes_road()`). Viele Dauer-Sperrungen.
- `Baustellen_MV` (Punkte): kein Straßenfeld, nur `Von`/`Nach`; rund die Hälfte der Einträge doppelt; Datumsangaben ohne Uhrzeit enden am Ende des Tages. „Vollsperrung für Lkw“ ist keine Sperrung.
- `Baustellen_Niedersachsen` (Linien): nur Bundesstraßen, kein Ortsname. „Sperrung“ = Richtungsfahrbahn gesperrt → `closure`.
- `Verkehrsstoerungen` (SH, live): Unfälle („Unfall“ im Ereignis), Sperrungen, Warnungen; `Dauer` als Freitext („am 18.10.2026 von ca. 07:00 Uhr bis ca. 18:00 Uhr“), sonst Beginn = `Datenerzeugungszeit`.
- **Ausgelassen:** Autobahn-Layer (deckt die Autobahn-API ab), Punkt-Zwillinge der Linien-Layer, `Baustellenpunkte_Norderstedt` (nicht gepflegt, alles 2023–2025 beendet), Umleitungen, Verkehrslage.

### Berlin (VIZ, `https://api.viz.berlin.de/daten/baustellen_sperrungen_viz.json`)

Redaktionell gepflegte Datei der Verkehrsinformationszentrale („von besonderem verkehrlichem Interesse“), ~550 KB mit ETag, stabile Kennung `id` („17/2025“). Lizenz dl-de-by-2.0, Namensnennung „Digitale Plattform Stadtverkehr Berlin / [Titel]“ (Datenregister Berlin). Geprüft 2026-10-14.

- `subtype` Baustelle/Bauarbeiten/Sperrung/Störung/Gefahr, `severity` Vollsperrung/Fahrtrichtungssperrung/keine Sperrung → `closure` bei den beiden Sperrgraden; Störung mit „Unfall“ → `accident`, sonst `warning`.
- `validity.from/to` als Ortszeit ohne Zone („2026-10-15T17:00“). Geometrie ist eine `GeometryCollection` (Punkt + Linien).
- Autobahn-Baustellen und -Sperrungen (`street` „A100 …“) werden ausgelassen, die Autobahn-API liefert sie; Störungen und Gefahren dort bleiben.
- Daneben gibt es einen ungefilterten Rohdaten-Feed `…/tic3/baustellen_sperrungen_tic.json` (~390 Einträge, weniger Details) – bewusst nicht genutzt.

### Brandenburg (WFS `https://isk.geobasis-bb.de/ows/baustelleninfo_wfs`)

Layer `app:baustelleninfo`, `OUTPUTFORMAT=application/geo+json`, ~1,4 MB ohne ETag → grobes Raster. Lizenz dl-de-by-2.0 („© Landesbetrieb Straßenwesen Brandenburg“, im Dienst selbst angegeben). Kennung `ID` stabil. Bundes-, Landes- und Kreisstraßen.

- Datumsangaben ohne Uhrzeit (`Baustellen_Beginn`/`_Ende`). `Art` „Sperrung“ (= Fahrstreifen gesperrt) → `closure`, „Bauabschnitt“ → `roadworks`. Die erste Zeile von `Verkehrsinformation` nennt die Maßnahme.
- **Leere Treffer kommen als `FeatureCollection` ganz ohne `features`** – die WFS-Basis wertet das als leer.

### Sachsen-Anhalt (WFS `https://service.ifak.eu/sperrinfo/wfs`)

Layer `ms:roadworks`, `OUTPUTFORMAT=geojson`, ~200 KB → komplett geladen (`filter_by_bbox = False`). **Der Dienst erlaubt laut `AccessConstraints` nur nichtkommerzielle Nutzung** – passt zu Streckenwacht (privat, jede Instanz ruft selbst ab), steht in der Namensnennung und in der README. Alle Straßenklassen inkl. Gemeindestraßen.

- Eine Baustelle besteht aus mehreren Abschnitten mit gleicher `feature_id` (bis zu 7) → `merge_sections()` fasst sie zu einer Meldung zusammen, die schwerste `kind` gewinnt (D Vollsperrung, F Sperrung einer Fahrtrichtung → `closure`; C halbseitig, B Einschränkung).
- `location` enthält oft nur „außerhalb der Ortschaft“/„freie Strecke“ → dann ohne Ort im Titel. Autobahnfelder (`bab_*`) sind leer.

### Sachsen (ZIP `https://www.list.smwa.sachsen.de/gdi/download/baustelleninfo/Baustelleninfo_Sachsen_geojson.zip`)

Kein WFS (nur ein WMS für Kartenbilder). ZIP mit `Baustelleninfo_Sperrungen_Sachsen.geojson` (~2,7 MB, ~1.400 Abschnitte) und `…_Umleitungen_…` (ungenutzt), stündlich neu, **mit ETag**. Lizenz CC BY 4.0, Quellenvermerk „Baustelleninformationssystem Sachsen“ (WMS-Capabilities). Geprüft 2026-10-14.

- **Koordinaten in ETRS89/UTM 33N (EPSG:25833).** Umrechnung mit `geo.utm_to_wgs84()` (Krüger-Reihen); gegen pyproj an 2.000 echten Punkten geprüft, Abweichung < 1 mm – kein `pyproj` nötig.
- Herunterladen und Auswerten nur, wenn sich die Datei geändert hat (`Provider._get_bytes`, ETag); das Auswerten läuft per `asyncio.to_thread`. Für jeden Nutzer mit dieser Quelle ~2,4 MB je Änderung (höchstens stündlich), dafür keine Ortsangabe in der Abfrage.
- Eine Sperrung (`ID`) hat bis zu 13 Abschnitte → zusammengefasst, die schwerste `Sperrung_Art` gewinnt (D Vollsperrung, G Richtungsfahrbahn, F Fahrtrichtung, J Anschlussstelle → `closure`). `Strassenklasse` „A“ (Autobahn) und `Sperrung_Art` „O“ (Halte-/Parkverbot) werden ausgelassen. `Sperrung_Typ` „V“ = Veranstaltung.
- `Ort` kann eine mehrzeilige Liste sein (erste Zeile wird verwendet). Datumsangaben `dd.mm.yyyy` ohne Uhrzeit. Enthält auch Thüringer Grenzgebiet.

### Rheinland-Pfalz (WFS `https://maps.mobilitaetsatlas.de/geoserver/ows`, Mobilitätsatlas)

Layer `mwvlw:baustelle` (GeoServer, `outputFormat=application/json`, **gzip**). Enthält mehrere Herkünfte (`quelle`: Autobahn GmbH, Verkehrsministerium BW, Stadt Karlsruhe, Straßenbauverwaltung Luxemburg, **Verkehrsbehörden in Rheinland-Pfalz**) → `CQL_FILTER=quelle='Verkehrsbehörden in Rheinland-Pfalz'`; so ~1.050 Meldungen, ~90 KB übertragen, daher komplett ohne Ausschnitt. Geprüft 2026-10-14.

- **Lizenz:** In der Mobilithek vom Landesbetrieb Mobilität als öffentliches Angebot ohne Freigabe eingestellt („Arbeitsstellen des klassifizierten Straßennetzes in Rheinland-Pfalz - WFS“), aber mit `rights = NO_LICENSE`; der Dienst selbst nennt keine. Gleiche Abwägung wie bei der Autobahn-API: jede Instanz ruft den öffentlichen Dienst selbst ab, Namensnennung des Landesbetriebs.
- Nur Punkte, **kein Ortsname** – Titel aus Straßennummer (`strasse`, „G“ = Gemeindestraße) und dem ersten Satz von `beschreibung` (oft leer → `art_der_arbeiten`). Kennung = Feature-ID (enthält das Aktenzeichen).
- `typ` wie SPERRINFOSYS (G Vollsperrung, F Fahrtrichtung → `closure`; B, C, N sonst), Suffix `_GEPLANT` für geplante.
- **Zeiten tragen „Z“, sind aber Ortszeit** (Tage laufen von 00:00 bis 23:59).
- Gehweg- und Halteverbots-Meldungen werden ausgelassen. Vereinzelt kaputte Umlaute in den Quelldaten („Straï¿½e“, 4 von 1.058) – nicht rekonstruierbar, bleiben so.

### Großstädte in Ländern ohne Landesquelle (geprüft 2026-10-14)

Alle klein genug für den Komplettabruf ohne Ausschnitt.

- **München** (WFS `https://geoportal.muenchen.de/geoserver/mor_wfs/ows`, Layer `mor_wfs:baustellen_opendata`, gzip; dl-de-by-2.0 „Landeshauptstadt München – opendata.muenchen.de“). Sehr feinkörnig (~6.000 Einträge, nächste vier Wochen, Fokus Innenstadt und Hauptstraßen) → `CQL_FILTER=art='Baumaßnahme' AND betroffene_bereiche LIKE '%Fahrbahn%'` (~1.200, ~200 KB gzip); zusätzlich werden Einträge ausgelassen, deren `beeintraechtigung` nur Parkplätze/Halteverbote nennt. Feature-IDs fortlaufend, `fachliche_id` meist leer → Schlüssel aus Inhalt; mehrere Polygone einer Baustelle werden zusammengefasst (`merge_features`). Beginn teils Freitext („Beginn vor mehr als einem Jahr“ → offener Start). „Straßensperrung“/„Vollsperrung“ → `closure`, „halbseitige …“ nicht.
- **Köln** (ArcGIS `…/verkehr/verkehrskalender/MapServer/0/query`, `f=geojson`, `where=anzeige=1`; **mit ETag**; dl-de-zero laut Open-Data-Portal). Redaktioneller Verkehrskalender (~170 Einträge). `typ` 1–15 (Codeliste aus den Layer-Metadaten): 2 Einfahrtverbot → `closure`, 3 Baustelle (bei „gesperrt“ im Text `closure`), 5 Stau, sonst Hinweise/Veranstaltungen → `warning`. Zeiten in Epoch-ms UTC; 00:00 UTC steht für ganze Tage. Kennung = `objectid` (die Nummer im `link` ist nicht eindeutig).
- **Frankfurt** (WFS `https://geowebdienste.frankfurt.de/Baustellen`, GeoServer hinter mainziel.de; Layer `opendata_verkehr:Baustellen` und `…:Verkehrsmeldungen`, ~340 KB). **Keine Lizenzangabe** (`AccessConstraints: YES` ist der GeoServer-Platzhalter) → wie Rheinland-Pfalz behandelt. `sperrung` = 1 → `closure` (Text „Vollsperrung“ betrifft oft nur Park- oder Gehwege). Zeiten echtes UTC; Ende 2099 = offen. Titel aus „aufgrund von …“ in `textlong`.
- **Dortmund** (Opendatasoft-Export `…/fb66-baustellen-tagesaktuell` und `…-geplant`, je ~10 KB gzip; dl-de-zero). **Keine Kennungen** → Schlüssel aus Inhalt. Einschränkung steckt im Titel hinter „//“; „Vollsperrung“ am Anfang → `closure`. Ende 2099/2204/2999 = offen.
- **Aachen** (WFS `https://bsis.aachen.de/geoserver/ows`, `BSIS:PUNKTE_ALLE`, gzip ~50 KB; dl-de-by-2.0). `symbol` = „Sperrgrad - Zustand“ (Vollsperrung/Teilsperrung/(starke) Verkehrsbehinderung – aktuell/zukünftig/abgelaufen): abgelaufene weg, Vollsperrung → `closure`. Einträge, deren `einschraen` nur Gehweg/Parkplätze nennt, weg. Kennung `sdatenid`. Datumsangaben „2026-10-05Z“ (nur Datum).
- **Duisburg** (ArcGIS `…/MP_Verkehrsportal/MapServer/2/query`, mit ETag; CC BY 3.0 DE laut Open.NRW). `SYMBOL_ID` (1/2/4) ist nirgends erklärt (keine Legende, keine Codeliste) → nicht ausgewertet; Sperrung nur, wenn der Text „gesperrt“ sagt. `BAUZEIT_AB` „12.10.26 - 30.10.26“ mit zweistelligen Jahren. Kennung `OBJECTID`.
- **Münster** (MapServer-WFS `…/odbaustellen_serv`, `OUTPUTFORMAT=geojson`; dl-de-by-2.0). ~20 redaktionell gepflegte Baustellen, `typ_bez` Voll-/Teilsperrung. **Enthält Namen und Telefonnummern von Ansprechpartnern – werden nicht übernommen** (auch nicht in die Fixture).
- **Bochum:** ArcGIS-Dienst vorhanden, laut Open.NRW aber „andere geschlossene Lizenz“ → nicht umgesetzt.
- Nicht genutzt: Kölner Baustellen-WFS (15 Layer nach Arbeitsart, viel Kleinkram), Frankfurter Region (ivm, Mobilithek, nicht erreichbar).

### Luxemburg (DATEX II, `https://www.cita.lu/info_trafic/datex/chantierActuelDatex.xml` und `…/chantierFuturDatex.xml`)

Administration des Ponts et Chaussées, **CC0** auf data.public.lu. Zwei Dateien (aktuell, geplant), je ~0,5 MB, gzip und ETag. Die gleichen Meldungen stehen auch im Mobilitätsatlas-Layer von Rheinland-Pfalz (ohne Lizenz, ohne Details) – die Originalquelle ist besser. Geprüft 2026-10-18.

- Eine `situation` hat mehrere `situationRecord`s (`MaintenanceWorks`, `GeneralNetworkManagement` = Baustellenampel, `SpeedManagement`) → eine Meldung; `trafficConstrictionType` `roadBlocked` → `closure`. Zeitfenster aus `validPeriod` (mit Zeitzone), Ort als Linie von `from` nach `to`, Straße aus dem Ortsnamen (`descriptor`, z. B. „CR129“, „A7N-F“).
- Die Kommentare (`generalPublicComment`) sind französisch und in der Quelle ohne Akzente („chausse rtrcie“) → nicht übernommen. Die KML-Variante enthält dieselben Angaben nur als HTML.
- Gleiche Situation in beiden Dateien → die aktuelle gewinnt. XML-Auswertung per `xml.etree` im Thread (expat begrenzt Entity-Expansion).

### Weitere Städte (geprüft 2026-10-18, `providers/cities.py`)

Füllen kommunale Straßen auf, die die Landesquellen (MobiData BW, Norddeutschland) nicht kennen, bzw. Bayern ohne Landesquelle. Alle komplett ohne Ausschnitt.

- **Karlsruhe** (WFS `https://mobil.trk.de/geoserver/TBA/ows`, Layer `TBA:baustellen` = aktuell + Vorschau, ~180 KB gzip; CC BY 4.0). Deckt die ganze Technologieregion ab (auch Pfalz und Elsass). `CQL_FILTER` auf `sperrung` (Vollsperrung, eine Fahrtrichtung, Verkehrsbehinderung). Eine Baustelle steht oft doppelt (Punkt und Fläche) → `merge_features` nach Lage/Art/Zeitraum. Feature-IDs werden neu nummeriert, `vorgangsnummer` teils „---“ → Schlüssel aus Vorgangsnummer, Lage, Art und Beginn. Zeiten UTC. Elsässer Einträge haben interne Codes als `art` („AK5_encours“) → als „Baustelle“ angezeigt.
- **Rostock** (GeoJSON `https://geo.sv.rostock.de/download/opendata/baustellen/baustellen.json`, ETag; CC0). Nur Einträge, deren `verkehrsbeeintraechtigungen` Vollsperrung, halbseitige Sperrung oder Verkehrsraumeinschränkungen nennt (der Rest sichert Gehwege und Fassaden). `von`/`nach` sind Hausnummern oder Querstraßen mit Straßenschlüssel („Borwinstr. (01500)“). Kennung `uuid`.
- **Kiel** (ArcGIS-WFS `https://ims.kiel.de/…/LHKielWmsWfs/MapServer/WFSServer`, `outputFormat=geoJSON`; CC BY 4.0). Layer `lhkiel:Baustellen_{L,F}_-_{Aktuell,Zukunft}` (Linien, Flächen); die Punkt-Layer liefen beim Test in Timeouts, der Sammellayer `Baustellen` ist leer. `Legende` „Voll_…“ → `closure`. Zeitraum als Text „06.07.2026 bis 30.10.2026“. Leere Felder kommen als Text „null“. Kiel steht zusätzlich im norddeutschen WFS (keine Deduplizierung).
- **Ingolstadt** (GeoJSON `https://www.ingolstadt.de/openbydata/VMS/Baustellen_14_Tage_Ingolstadt.geojson`, ETag; CC BY 4.0 laut open.bydata). Nächste 14 Tage, Punkte in **UTM 32N** (`geo.utm_to_wgs84`). Nur `ART_VB` mit „Gesamtsperrung“ (→ `closure`) oder „halbseitige Sperrung“. `ART_ARB` mit „;“ und Zeilenumbrüchen getrennt; `SONDERINFO` ist manchmal eine ganze Pressemitteilung → gekürzt. `AUFTRAGGEBER_EMAIL` wird nicht übernommen (auch nicht in die Fixture).
- **Freiburg** (WFS `https://geoportal.freiburg.de/wfs/gut_baustellen/gut_baustellen`, Layer `baustellenumgriffe`, `outputFormat=GEOJSON`, `srsName=EPSG:4326`; dl-de/by-2.0 laut GovData). ~20 redaktionell gepflegte Baustellen auf Hauptverkehrsstraßen (Flächen), Datum ISO ohne Uhrzeit, Kennung `fid`. Manche Baustelle ist mehrfach gezeichnet → zusammengefasst nach Name und Zeitraum. „Vollsperrung“/„voll gesperrt“ im `verkehrshinweis` → `closure`.
- Nicht umgesetzt: **Leipzig** (Lizenz des WFS unklar, Hauptstraßen über Sachsen abgedeckt), **Herne** (WFS antwortete mit Serverfehler 500), **Bonn** (Datensatz bei Open.NRW nicht mehr auffindbar), **Bayern landesweit** (open.bydata hat nur eine statische Referenz-ZIP, aktuelle Daten nur über die Mobilithek mit Freigabe).

### Landesmeldestelle Baden-Württemberg (DATEX II, `https://api.mobidata-bw.de/datasets/traffic/incidents/incidents_lmsbw.datex2.xml`)

Verkehrsmeldungen der LMS BW über MobiData BW, **dl-de/by-2.0**, ~75 KB gzip, ETag. Geprüft 2026-10-18: ~35 Meldungen, überwiegend von der Integrierten Verkehrsleitzentrale Stuttgart (Sperrungen mit Umleitung, auch auf Stadtstraßen), dazu Autobahnen und Umland. Ergänzt den Stuttgarter WFS, der seit dem Umzug keine Sperrungen mehr erkennen lässt.

- Eine `situation` → eine Meldung. Text aus `generalPublicComment` mit `commentType=description`: 1. Zeile Ort („B14 Stuttgart, Cannstatter Straße“, „Kreis Ludwigsburg, L1100“), 2. Zeile Abschnitt, 3. Zeile Meldung.
- **Autobahn-Meldungen** (Ort beginnt mit „A<Nummer>“) werden ausgelassen – die kommen über die Autobahn-API. **Erledigte** Meldungen bleiben eine Weile in der Datei (`validityStatus=suspended`, `cancel=true`, Text „Unfallstelle geräumt“) → ausgelassen.
- Art: `Accident` → `accident`; `roadClosed` → `closure`; `stationaryTraffic` oder „Stau“ im Text → `traffic_jam`; `MaintenanceWorks`/`ConstructionWorks` → `roadworks`; sonst `warning` (Titel dann aus der Meldung, z. B. „Ölspur“).
- `validPeriod` nennt oft nur das Ende; der Beginn steht in `overallStartTime` (gilt jetzt für alle DATEX-Quellen, `providers/datex.py`). Ort als Linie `from` → `to`, sonst `locationForDisplay`.
- Nicht genutzt: der ältere TIC3-Feed derselben Stelle (`…/incidents-bw/TIC3-Meldungen.xml`).

### Kartenkarte (`frontend/streckenwacht-map-card.js`, seit 0.6.0)

- Reines JavaScript ohne Build-Schritt (Custom Element mit Shadow DOM), Leaflet 1.9.4 mitgeliefert (`frontend/leaflet.js`, BSD-2-Clause, Lizenz daneben). Die Integration liefert den Ordner unter `/streckenwacht/frontend` aus (`async_setup`, nur wenn `http` geladen ist; `after_dependencies`). URL mit `?v=<Version>` gegen alte Browser-Caches.
- Anmeldung beim Frontend (`frontend_resource.py`, seit 0.7.1): als **Dashboard-Ressource** (Ressourcen im Storage-Modus, Standard), angelegt in `async_setup_entry`, bei neuer Version auf die neue URL umgestellt, Dubletten (gleicher Pfad, anderes `?v=`) gelöscht, in `async_remove_entry` entfernt. Nur bei Ressourcen im YAML-Modus (dort nicht änderbar) oder bei einem Fehler Rückfall auf `add_extra_js_url`. Grund (bis 0.7.0 nur `add_extra_js_url`): Extra-Module schreibt der Core beim Abruf in die `index.html`; eine Seite, die während des HA-Starts geladen wird (HTTP läuft ab Stufe 0, die Integration erst in Stufe 2), bekommt die Karte nie – das Frontend lädt Extra-Module nicht nach (`frontend/subscribe_extra_js` nutzt es nicht). Folge: „Custom element not found“ bis zum Neuladen, vor allem in der Companion App. Ressourcen kennt das Frontend unabhängig davon, die Datei kommt dann aus dem Browser-Cache (`cache_headers`); nur der erste Seitenaufruf nach einem Update während des Starts kann noch scheitern (404). Spätes Laden an sich ist kein Problem: das Frontend wartet per `customElements.whenDefined` und baut die Karte dann neu. Das JS definiert das Element nur einmal (Schutz gegen doppeltes Laden unter verschiedenen `?v=`).
- Daten über den WebSocket-Befehl `streckenwacht/map` (`websocket.py`): Bereich über eine beliebige Entität des Bereichs (Entity-Registry → `config_subentry_id`), Antwort = Kreis + `summary.map_features()` (aktive und in 14 Tagen beginnende Meldungen als GeoJSON, zusammengefasste Dubletten). Geometrien bleiben so aus Attributen und Recorder heraus. Die Karte lädt neu, wenn sich `last_updated` der gewählten Entität ändert, sonst alle 5 Minuten.
- Kartenhintergrund über den Kachel-Proxy des Cores (`map_tiles`, seit HA 2026.9): Token per WebSocket `map_tiles/access_token`, Raster unter `/api/map_tiles/raster/{z}/{x}/{y}.png?token=…`, Token-Erneuerung alle 20 Minuten (Core rotiert alle 30). **Kein Rückfall auf OSM direkt** – das würde den Kartenausschnitt einem Dritten zeigen; stattdessen ein Hinweis. Dunkles Theme per CSS-Filter auf den Kacheln.
- Ausschnitt: halbe Zoomstufen (`zoomSnap: 0.5`); die Karte folgt dem Bereichskreis (auch nach Größenänderungen), bis der Nutzer selbst schiebt oder zoomt. Die Interaktions-Handler werden erst nach der Startansicht angemeldet, weil Leaflet auch dabei `zoomstart` feuert.
- Mehrere Bereiche (seit 0.7.0): `entities:` (Liste), ein altes `entity:` wird dazugenommen. Je Bereich ein `streckenwacht/map`-Aufruf (parallel, `Promise.allSettled`: ein fehlerhafter Bereich blendet nur einen Hinweis ein), Meldungen über ihre `id` nur einmal gezeichnet, Ausschnitt über alle Kreise. `L.circle().getBounds()` geht erst, wenn der Kreis auf der Karte liegt.
- Gruppierung (seit 0.8.0, `cluster`, Standard an, im Editor abschaltbar): eigene, ohne Zusatzbibliothek. Beim jeweiligen Zoom gierig in Bildschirmpixeln: die schwerste freie Meldung (aktive vor geplanten) sammelt alle freien im Umkreis von 40 px; ab 2 Meldungen ersetzt eine Blase mit der Anzahl deren Punkte und Linien. Die Blase sitzt auf der schwersten Meldung (so liegen Blasen nie übereinander), Farbe nach ihr, blass wenn nichts aktiv ist; Klick zoomt auf die Gruppe. Ab Zoom 15 keine Gruppen. Neu berechnet bei `zoomend` und nach jedem Zeichnen (München, 1.011 Meldungen: 3 ms). Legende und Hinweis liegen über der Markerebene (`z-index` 650/660, Popups 700).
- Editor über `getConfigForm()` (Bereiche als Mehrfachauswahl, Titel, Höhe, geplante zeigen, Gruppierung). Lokal getestet mit einer Testseite und simuliertem `hass` (Playwright), nicht in CI.

## 3. Entscheidungen

- **Eine Integration mit Providern** statt mehrerer: gemeinsame Entities pro Bereich, ein Config-Flow, ein HACS-Eintrag.
- **Ein Entry + Subentries je Bereich, ein Coordinator je Quelle** (siehe Architektur).
- **Keine Webcams** – keine Quelle liefert öffentliche Bilder.
- **Deduplizierung zwischen Quellen seit 0.6.0** (`dedup.py`, Option „Doppelte Meldungen zusammenfassen“, Standard an). Bis 0.5 gab es keine: Messung 2026-10-02 (10 km um Stuttgart-Kaltental) ergab 64 quellenübergreifende Paare ≤ 300 m, fast alle aber verschiedene Straßen am selben Ort. Mit LMS BW kamen echte Dubletten dazu. Messung 2026-10-19 über zehn Städte (Live-Daten): Stuttgart 9 Gruppen (LMS-Sperrung + städtische Baustelle, B10 Stammheim aus drei Quellen), Karlsruhe 2 (B36-Brücke Stadt + MobiData), Berlin, Kiel, Freiburg, München, Köln 0.
  - Regeln: verschiedene Quellen (je Quelle höchstens eine Meldung pro Gruppe, nächstes Paar zuerst); nur Baustelle/Sperrung, nie Stau/Unfall/Warnung; Geometrien ≤ 300 m; gleiche **Hauptstraße** (Straßennummer oder Straßenname der Meldung selbst – Text vor dem Doppelpunkt bis „zw./zwischen/von/bis/Richtung …“; bei der Autobahn nur das Feld `road`, weil ihre Titel Abschnitte nennen); Zeitraum: Beginn oder Ende ≤ 14 Tage auseinander oder einer liegt im anderen und der äußere dauert ≤ 1 Jahr (schließt Dauer-Anordnungen wie „Verbot des Unterschreitens des Mindestabstandes“ 2024–2029 aus). Unbekannte Zeiten → nicht zusammenfassen.
  - Führend ist die Sperrung, bei Gleichstand die örtlichere Quelle (Stadt vor LMS BW vor Landesquellen vor Autobahn). Die anderen stehen in der Beschreibung („Auch gemeldet von …“), in `also_reported_by` und in der Namensnennung.
  - Bewusst verpasst: „Hausmannstraße bis Gerokstraße: Sperrung“ ↔ „Gerokstraße: Gleisbau“ (Straße nur im Abschnitt), Autobahn „A100 Hohenzollerndamm (AS) Brückeninstandsetzung“ ↔ Berlin „Hohenzollerndamm: Brückensanierung“.
  - „neu/beendet“ (changes.py): eine Gruppe wird einmal angekündigt, von der führenden Meldung. Kommt eine Sperrung zu bekannten Arbeiten dazu, ist das ein „neu“; kommen Arbeiten zu einer bekannten Sperrung, bleibt es still. Verschwindet eine Meldung, deren Partner noch gemeldet wird, gibt es kein „beendet“ (`merged_with` in den bekannten Meldungen).
  - Rechenaufwand: Kandidaten nur über gemeinsame Straßenschlüssel, Abstand mit Bounding-Box-Vortest; Ergebnis je Bereich zwischengespeichert, bis ein Coordinator neue Daten hat (Entitäten fragen minütlich). Seit 0.9.2 rechnet ein eigener Listener je Coordinator (`refresh_area_events`, vor den Entitäten angemeldet) das Ergebnis gleich nach dem Abruf vor, nicht mehr die erste lesende Entität in ihrem Zustandsschreiben – HA misst die Dauer jedes Schreibens und warnt ab 0,4 s (einmal beobachtet am 2026-10-27).
- **„Störung aktiv“ nur für Sperrung, Unfall, Stau ab Schwelle** – sonst wäre es wegen Dauerbaustellen praktisch immer an.
- **Langlaufende Sperrungen zählen nur in ihrer ersten Woche** (0.2.0): In Städten gibt es viele monatelange Sperrungen; der Sensor war dort praktisch immer an. Kurze Zeitfenster (bis 30 Tage, auch einzelne Nachtsperrungen langer Projekte) zählen weiter durchgehend; Sperrungen ohne bekannten Beginn gelten als langlaufend, solche ganz ohne Zeiten zählen. Gemessen 2026-10-14 (aktive Sperrungen → zählend): Stuttgart 10 km 29 → 3, Berlin 8 km 46 → 3, München 5 km 32 → 3, Köln 5 km 16 → 3, Hamburg-Mitte 10 km 134 → 29.
- **Projektlizenz MIT** (HACS-üblich; Apache-2.0 brächte hier keinen Mehrwert).
- **Wenig Schreiblast (SD-Karten, seit 0.9.1):** Messung 2026-10-26 mit Live-Daten: Die Datei der bekannten Meldungen (`known_events.py`, eine Datei für alle Bereiche) wiegt bei München 12 km 357 KB, bei Stuttgart 15 km 65 KB, und änderte sich mit Staus bei fast jedem Abruf – rund 40 MB Schreiblast am Tag. Deshalb höchstens ein Schreibvorgang pro Stunde: Die erste Änderung plant ihn (`SAVE_DELAY`), weitere hängen sich an – ein erneutes `async_delay_save()` würde ihn sonst immer weiter hinausschieben. HA schreibt Ausstehendes beim Beenden, `async_unload_entry` per `async_flush()` (sonst läse ein Neuladen den alten Stand). Preis: Nach einem Stromausfall kann eine Meldung der letzten Stunde doppelt angekündigt werden. Im Recorder fehlen die großen, oft wechselnden Attribute (`_unrecorded_attributes`): `events` (bis ca. 9 KB), `disruptions`, die Kalender-`description`. Das minütliche Neuberechnen kostet nichts: HA schreibt nur bei geänderten Zuständen oder Attributen. Je Zustandsschreiben gilt ein einziger Zeitpunkt, und Ansichten, die Zustand und Attribute beide brauchen (aktive Meldungen, größter Zeitverlust, nächste Sperrung, Störungen), werden nur einmal gerechnet (`TimeDependentEntity._per_write`, über den von HA vorgesehenen Haken `_async_write_ha_state`; seit 0.9.2).
- **Repo** `github.com/streckenwacht/integration` (Organisation), `codeowners` `@n42net`.

## 4. Risiken, Lizenzen, Recht (keine Rechtsberatung)

- **Namensnennung** je Quelle in `const.ATTRIBUTION` und im Attribut `attribution`: Stuttgart CC BY 4.0, MobiData BW DL-DE-BY-2.0, Norddeutschland CC BY 4.0, Berlin und Brandenburg DL-DE-BY-2.0, Sachsen CC BY 4.0, Sachsen-Anhalt nur nichtkommerziell, Rheinland-Pfalz und Frankfurt ohne erklärte Lizenz, München dl-de-by-2.0, Köln und Dortmund dl-de-zero, Autobahn GmbH (keine erklärte Lizenz, Nennung als gute Praxis), zusätzlich „Verkehrslage: INRIX“.
- **INRIX** (entschieden 2026-10-02): keine erklärten Nutzungsbedingungen; die Daten werden offen und auch kommerziell genutzt. Streckenwacht verbreitet nichts weiter – jede Instanz ruft den öffentlichen Endpunkt selbst ab; Risiko gering. Vorsorge: `upstream="inrix"` und die abschaltbare Option. **Warnungs-Fixtures (echte INRIX-Daten) nur lokal, nie committen** (`.gitignore`; aus der Historie entfernt); Tests nutzen ein eingebettetes Beispiel.
- **Zurückgestellt** (Entscheidung des Projektinhabers): Impressumsfrage und Anfrage bei der Autobahn GmbH zu INRIX – erst beim öffentlichen Bewerben wieder aufgreifen. Bis dahin keine Spenden-Links oder Werbung.
- **API-Stabilität:** keine Quelle ist versioniert oder hat ein SLA, Rate Limits sind unbekannt → defensiv parsen, konservativ pollen, ETag nutzen.

## 5. Arbeitsweise

- **Branches:** Entwicklung auf `dev` (CI läuft dort). `main` erhält nur freigegebene Stände, weil die HACS-Installation `main` bzw. den Releases folgt.
- **Release:** Version in `manifest.json`, `const.py` (`VERSION`) und `pyproject.toml` setzen (danach `uv lock`; `tests/test_manifest.py` prüft die Gleichheit), in `CHANGELOG.md` „Unveröffentlicht“ zur neuen Version machen → CI auf `dev` grün → `main` per Fast-Forward → `gh release create vX.Y.Z --target main`, immer als reguläres Release, nie `--prerelease` (Checkliste in `CLAUDE.md`, Abschnitt „Release“) → Workflow „Release-ZIP“ abwarten und prüfen, dass `streckenwacht.zip` am Release hängt. HACS zeigt den Tag des neuesten Releases und installiert seit 0.7.2 dieses ZIP (`hacs.json`: `zip_release`, `filename`); der Workflow (`.github/workflows/release-asset.yml`) baut es beim Veröffentlichen aus `custom_components/streckenwacht` (Dateien im Wurzelverzeichnis des ZIPs) und bricht ab, wenn Tag und `manifest.json`-Version nicht passen. Fehlt das ZIP, schlägt die Installation über HACS fehl: dann den Workflow per Hand mit dem Tag starten. Nutzen: GitHub zählt die Downloads pro Release (`gh api repos/streckenwacht/integration/releases --jq '.[] | "\(.tag_name): \(.assets[0].download_count)"'`) – Installationen und Updates zusammen, keine Nutzerzahl. Reine README-Korrekturen ohne Release nach `main` nur nach Rücksprache.
- **Tests:** Logik- und Provider-Tests lokal (`uv run pytest --ignore=tests/ha`); HA-Tests (`tests/ha/`, `pytest-homeassistant-custom-component`) nur in GitHub Actions, weil die Bibliothek unter Windows nicht läuft. CI-Jobs: `test` (aktuelles HA), `compat` (HA 2026.3), `hassfest`, `hacs`. Dependabot-Warnungen stammen aus `uv.lock`, also aus der Entwicklungsumgebung (die Integration hat keine Abhängigkeiten): bei neuen HA-Versionen `homeassistant` in der `dev`-Gruppe und `pytest-homeassistant-custom-component` gemeinsam anheben, dann `uv lock --upgrade`. Was Home Assistant selbst festpinnt (2026-10: Pillow 12.3.0), lässt sich erst mit dessen nächstem Release beheben.
- **Werkzeuge:** `tools/fetch_fixtures.py` (Fixtures aktualisieren), `tools/live_check.py` (Live-Abruf außerhalb von HA), `tools/source_check.py` (alle Quellen mit den echten Providern prüfen; läuft montags per `.github/workflows/source-check.yml`, öffnet bei Problemen ein Issue mit Label `quellen-check`, kommentiert ein offenes und schließt es, sobald wieder alles geht; Probleme = zweimal Fehler, keine Meldungen, keine im eigenen Gebiet oder keine Zeiträume; zeitgesteuerte Workflows laufen nur von `main` und schlafen nach 60 Tagen ohne Repo-Aktivität ein), `tools/mobilithek_scan.py` (Mobilithek-Katalog prüfen), `tools/brand/` (Bilder neu erzeugen).
- Entwickelt wird gegen eine produktive HA-Instanz: neue Provider-Logik zuerst außerhalb von HA testen.

### GitHub-Einstellungen (Stand 2026-10-27, per `gh api` geprüft)

Nicht aus dem Code ablesbar, deshalb hier festgehalten. Gleich in allen Schwesterprojekten.

- **Repo:** Secret Scanning mit Push-Schutz, Dependabot-Warnungen und -Sicherheitsupdates, CodeQL (Standard-Setup: Python, JavaScript, Actions), vertrauliche Meldung von Sicherheitslücken (`SECURITY.md`). Branches nach dem Mergen löschen; kein Wiki, keine Projekte.
- **Rulesets:** „main schützen“ (kein Löschen, kein Force-Push, Pflicht-Checks `test`, `hassfest`, `compat`) und „Release-Tags schützen“ (`v*`: nicht löschen, nicht verschieben).
- **Actions:** nur GitHub-eigene Actions plus `astral-sh/setup-uv@*`, `home-assistant/actions/*`, `hacs/action@*`; Workflow-Token standardmäßig nur lesend. Eine neue Action im Workflow muss dort erst erlaubt werden (*Settings → Actions → General*).
- **Bewusst aus:** „Unveränderliche Releases“ – der Workflow „Release-ZIP“ hängt die ZIP erst nach dem Veröffentlichen an.
- **Organisation:** Zwei-Faktor-Pflicht für alle Mitglieder.

## 6. Backlog

Stand 2026-10-19. Datenquellen gelten vorerst als ausgeschöpft (Städte-Sweep und TomTom-Prüfung in [`DATENQUELLEN.md`](DATENQUELLEN.md)); gelegentlich erneut prüfen: Rhein-Main/ivm (Zertifikat abgelaufen), Heidelberg (404); Herne liefert seit 2026-10-20 (Lizenzfrage offen, siehe `DATENQUELLEN.md`).

- **Strecke statt Kreis:** Korridor entlang einer Route aus Wegpunkten (Wunsch aus dem Beta-Test). Knackpunkt: Eingabe im Dialog, HA hat keinen Linien-Selektor.
- **Autobahn-Abschnitte** („A81 zwischen AS X und AS Y“): Abschnittsnamen sind Freitext – zugunsten der Fahrtrichtungen zurückgestellt.
- **Kartenkarte, nächste Ausbaustufen:** Zeitregler. (Mehrere Bereiche in einer Karte: erledigt in 0.7.0; Gruppierung naher Meldungen: 0.8.0.)
- **Bekanntmachen:** simon42 Community erledigt (Vorstellung, Updates zu 0.2.0 und 0.3–0.5), HA Community (Custom Integrations, 2026-10-20) erledigt, in der HACS-Standardliste seit 2026-10-24 ([hacs/default#12314](https://github.com/hacs/default/pull/12314), beantragt 2026-10-20); als Nächstes ggf. Awesome Home Assistant.
- Erledigt: eigene Kartenkarte (0.6.0, siehe Abschnitt 2 „Kartenkarte“), Deduplizierung (0.6.0, siehe Entscheidungen), Langzeitstatistik (der Sensor „Reisezeitverlust“ hat `state_class: measurement`, README zeigt die Statistik-Karte), Kartenansicht per `geo_location`, weitere Datenquellen.
