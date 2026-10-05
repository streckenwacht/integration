# Streckenwacht – Entwicklerdokumentation

Wie Streckenwacht gebaut ist, was man über die Datenquellen wissen muss und warum Dinge so entschieden wurden. **Maßgeblich ist der Code**; dieses Dokument erklärt, was dort nicht steht. Weitere Dokumente: [`DATENQUELLEN.md`](DATENQUELLEN.md) (Recherche zu neuen Quellen), [`BRAND.md`](BRAND.md) (Bilder, Farben). Die ursprüngliche Spezifikation (`docs/HANDOVER.md`) liegt in der Git-Historie bis Version 0.1.0.

## 1. Architektur

### Konfiguration

- **Ein Config-Entry** „Streckenwacht“ (`single_config_entry`): aktive Quellen, Abrufintervall (10–60 min, Standard 15), Option „Staumeldungen (INRIX) einbeziehen“ (Standard an). Nur UI, kein YAML.
- **Ein Config-Subentry `area` je Beobachtungsbereich**, eingerichtet als Assistent `user`/`reconfigure` → `roads` → `directions`:
  - Mittelpunkt und Radius per Karte (Standard 10 km, höchstens 100 km – `geo.py` rechnet flach, das ist bis ~100 km genau).
  - Quellen pro Bereich (fehlt die Angabe: alle).
  - Autobahnen (nur wenn die Autobahn-Quelle aktiv ist) und Stau-Schwelle in Minuten (nur mit INRIX, Standard 10).
  - Optional Fahrtrichtungen: Auswahl aus den real vorkommenden „Start -> Ziel“-Richtungen; Anschlussstellen und Meldungen ohne Richtung bleiben immer sichtbar.
- `area_subentries()` ersetzt `get_subentries_of_type()`, das es in HA 2026.3 noch nicht gibt. Mindestversion ist 2026.3 (`hacs.json`), weil HA erst ab dort die Brand-Bilder aus `custom_components/streckenwacht/brand/` lädt.

### Datenfluss

- **Ein `DataUpdateCoordinator` pro Quelle** (`coordinator.py`), `always_update=False`. Er lädt einmal pro Abruf alles, was alle Bereiche zusammen brauchen (Autobahn: Vereinigungsmenge der gewählten Autobahnen; MobiData: eine landesweite Datei; Stuttgart: zwei Layer). Jeder Bereich filtert lokal über `ObservationArea.contains()`; Abstand zu Linien wird zum Segment gemessen, nicht nur zu den Stützpunkten.
- **Provider** (`providers/`) sind reines Python ohne HA-Importe, bekommen nur eine `aiohttp`-Session und werfen bei jedem Fehler `ProviderError`. Bedingte Abrufe per ETag (`If-None-Match`/304) stecken in der Basisklasse.
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
| `diagnostics.py` | Diagnose-Download; Koordinaten der Bereiche geschwärzt (landet in öffentlichen Issues) |

`model.py`, `geo.py`, `summary.py`, `changes.py` und die Provider importieren nichts aus HA und werden lokal getestet.

### Entities (je Bereich ein Gerät)

| Entity | Beispiel-ID | Verhalten |
|---|---|---|
| Kalender | `calendar.streckenwacht_arbeitsweg` | Jedes Zeitfenster ein Eintrag (Tagesbaustellen mit mehreren Fenstern → mehrere Einträge). Stau/Unfall/Warnung ohne Ende reichen bis jetzt + 30 min (`LIVE_SPAN`), sonst würden sie über den ganzen sichtbaren Zeitraum gestreckt. |
| Störung aktiv | `binary_sensor.streckenwacht_arbeitsweg_disruption_active` | An bei aktiver Sperrung, Unfall oder Stau ab Stau-Schwelle. Dauerbaustellen zählen bewusst nicht. Keine `device_class` (Anzeige Ein/Aus). |
| Ereignisse | `sensor.streckenwacht_arbeitsweg_events` | Anzahl aktiver Meldungen; Attribute je Typ, `by_source`, `events` (bis zu 20, schwerste zuerst) |
| Reisezeitverlust | `sensor.streckenwacht_arbeitsweg_travel_time_loss` | Größter aktueller Verlust in Minuten; nur mit INRIX |
| Ereignisänderung | `event.streckenwacht_arbeitsweg_event_change` | `new`/`ended`. Erste Daten einer Quelle und alles nach einer Bereichsänderung (Fingerprint der Einstellungen) werden still gelernt; ein Ausfall löst kein `ended` aus. Pro Ereignis ein State-Write, damit Automationen jedes sehen. |

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

### Stadt Stuttgart (WFS `https://geoserver.stuttgart.de/geoserver/wfs`)

- Layer `GEOLINE_FLEX:A66_BAUM_BAUSTELLEN_DATE_im_Bau_EPSG25832` und `…_geplant_EPSG25832`; mit `outputFormat=application/json&srsName=EPSG:4326` liefert der Server GeoJSON in WGS84 – kein GML, kein `pyproj`.
- Nur „Vorbehaltsstraßennetz“, ~60 Punkte. Stabile ID ist `BAUSTELLENNUMMER` (GeoServer-Feature-IDs nicht). Gleiche Nummer in beiden Layern → „im Bau“ gewinnt.
- `ANFANG`/`ENDE` sind Freitext: meist `dd.mm.yyyy`, daneben „Ende Dez. 2026“, „Mitte Okt. 2026“ (Anfang = 1., Mitte = 15., Ende = Monatsletzter). Bei Fehlschlag bleibt die Meldung erhalten. `BEGINN_UHRZEIT`/`ENDE_UHRZEIT` ergänzen Start bzw. Ende zu einem durchgehenden Zeitraum; `ZEITL_REGELUNG: werktags` wird nicht in Einzeltage zerlegt, sondern in der Beschreibung genannt. „Vollsperrung“ in der Auswirkung → `closure`.
- Qualität: am schwächsten (nur Hauptachsen, bekannte Koordinationsprobleme mit Versorgern).

## 3. Entscheidungen

- **Eine Integration mit Providern** statt mehrerer: gemeinsame Entities pro Bereich, ein Config-Flow, ein HACS-Eintrag.
- **Ein Entry + Subentries je Bereich, ein Coordinator je Quelle** (siehe Architektur).
- **Keine Webcams** – keine Quelle liefert öffentliche Bilder.
- **Keine Deduplizierung zwischen Quellen** in v1. Messung (2026-10-02, 10 km um Stuttgart-Kaltental): 64 quellenübergreifende Paare ≤ 300 m, fast alle aber verschiedene Straßen am selben Ort. Ein späteres Verfahren muss dieselbe Straße verlangen.
- **„Störung aktiv“ nur für Sperrung, Unfall, Stau ab Schwelle** – sonst wäre es wegen Dauerbaustellen praktisch immer an.
- **Projektlizenz MIT** (HACS-üblich; Apache-2.0 brächte hier keinen Mehrwert).
- **Repo** `github.com/streckenwacht/integration` (Organisation), `codeowners` `@n42net`.

## 4. Risiken, Lizenzen, Recht (keine Rechtsberatung)

- **Namensnennung** je Quelle in `const.ATTRIBUTION` und im Attribut `attribution`: Stuttgart CC BY 4.0, MobiData BW DL-DE-BY-2.0, Autobahn GmbH (keine erklärte Lizenz, Nennung als gute Praxis), zusätzlich „Verkehrslage: INRIX“.
- **INRIX** (entschieden 2026-10-02): keine erklärten Nutzungsbedingungen; die Daten werden offen und auch kommerziell genutzt. Streckenwacht verbreitet nichts weiter – jede Instanz ruft den öffentlichen Endpunkt selbst ab; Risiko gering. Vorsorge: `upstream="inrix"` und die abschaltbare Option. **Warnungs-Fixtures (echte INRIX-Daten) nur lokal, nie committen** (`.gitignore`; aus der Historie entfernt); Tests nutzen ein eingebettetes Beispiel.
- **Zurückgestellt** (Entscheidung des Projektinhabers): Impressumsfrage und Anfrage bei der Autobahn GmbH zu INRIX – erst beim öffentlichen Bewerben wieder aufgreifen. Bis dahin keine Spenden-Links oder Werbung.
- **API-Stabilität:** keine Quelle ist versioniert oder hat ein SLA, Rate Limits sind unbekannt → defensiv parsen, konservativ pollen, ETag nutzen.

## 5. Arbeitsweise

- **Branches:** Entwicklung auf `dev` (CI läuft dort). `main` erhält nur freigegebene Stände, weil die HACS-Installation `main` bzw. den Releases folgt.
- **Release:** Version in `manifest.json` und `const.py` (`VERSION`) setzen → CI auf `dev` grün → `main` per Fast-Forward → `gh release create vX.Y.Z` (Vorabversionen mit `--prerelease`). HACS zeigt den Tag des neuesten Releases. Reine README-Korrekturen ohne Release nach `main` nur nach Rücksprache.
- **Tests:** Logik- und Provider-Tests lokal (`uv run pytest --ignore=tests/ha`); HA-Tests (`tests/ha/`, `pytest-homeassistant-custom-component`) nur in GitHub Actions, weil die Bibliothek unter Windows nicht läuft. CI-Jobs: `test` (aktuelles HA), `compat` (HA 2026.3), `hassfest`, `hacs`.
- **Werkzeuge:** `tools/fetch_fixtures.py` (Fixtures aktualisieren), `tools/live_check.py` (Live-Abruf außerhalb von HA), `tools/mobilithek_scan.py` (Mobilithek-Katalog prüfen), `tools/brand/` (Bilder neu erzeugen).
- Entwickelt wird gegen eine produktive HA-Instanz: neue Provider-Logik zuerst außerhalb von HA testen.

## 6. Backlog

- **Weitere Datenquellen:** Planung und geprüfte Endpunkte in [`DATENQUELLEN.md`](DATENQUELLEN.md). Empfehlung: generischer WFS/GeoJSON-Provider, beginnend mit dem norddeutschen WFS (SH, MV, NI, HH).
- **Kartenansicht:** eigene Lovelace-Karte mit der ohnehin vorhandenen Geometrie.
- **Strecke statt Kreis:** Korridor entlang einer Route (aus dem Beta-Test).
- **Autobahn-Abschnitte** („A81 zwischen AS X und AS Y“): Abschnittsnamen sind Freitext – zugunsten der Fahrtrichtungen zurückgestellt.
- **Deduplizierung** nur bei gleicher Straße (siehe Entscheidungen).
- **Langzeitstatistik**, z. B. Reisezeitverlust pro Monat.
- **Bekanntmachen:** erst simon42 Community, danach HA Community (Custom Integrations); später ggf. Awesome Home Assistant und die HACS-Default-Liste.
