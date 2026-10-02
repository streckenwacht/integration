# Streckenwacht – Übergabedokument für die Implementierung

> Zweck dieses Dokuments: Vollständiger Kontext + Spezifikation, damit eine andere KI (oder ein anderer Entwickler) direkt mit der Implementierung als Home-Assistant-Custom-Integration (HACS) beginnen kann. Dieses Dokument beschreibt **was** gebaut werden soll und **warum**, nicht fertigen Code – die Implementierung selbst ist die nächste Aufgabe.

---

## 0. Umsetzungsstand (2026-10-02)

Dieses Dokument war die Ausgangsspezifikation. Die Integration ist inzwischen umgesetzt; **maßgeblich ist der Code**, die Abschnitte unten sind dort korrigiert, wo die echten Daten anders waren.

| Schritt | Stand |
|---|---|
| 1 Grundgerüst, 2 Autobahn, 3 MobiData BW, 4 Stuttgart | fertig, gegen Fixtures und Live-APIs getestet |
| 5 Coordinator, Config-Flow mit Subentries, Repairs | fertig |
| 6 Entities (Kalender, Binärsensor, Sensoren, Event) | fertig |
| 7 Installation auf der produktiven Instanz per HACS | v0.1.0b1 und v0.1.0b2 laufen |
| 8 Politur (README, Diagnose, Handover) | in Arbeit |

**Wichtigste Abweichungen vom ursprünglichen Plan** (Details in den genannten Abschnitten):
- Stuttgart als GeoJSON/WGS84 direkt vom GeoServer – kein GML, kein `pyproj` (2.3, 2b).
- Autobahn-API ohne Endfeld und ohne Umkreissuche: Zeiten aus dem Freitext, Autobahnen werden pro Bereich gewählt (2b).
- Datenmodell mit Zeitfenstern (`periods`) und `upstream`, ohne `raw` (3).
- Bereiche als Config-Subentries mit eigener Quellenauswahl und optionalen Fahrtrichtungen; ein Coordinator pro Quelle (10).
- „Störung aktiv“ zählt nur Sperrung/Unfall/Stau, nicht Dauerbaustellen; zusätzlicher Sensor „Reisezeitverlust“ (10).
- INRIX-Daten über Option abschaltbar, Warnungs-Fixtures nur lokal (6).
- Bedingte Abrufe per ETag (304) gegen unnötiges Datenvolumen.
- Entity-IDs sind englisch (HA bildet sie aus den englischen Namen), z. B. `binary_sensor.streckenwacht_<bereich>_disruption_active`.

**Arbeitsweise:** Entwicklung auf `dev`, `main` nur für Releases (die produktive HACS-Installation folgt `main`).

**Offen vor v0.1.0:** Beta-Erfahrungen (Nachtsperrungen, Event-Häufigkeit bei INRIX-Staus).

**Zurückgestellt (Entscheidung des Projektinhabers, 2026-10-02):** Impressumsfrage und Anfrage bei der Autobahn GmbH zu INRIX – erst wieder aufgreifen, wenn das Projekt öffentlich beworben werden soll.

---

## 1. Projektüberblick

| | |
|---|---|
| **Name** | Streckenwacht |
| **Domain (HA)** | `streckenwacht` |
| **Tagline** (kurz, für HACS-Listing/GitHub-Beschreibung) | „Baustellen, Sperrungen, Staus und Unfälle auf deiner Strecke." |
| **README-Intro-Satz** (präziser, direkt unter der Tagline) | „Verfolge Baustellen, Sperrungen, Staus und Unfälle auf frei wählbaren Straßen oder in einer selbst definierten Umgebung – z. B. deiner Pendelstrecke." |
| **Typ** | Home-Assistant Custom Integration, verteilt über HACS (Custom Repository, später ggf. HACS-Default) |
| **Zielplattform** | Home Assistant Core (Config-Entry-basiert, `async`, moderne HA-Integration-Patterns) |
| **Lizenz des Projekts** | **MIT** (entschieden – siehe Begründung in Abschnitt 8a) |
| **Sprache** | Code auf Englisch (HA-Konvention), UI-Strings via `strings.json`/`translations/` auf Deutsch + Englisch |

### Kurzbeschreibung

Für Baustellen/Verkehrsstörungen in Deutschland existiert bislang **keine** Home-Assistant-Integration (am 2026-10-02 nachrecherchiert: HACS-Default-Liste, GitHub-Code-Suche nach `verkehr.autobahn.de`, HA-Forum – nichts gefunden; vergleichbare Integrationen gibt es nur für Schweden, Dänemark, Niederlande). Mehrere Stellen stellen dafür jedoch offene, kostenlose Daten bereit. Streckenwacht kombiniert diese Quellen in **einer** Integration und lässt Nutzer für selbst definierte „Beobachtungsbereiche" (Ort/Zone + Radius, optional Straße/Richtung) Baustellen, Sperrungen, Staus und Unfälle in Home Assistant sichtbar machen – als Kalender, Sensoren und Events, nutzbar für Automationen (z. B. „warne mich, wenn auf meiner Pendelstrecke eine neue Sperrung auftaucht").

### Namensgeschichte & Markenidentität

"Streckenwacht" – **wacht über deine Strecke.** Ein kurzer, warmer Absatz in dieser Richtung eignet sich gut als Einstieg in die README, statt gleich mit der technischen Tagline zu starten:

> Streckenwacht wacht über deine Strecke – ob Autobahn, Bundesstraße oder dein täglicher Arbeitsweg. Baustellen, Sperrungen, Staus und Unfälle, direkt in deinem Home Assistant.

**Icon-Konzept (entschieden):** Ein Design-Konzept wurde ausgearbeitet und liegt separat unter `https://claude.ai/artifact/VbLtuZGvQcFd54MccfXHXb` (drei Artboards: Icon-Kachel, Lesbarkeitstest bei 128/64/40/24px, README-Header-Lockup). Konzept: eine perspektivische Fahrbahn mit gestrichelter Mittellinie, die nach oben in ein leuchtendes Warn-Beacon mit Halo übergeht – auf einer abgerundeten Kachel. Bildet die Namensbedeutung ("wacht über deine Strecke") direkt ab.
- **Farben (final, nach Iteration):** Kachel-Hintergrund `#005B8C` – das ist **RAL 5017 "Verkehrsblau"**, die tatsächliche Farbe deutscher Autobahn-Wegweiser ([Wikipedia: Verkehrsblau](https://de.wikipedia.org/wiki/Verkehrsblau)) – bewusst gewählt statt eines beliebigen Blautons, weil es einen echten, erkennbaren Bezug zur Autobahn-API (Kerndatenquelle) herstellt. Beacon/Mittellinie `#F5A623` (warmes Amber-Gold, Signalfarbe, guter Kontrast zum Verkehrsblau). Fahrbahn `#FBF7EE` (warmes Off-White).
  - Verworfene Zwischenschritte (zur Nachvollziehbarkeit): ursprünglich dunkles Navy `#1B2430` (wirkte zu schwer/wenig einladend), dann zwei freundlichere Testvarianten (`#3E7CB1` Blau, `#2E8F82` Petrol) – am Ende fiel die Wahl auf das bedeutungsvollere Verkehrsblau statt einer der beiden generischen Optionen.
- Wortmarke/Headline-Font: „Space Grotesk" (Google Fonts, Weights 500/700), Headline-Farbe ebenfalls `#005B8C`.
- **Alle Bilddateien liegen fertig im Paket** (SVG-Master, HA-Brand-PNGs, GitHub-Bilder, Favicons, Größenreihe 16–2048px). Übersicht, Einsatzregeln und Regenerierung: `docs/BRAND.md`. Die Wortmarke ist in den SVGs in Pfade umgewandelt, braucht also keine installierte Schrift.
- Für Größen ≤ 32px gibt es eine **vereinfachte Mini-Variante** (ein Mittelstrich, größeres Beacon, kein Halo) – die volle Variante verschwimmt dort.

### Warum eine Integration und nicht mehrere?

Bewusste Architekturentscheidung: **eine** Integration (`streckenwacht`) mit mehreren **Providern** als internes Plugin-Muster, statt drei separate HACS-Integrationen. Gründe:
- Nutzer wollen ein gemeinsames Set an Entities/Kalender pro Beobachtungsbereich, nicht drei getrennte Integrationen manuell kombinieren.
- Gemeinsames Datenmodell ermöglicht spätere Deduplizierung zwischen Quellen.
- Einfachere Discoverability in HACS (ein Eintrag statt drei).
- Setup-Aufwand für Nutzer geringer (ein Config Flow statt drei).

---

## 2. Datenquellen (Details für die Implementierung)

### 2.1 Autobahn GmbH – Autobahn-API

- **Base-URL:** `https://verkehr.autobahn.de/o/autobahn`
- **Auth:** keine (öffentliche API, kein API-Key nötig)
- **Struktur:** Pro Autobahn (z. B. `A8`) und Kategorie ein Endpoint:
  - `GET /{roadId}/services/roadworks` – Baustellen
  - `GET /{roadId}/services/closure` – Sperrungen
  - `GET /{roadId}/services/warning` – Warnmeldungen (**inkl. Staus und Unfälle**, nicht nur Baustellen!)
  - `GET /{roadId}/services/webcam` – Webcams (siehe Risiko unten: liefert aktuell leere Arrays)
  - `GET /{roadId}/services/parking_lorry` – LKW-Parkplätze
  - `GET /{roadId}/services/electric_charging_station` – E-Ladesäulen
  - Liste aller `roadId`s: `GET /` → `{"roads": ["A1", …]}` (**verifiziert**, 113 Einträge, davon ein Datenfehler: `"A60 "` mit Leerzeichen neben `"A60"`, liefert nur leere Listen → trimmen und deduplizieren).
  - **Es gibt keine Geo-Abfrage** (kein „alle Meldungen im Umkreis"). Abgefragt wird immer pro Autobahn → siehe 2b.
- **Wichtige Felder** (Stand Konzeption; **verifizierte Abweichungen siehe Abschnitt 2b**):
  - `identifier` – eindeutige ID der Meldung
  - `title`, `subtitle` – Kurzbeschreibung
  - `description` – Freitext (Array von Strings)
  - `startTimestamp` – Beginn
  - `extent` – räumliche Ausdehnung
  - `coordinate` – Lat/Lon
  - `geometry` – GeoJSON LineString (Streckenverlauf)
  - `impact` – Schweregrad/Auswirkung
  - `display_type` – Kategorie-Hinweis
  - `delayTimeValue` – Reisezeitverlust in Minuten (**bestätigt vorhanden**, z. B. "Reisezeitverlust: 78 Minuten (zunehmend)") → ermöglicht Stau-Erkennung mit Zeitangabe
  - `abnormalTrafficType` – Typ der Verkehrsstörung
  - `source` – Herkunft der Meldung: `"eva"` = offizielle Meldung (z. B. Unfall, Fahrbahnschaden), `"inrix"` = kommerzieller Anbieter (Verkehrsfluss-abgeleitete Stau-Daten) → **relevant für Lizenzfrage, siehe Risiken**
- **Keine offizielle, explizit genannte Lizenz** für die API-Daten selbst gefunden. Vor Veröffentlichung prüfen (Nutzungsbedingungen auf verkehr.autobahn.de bzw. bund.dev, falls dort gelistet).
- **Rate Limits:** nicht dokumentiert getroffen – bei Implementierung defensiv pollen (z. B. alle 5–15 Minuten pro Beobachtungsbereich) und Caching/ETag-Handling prüfen.

### 2.2 MobiData BW (Baden-Württemberg)

- **Portal:** mobidata-bw.de (Open-Data-Plattform des Landes BW / NVBW), technische API-Basis: `https://api.mobidata-bw.de`
- **Baustellen – konkret verifizierter Endpoint (empfohlen: GeoJSON-Variante verwenden, nicht Datex II):**
  - `GET https://api.mobidata-bw.de/datasets/traffic/roadworks/roadworks_geojson.json`
  - Alternativ vorhanden, aber **nicht empfohlen** (mehr Parsing-Aufwand): `roadworks_svzbw.datex2.xml` (Datex II/XML), `roadworks_cifs.json` (CIFS)
  - **Kein API-Key nötig**, aber die Plattform bittet um einen aussagekräftigen `User-Agent`-Header zur Identifikation der Anwendung.
  - **Koordinatensystem: WGS84 (EPSG:4326)** – lat/lon direkt nutzbar, **keine Reprojektion nötig** (im Gegensatz zu Stuttgart, siehe 2.3).
  - **Bestätigte Struktur** (Live-Check bei Konzeption: 54 Features; am 2026-10-02: **977 Features, 2,6 MB** – siehe 2b): Standard-GeoJSON-`FeatureCollection`, `geometry` als `LineString`, `properties` mit:
    - `id` – eindeutige Kennung
    - `type` – z. B. `"CONSTRUCTION"`, `"ROAD_CLOSED"`
    - `subtype` – Unterkategorie
    - `description` – Kurzbeschreibung
    - `reference` – Quellenangabe (`"MobiData BW"`)
    - `street` – Straßenname/Strecke
    - `direction` – `"BOTH_DIRECTIONS"` | `"ONE_DIRECTION"`
    - `starttime` / `endtime` – ISO 8601 mit Timezone
  - Beispiel-Feature:
    ```json
    {
      "type": "Feature",
      "geometry": {"type": "LineString", "coordinates": [[8.961428, 48.665755], [8.961231, 48.665646]]},
      "properties": {
        "id": "2454613-14973690-14973691-14973706.001",
        "type": "CONSTRUCTION",
        "description": "K1077 Erdlager DEGES",
        "street": "K1077 Böblingen-Gärtringen",
        "direction": "ONE_DIRECTION",
        "starttime": "2024-07-14T00:00:00.000+02:00",
        "endtime": "2026-12-31T23:59:00.000+01:00"
      }
    }
    ```
  - Technische API-Doku/Integrationsplattform: `https://dev-ipl.mobidata-bw.de/` (nennt u. a., dass die Endpunkte offen und ohne Zugangsdaten nutzbar sind).
- **Weitere Datensätze** (nicht Kernbestandteil von v1, aber vorhanden): **Parkraum (ParkAPI/p-count)**, **E-Ladesäulen**.
- **Webcams**: **aktuell NICHT öffentlich verfügbar** – Zitat aus der Datensatz-Doku: „Auf Grund der aktuellen sicherheitspolitischen Lage werden die Webcam-Bilder bis auf Weiteres nicht frei veröffentlicht … nur für behördeninterne Nutzung." Kontakt für Rückfragen: `mobidata-bw@nvbw.de`
- **Lizenz:** „Datenlizenz Deutschland – Namensnennung 2.0" (Attribution erforderlich)
- **Fazit für die Implementierung:** Dank des GeoJSON-Endpoints mit WGS84-Koordinaten ist dieser Provider **deutlich einfacher** zu bauen als ursprünglich angenommen – vergleichbar mit dem Aufwand für die Autobahn-API, (Stuttgart ist inzwischen ebenfalls per GeoJSON/WGS84 abrufbar, siehe 2.3.)

### 2.3 Stadt Stuttgart – Baustellenkalender (Tiefbauamt)

- **Quelle:** OpenData@Stuttgart, veröffentlicht via WFS (GeoServer)
- **Endpoint (verifiziert):** `https://geoserver.stuttgart.de/geoserver/wfs`, zwei Layer:
  - `GEOLINE_FLEX:A66_BAUM_BAUSTELLEN_DATE_im_Bau_EPSG25832` (laufend)
  - `GEOLINE_FLEX:A66_BAUM_BAUSTELLEN_DATE_geplant_EPSG25832` (geplant)
- **Format:** ~~GML/XML (kein GeoJSON)~~ → **korrigiert:** Der GeoServer liefert mit `outputFormat=application/json&srsName=EPSG:4326` direkt **GeoJSON in WGS84**. Damit entfallen GML-Parsing und `pyproj` komplett.
- **Koordinatensystem:** nativ EPSG:25832 (UTM 32N), per `srsName=EPSG:4326` serverseitig umgerechnet (4 Nachkommastellen ≈ 10 m, ausreichend).
- **Umfang:** nur „Vorbehaltsstraßennetz" (Hauptverkehrsachsen/Radrouten), nicht alle Straßen der Stadt
- **Aktualisierung:** täglich
- **Relevante Felder:**
  - `VERKEHRSAUSWIRKUNG` – Art der Auswirkung (z. B. Teilsperrung, Vollsperrung)
  - `DETAILS_STANDORT` – Ortsbeschreibung
  - `ANFANG` – Startdatum (**Freitext-Format**, Parsing nötig)
  - `STRASSENNAME`
  - `ENDE` – Enddatum (**Freitext-Format**, Parsing nötig)
  - `ZEITL_REGELUNG` – zeitliche Regelung
  - `ART_ARBEIT` – Art der Arbeiten
  - `KOORDINATE_X`, `KOORDINATE_Y` – UTM-Koordinaten
  - `STATUS`
- **Lizenz:** CC BY 4.0 (Namensnennung Stadt Stuttgart erforderlich)
- **Beispieldaten aus Live-Test** (zur Orientierung, nicht als stabile API-Garantie): Werastraße, Teilsperrung 28.09.–10.10.2026; Grazer Straße, Vollsperrung bis 20.11.2026.

### 2a. Datenqualität der drei Quellen – Einschätzung

Diese Einschätzung stammt aus einer gezielten Recherche zur Frage, ob die Daten gut/aktuell genug sind, damit Nutzer die Integration gerne verwenden würden. Fazit vorweg: **unterschiedlich gut**, mit klarer Rangfolge.

- **Autobahn-API (am stärksten):** Ein kommerzieller Drittanbieter ([autobahn-baustellen.de](https://www.autobahn-baustellen.de/download-und-api-zugang/)) pollt exakt diese API alle 10 Minuten, um daraus ein bezahltes Unfall-Produkt zu bauen – starkes Indiz für deutlich häufigere Aktualisierung als "täglich". Live-Test zeigte plausible, aktuelle Einträge. Kein offiziell dokumentiertes SLA, aber offenbar im Praxiseinsatz verlässlich genug für kommerzielle Weiterverwendung.
- **MobiData BW (rechtlich gut abgesichert):** Die Bereitstellung basiert auf der **EU-Verordnung 2022/670** (Pflicht zur Echtzeit-Verkehrsdatenbereitstellung nach FRAND-Prinzipien) – keine freiwillige Hobby-Veröffentlichung, sondern eine gesetzlich verankerte Pflicht des Landes. Deckt Bundes-, Landes- und Kreisstraßen in BW ab, kommunale Straßen nur vereinzelt (siehe 2b).
- **Stuttgart (am schwächsten):** Zwei strukturelle Schwächen: (1) deckt per Definition nur das "Vorbehaltsstraßennetz" ab, keine Nebenstraßen/Notreparaturen; (2) ein Lokaljournalismus-Artikel ([wilih.de](https://wilih.de/stuttgart-und-seine-baustellen)) beschreibt bekannte Koordinationsprobleme zwischen Versorgern/Telekommunikationsfirmen und der Stadtverwaltung – Sperrungen können dadurch verspätet oder unvollständig im städtischen System landen, unabhängig von der technischen Qualität der WFS-Schnittstelle selbst.

**Konsequenz für die Implementierung:** Für den Kernfall "Pendler auf Autobahn/Bundesstraße warnen" ist die Datenlage gut genug. Für "zeig mir jede Baustelle in meiner Straße" ist sie strukturell unvollständig – das ist keine Schwäche der Integration, sondern der Datenquellen selbst. Genau deshalb existiert der Erwartungsmanagement-Textbaustein in Abschnitt 13.

### 2b. Verifikation gegen die Live-APIs (2026-10-02)

Fixtures mit `tools/fetch_fixtures.py` geladen (`tests/fixtures/`). Diese Befunde haben Vorrang vor den Beschreibungen in 2.1–2.3.

**Autobahn-API**
- **Kein Endzeitpunkt als Feld.** Weder in den Listen noch im Detail-Endpoint (`/details/roadworks/{id}`). Das Ende steht nur im Freitext-Array `description`, in drei Varianten:
  - `"Ende: 01.05.27 um 00:00 Uhr"` (häufigste, Langzeitbaustellen)
  - `"06.10.26 15:30 bis zum 07.10.26 05:00 Uhr."`
  - mehrere Zeitfenster, je eine Zeile: `"05.10.26 von 10:00 bis 16:30 Uhr"` (Tagesbaustellen) → ein Kalendereintrag pro Fenster
- `startTimestamp` fehlt bei rund der Hälfte der Baustellen (bei allen `SHORT_TERM_ROADWORKS`) → Start ebenfalls aus `description` parsen. Format, wenn vorhanden, uneinheitlich: `"2026-10-02T10:01:00Z"` bzw. `"2026-07-31T08:30:00+02:00"`.
- Feldtypen: `isBlocked`, `delayTimeValue`, `averageSpeed`, `startLcPosition` sind **Strings** (`"false"`, `"38"`). Koordinate: `coordinate.lat` / `coordinate.long` (nicht `lon`). `extent`/`point` sind Komma-Strings.
- `display_type`: `ROADWORKS`, `SHORT_TERM_ROADWORKS`, `CLOSURE`, `CLOSURE_ENTRY_EXIT`, `WARNING`. `future: true` = noch nicht begonnen.
- `impact` ist ein Objekt (`lower`, `upper`, `symbols[]` = Fahrstreifen-Symbolik), kein Schweregrad.
- `source` existiert **nur bei `warning`** – und war dort in der Stichprobe (A8: 15, A81: 7) **zu 100 % `"inrix"`**. Ein `"eva"`-Eintrag kam nicht vor. `abnormalTrafficType`: `QUEUING_TRAFFIC`, `SLOW_TRAFFIC`, `HEAVY_TRAFFIC`, `UNSPECIFIED_ABNORMAL_TRAFFIC` (live gesehen) → Regel: jeder gesetzte Typ oder `delayTimeValue` > 0 = Stau.
  → **Stau-Daten stammen praktisch ausschließlich von INRIX.** Die Lizenzfrage (Abschnitt 6) betrifft damit nicht einen Randaspekt, sondern das komplette Feature „Staus".
- Unfälle haben keine eigene Kategorie; sie würden als `warning` erscheinen (in der Stichprobe: keine).
- Die Abfrage `A8` enthält auch Meldungen anderer Straßen (z. B. A995-Baustelle mit Titel „A8 | München-Süd – Sauerlach"). Identifier waren zwischen A8 und A81 überschneidungsfrei.
- Datenmenge: A8 Baustellen ≈ 700 KB (überwiegend Geometrie), alle drei Dienste zweier Autobahnen ≈ 1,9 MB.
- **Konsequenz Config-Flow:** Weil es keine Geo-Abfrage gibt, muss der Nutzer die Autobahnen auswählen (Multi-Select aus `GET /`); Zone + Radius filtert dann lokal. Alle 112 Autobahnen × 3 Dienste pro Poll abzufragen wäre unverhältnismäßig.
- Lizenz: weiterhin **nicht auf der API deklariert**. Dritte (z. B. `maschinenlesbar-org/autobahn-cli`) nennen DL-DE-BY-2.0 nur „by analogy".

**MobiData BW**
- 977 Features (statt 54), 2,6 MB, eine einzige landesweite Datei → **ein** Download pro Poll für alle Beobachtungsbereiche, Filterung lokal.
- **Enthält doch kommunale Straßen:** `street` beginnt bei 361 von 977 Features mit „Gemeindestraße". Außerdem einzelne Autobahn-Abschnitte (`A5`, `A98`) → mögliche Dubletten mit der Autobahn-API. Verteilung: G 361, L 234, B 203, K 177, A 2.
- `type` nur `CONSTRUCTION` / `ROAD_CLOSED`, `subtype` nur `""` / `ROAD_CLOSED_CONSTRUCTION`. `reference` immer `"MobiData BW"`.
- Geometrie: 975 × `LineString`, 2 × `Point` → beide Typen unterstützen. **Die `Point`-Features haben vertauschte Koordinaten** (`[lat, lon]` statt `[lon, lat]`) → der Provider repariert Positionen, deren erster Wert im deutschen Breitengrad-Bereich liegt.
- `description` ist teils generisch („Bauphase“) oder beginnt mit „keine Beschreibung vorhanden“; Titel wird daher aus `street` + `description` gebildet (Logik in `providers/mobidata_bw.py`).
- Viele Langläufer (Start 2015, Ende bis 2037). Kein Stau/Unfall-Inhalt – nur Baustellen/Sperrungen.

**Stadt Stuttgart**
- 57 Features (47 im Bau, 10 geplant), ausschließlich `Point`.
- Stabile ID: `BAUSTELLENNUMMER` (z. B. `"7374/2026"`, eindeutig). Die GeoServer-Feature-ID (`…EPSG25832.65523`) ist vermutlich nicht stabil.
- Datumsformate `ANFANG`/`ENDE`: überwiegend `dd.mm.yyyy`; daneben `"Ende Dez. 2026"`, `"Mitte Okt. 2026"`, `"Anfang April 2027"` (abgekürzte und ausgeschriebene Monatsnamen). Mapping-Vorschlag: Anfang = 1., Mitte = 15., Ende = Monatsletzter.
- Zusätzliche Felder, die das Handover nicht nannte: `BEGINN_UHRZEIT`, `ENDE_UHRZEIT` (z. B. `"22:30"`/`"05:00"` bei Nachtbaustellen), `STADTTEIL`, `STADTBEREICH`, `BAUSTELLENNUMMER`, `VERKEHRSAUSWIRKUNG_GESAMT`, `ZUSAETZL_INFO`. `ZEITL_REGELUNG`: `durchgehend` / `werktags`.
- Umsetzung (Schritt 4): `BEGINN_UHRZEIT` gehört zu `ANFANG`, `ENDE_UHRZEIT` zu `ENDE` → **ein** durchgehender Zeitraum; ohne Uhrzeit ganztägig bis Ende des letzten Tages. `werktags` wird **nicht** in Einzeltage zerlegt (unklar, ob „werktags 22:30–05:00“ jede Nacht meint), sondern als „Zeitliche Regelung: werktags“ in der Beschreibung genannt. Typ: „Vollsperrung“ im Auswirkungstext → `closure`, sonst `roadworks`. Gleiche `BAUSTELLENNUMMER` in beiden Layern → „im Bau“ gewinnt.

---

## 3. Datenmodell (gemeinsames Schema)

Alle drei Quellen werden auf ein einheitliches Modell normalisiert. **Umgesetzt in `custom_components/streckenwacht/model.py`** (Schritt 1, 2026-10-02) – der Code ist maßgeblich. Abweichungen vom ursprünglichen Vorschlag, begründet durch die verifizierten Daten (2b):

- `event_type` ist ein Enum `EventType`: `roadworks`, `closure`, `traffic_jam`, `accident`, `warning`. **Unfälle** werden per Stichwort „Unfall“ im Text von Autobahn-Warnungen erkannt (entschieden 2026-10-02), INRIX-Meldungen mit Stau-Typ werden `traffic_jam`.
- `start`/`end` sind ersetzt durch `periods: tuple[Period, ...]` (Zeitfenster, `None` = offen). Tagesbaustellen haben mehrere Fenster, jedes wird ein Kalendereintrag. `start`/`end` gibt es weiter als abgeleitete Properties.
- Neu: `upstream` (z. B. `"inrix"`) – damit lassen sich INRIX-Daten gezielt abschalten, falls die Lizenzfrage negativ ausgeht.
- `attribution` ist eine Property (Text je Quelle in `const.ATTRIBUTION`), kein Feld.
- `raw` entfällt (977 MobiData-Einträge × Geometrie kosten unnötig Speicher). `geometry` bleibt, darf aber nie als State-Attribut erscheinen.
- Neu: `ObservationArea` (Name, Mittelpunkt, Radius, gewählte Autobahnen) mit `contains(event)`. Entfernung zu Linien wird zum Segment gemessen, nicht nur zu den Stützpunkten (`geo.py`).

**Deduplizierung** (bekanntes offenes Problem, siehe Risiken): Für den ersten Wurf reicht es, Events pro Provider getrennt zu halten und nicht automatisch zusammenzuführen. Eine Dedup-Heuristik (räumliche Nähe + zeitliche Überlappung + ähnlicher Titel) ist ein sinnvolles späteres Feature, kein Blocker für v1.

---

## 4. Architektur / Verzeichnisstruktur

```
custom_components/streckenwacht/
  __init__.py            # Setup, Config-Entry-Handling, Coordinator-Erzeugung pro Provider
  manifest.json           # domain, name, codeowners, requirements, iot_class, config_flow: true
  const.py                # DOMAIN, CONF_-Konstanten, Standard-Update-Intervalle
  model.py                 # StreckenwachtEvent, Period, ObservationArea (siehe oben)
  geo.py                   # Entfernung Punkt ↔ GeoJSON-Geometrie
  coordinator.py           # StreckenwachtDataUpdateCoordinator (generisch, pro Provider-Instanz)
  config_flow.py           # Multi-Step: Provider wählen → Beobachtungsbereiche definieren
  strings.json / translations/de.json, en.json
  providers/
    __init__.py            # gemeinsames Provider-Interface (ABC): async_fetch(areas), ProviderError
    autobahn.py             # Autobahn GmbH API Client + Mapping auf StreckenwachtEvent
    mobidata_bw.py           # MobiData BW Client + Mapping
    stuttgart.py              # Stuttgart WFS Client (GeoJSON/WGS84 direkt vom Server, Freitext-Datumsparsing) + Mapping
  calendar.py               # ein Kalender pro Beobachtungsbereich, Events = StreckenwachtEvent-Zeitraum
  binary_sensor.py          # z. B. "aktive Sperrung im Bereich X" (on/off)
  sensor.py                  # Anzahl aktueller Ereignisse, evtl. "nächstes Ereignis" mit Attributen
  event.py                   # HA-Event-Entity: feuert bei neuem/beendetem Ereignis
```

### Provider-Interface

**Umgesetzt in `custom_components/streckenwacht/providers/__init__.py`.** Abweichend vom ursprünglichen Konzept bekommt ein Provider **alle** Beobachtungsbereiche und lädt einmal pro Poll, was sie zusammen brauchen: `async_fetch(areas) -> list[StreckenwachtEvent]`. Das Filtern pro Bereich passiert danach über `ObservationArea.contains()`. Provider importieren nichts aus Home Assistant und bekommen nur eine `aiohttp`-Session; alle Fehler werden zu `ProviderError`.

Jeder Provider bekommt die vom Nutzer konfigurierten Beobachtungsbereiche und liefert normalisierte Events zurück. Netzwerk-/Parsing-Fehler werden pro Provider gefangen und dürfen nicht die anderen Provider blockieren.

### Coordinator-Design

- **Ein `DataUpdateCoordinator` pro (Provider × Beobachtungsbereich)** oder pro Provider mit internem Multiplexing über alle Bereiche – bei Implementierung abwägen (einfacher Start: ein Coordinator pro Provider, der alle konfigurierten Bereiche in einem Poll-Zyklus abfrägt).
- **Update-Intervall:** konfigurierbar, sinnvoller Default z. B. 10–15 Minuten (APIs sind nicht Echtzeit-kritisch, Baustellen ändern sich selten minütlich).
- **Fehlerbehandlung:** Schlägt ein Provider fehl (Netzwerkfehler, Parsing-Fehler, API-Änderung), soll das über Home Assistants **Repairs/Issue-Registry** sichtbar gemacht werden (`homeassistant.helpers.issue_registry`), nicht die gesamte Integration crashen. Andere Provider laufen unabhängig weiter.

### Config Flow (Konzept)

1. **Schritt 1 – Provider wählen:** Multi-Select (Autobahn-API / MobiData BW / Stuttgart), je nach Wohnort/Interessensgebiet des Nutzers relevant.
2. **Schritt 2 – Beobachtungsbereiche definieren:** pro Bereich:
   - Zone (Lat/Lon) + Radius (km), **oder**
   - konkrete Straße/Autobahn (z. B. "A8") + optional Fahrtrichtung
   - Name des Bereichs (z. B. "Arbeitsweg")
3. Mehrere Beobachtungsbereiche pro Config-Entry möglich (oder: ein Options-Flow zum Nachträglichen Hinzufügen).
4. Optionen (Options Flow): Update-Intervall pro Provider anpassbar.

### Entities (Beispiel pro Beobachtungsbereich "Arbeitsweg")

| Entity | Beispiel Entity-ID | Zweck |
|---|---|---|
| `calendar` | `calendar.streckenwacht_arbeitsweg` | Alle Ereignisse im Bereich als Kalendereinträge |
| `binary_sensor` | `binary_sensor.streckenwacht_arbeitsweg_stoerung_aktiv` | An, wenn mind. ein Ereignis aktuell aktiv ist |
| `sensor` | `sensor.streckenwacht_arbeitsweg_anzahl_ereignisse` | Anzahl aktueller Ereignisse, Details als Attribute |
| `event` | `event.streckenwacht_arbeitsweg_neues_ereignis` | Feuert bei neuem/beendetem Ereignis (für Automationen) |

---

## 5. Implementierungsreihenfolge

**Entscheidung:** Alle drei Provider werden **von Anfang an** gebaut (nicht stufenweise über mehrere Releases gestaffelt) – bewusste Abweichung von der ursprünglichen Empfehlung "erst nur Autobahn-API", da mehr Anfangsaufwand in Kauf genommen wird, um gleich das vollständige Bild zu haben.

**Empfohlene Reihenfolge innerhalb des einen Umsetzungsschritts** (auch wenn alle drei ins selbe erste Release gehen, hilft diese Coding-Reihenfolge, weil die Komplexität sehr unterschiedlich ist):

1. **Grundgerüst:** `manifest.json`, `const.py`, `model.py`, `coordinator.py`-Grundgerüst, Config Flow mit Provider-Mehrfachauswahl + Beobachtungsbereichen (Zone+Radius) von Anfang an.
2. **`providers/autobahn.py` zuerst** – einfachstes, bereits gut verstandenes Schema (`roadworks`, `closure`, `warning`), guter Rahmen zum Durchtesten der Gesamt-Pipeline (Coordinator → Entities).
3. **`providers/mobidata_bw.py` als zweites** – dank des verifizierten GeoJSON-Endpoints (`roadworks_geojson.json`, WGS84, siehe Abschnitt 2.2) fast so einfach wie Autobahn-API, keine Reprojektion nötig.
4. **`providers/stuttgart.py` als drittes/letztes** – Freitext-Datumsparsing für `ANFANG`/`ENDE` (GML-Parsing und Reprojektion entfallen, siehe 2b) – am besten angehen, wenn Grundgerüst und Datenmodell an den ersten beiden Providern schon bewiesen sind.
5. **Danach:** `calendar.py`, `binary_sensor.py`, `sensor.py`, `event.py` gegen alle drei Provider gemeinsam testen.
6. **Politur:** Repairs/Issue-Registry-Integration für Provider-Fehler (siehe Abschnitt 2, Risiko "Dev-Umgebung" unten), Übersetzungen (`strings.json`, `translations/de.json`), Tests (Abschnitt 7), HACS-Metadaten (`hacs.json`), README (inkl. Textbaustein in Abschnitt 13), Screenshots.

**Wichtiger Hinweis zur Testumgebung:** Die Entwicklung erfolgt auf einer **produktiven Home-Assistant-Instanz** (keine separate Dev-/Test-Instanz). Das erhöht das Risiko, dass ein Fehler im Custom Component das laufende Smart Home beeinträchtigt. Daher: **Provider-Logik (API-Calls + Parsing) zuerst als eigenständige Python-Skripte außerhalb von Home Assistant testen**, bevor der Custom Component überhaupt in die produktive Instanz geladen wird. Die im Architekturkonzept vorgesehene Fehlerisolation pro Provider (Repairs/Issue-Registry statt Crash der gesamten Integration, siehe Abschnitt 4) ist dadurch nicht optional, sondern eine harte Anforderung an v1.

**Konkreter Testfall für die Entwicklung:** Als Beobachtungsbereich für Tests wurde **A8/A81 im Raum Stuttgart** festgelegt (Autobahn-API + MobiData BW + Stuttgart-WFS decken diesen Bereich alle ab und eignen sich damit gut, um alle drei Provider gegeneinander zu testen).

---

## 6. Bekannte Risiken & offene technische Punkte

- **Webcams dauerhaft leer:** Sowohl Autobahn-API als auch MobiData BW liefern aktuell keine öffentlichen Webcam-Bilder (Sicherheitspolitik). Empfehlung: Feature komplett weglassen (nicht als eigene Entity bauen), um keine dauerhaft leere/tote Funktion zu shippen.
- **Lizenzunsicherheit INRIX-Daten:** Ein Teil der Autobahn-API-Warnmeldungen (Stau-Daten, `source: "inrix"`) stammt von einem kommerziellen Drittanbieter. Ob die Weiterverbreitung über eine HA-Integration lizenzrechtlich unproblematisch ist, ist **nicht geklärt** – vor öffentlicher Veröffentlichung prüfen (ggf. Autobahn GmbH kontaktieren).
- **INRIX – Recherche und Entscheidung (2026-10-02):** Weiterhin keine erklärten Nutzungsbedingungen (API, Impressum autobahn.de). bundesAPI-Issue #41 „What license does the data have?“ ist unbeantwortet („We don't care about licenses at bund.dev“). Die Warnungen werden offen genutzt, auch kommerziell (autobahn-baustellen.de verkauft ein Unfallprodukt auf dieser Basis). Einschätzung (keine Rechtsberatung): Streckenwacht verbreitet keine Daten weiter – jede HA-Instanz ruft den öffentlichen Endpunkt selbst ab; Risiko für Entwickler und private Nutzer sehr gering. Realistischster Fall: API-Änderung oder Bitte um Entfernung → dafür `upstream="inrix"` + **Option „Staumeldungen (INRIX) einbeziehen“, Standard an**, Namensnennung zusätzlich „Verkehrslage: INRIX“. Einzige echte Weitergabe wären Fixtures → **Warnungs-Fixtures sind aus der Git-Historie entfernt und per `.gitignore` nur lokal**; Tests nutzen ein eingebettetes Beispiel. Kurze Anfrage bei der Autobahn GmbH vor dem öffentlichen Bewerben bleibt sinnvoll.
- **Keine explizite Lizenz der Autobahn-API selbst** gefunden (im Gegensatz zu Stuttgart/MobiData BW, die klare Lizenzangaben haben).
- **Stuttgart-WFS-Eigenheiten:** ~~UTM-Koordinaten müssen reprojiziert werden~~ (entfällt, GeoJSON/WGS84 per `srsName`); Datumsfelder sind Freitext und nicht garantiert einheitlich formatiert – robustes Parsing mit Fallback nötig.
- **Deduplizierung zwischen Quellen:** Dieselbe Baustelle kann theoretisch sowohl in der Autobahn-API als auch bei MobiData BW auftauchen. Für v1 bewusst **nicht** lösen (getrennt anzeigen), später als Verbesserung.
  - **Messung (2026-10-02, Bereich 10 km um Stuttgart-Kaltental, A81 + MobiData + Stuttgart, 71 aktive Meldungen):** 64 quellenübergreifende Paare liegen ≤ 300 m auseinander – fast alle sind aber *verschiedene* Straßen am selben Ort (A81-Ausbau bei Sindelfingen kreuzt Leibnizstraße, K1055, L1185 mit je eigener Baustelle). Stuttgart ↔ MobiData: kein einziges nahes Paar. Eine Zusammenführung nur nach Nähe würde echte Meldungen verstecken. Ein späteres Verfahren muss **dieselbe Straße** verlangen (z. B. MobiData `road="A5"` ↔ Autobahn `road="A5"`); betrifft nur die wenigen A-Abschnitte in MobiData. Die vielen ähnlichen A81-Einträge sind keine Duplikate zwischen Quellen, sondern die Autobahn-API meldet je Abschnitt und Richtung getrennt.
- **API-Stabilität:** Keine der drei APIs ist offiziell versioniert/stabil dokumentiert im Sinne einer SLA – defensive Fehlerbehandlung und Schema-Validierung beim Parsen einbauen (nicht blind auf Feldnamen vertrauen).
- **Rate Limits unbekannt:** Polling-Intervalle konservativ wählen und ggf. konfigurierbar machen.

---

## 7. Home-Assistant-/HACS-Standards, die beachtet werden sollten

- **Manifest:** `manifest.json` mit `domain`, `name`, `codeowners`, `config_flow: true`, `iot_class` (vermutlich `cloud_polling`), `requirements` (nach Verifikation voraussichtlich **leer** – `pyproj` wird nicht gebraucht, siehe 2.3), `version`.
- **Config Entries:** Kein YAML-Setup, ausschließlich UI-Config-Flow (moderner HA-Standard).
- **`DataUpdateCoordinator`-Pattern** statt eigener Polling-Logik pro Entity.
- **Unique IDs** für Config-Entries und Entities (Stabilität über Neustarts/Umbenennungen hinweg).
- **Async durchgängig** (`aiohttp` über die von HA bereitgestellte Session, `async_get_clientsession(hass)`).
- **Übersetzungen** (`strings.json` + `translations/*.json`) für Config-Flow-Texte.
- **Tests:** `pytest-homeassistant-custom-component` für Config-Flow- und Coordinator-Tests. **Wie die Provider-Tests genau gegen API-Daten laufen sollen (aufgezeichnete Fixtures vs. Live-Calls), ist bewusst offengelassen** – Empfehlung: aufgezeichnete Beispiel-Responses (Snapshots) verwenden, damit Tests offline, schnell und reproduzierbar laufen und nicht von der Verfügbarkeit der drei kostenlosen öffentlichen APIs abhängen; die implementierende KI kann das aber selbst final entscheiden.
- **HACS-Anforderungen:** `hacs.json` (Entwurf liegt bei: `name`, `country: "DE"`, `homeassistant: "2026.3.0"`), GitHub-Repo-Beschreibung und Topics (z. B. `home-assistant`, `hacs`, `hacs-integration`, `homeassistant-integration`, `autobahn`, `traffic`, `germany`), README mit Nutzungsinfos, GitHub-Releases (der Tag des neuesten Release ist die Version, die HACS anzeigt – SemVer verwenden).
- **Brand-Icons – geänderte Rechtslage seit Februar 2026 (wichtig!):** Das zentrale Repo `home-assistant/brands` nimmt **keine Custom-Integrationen mehr an**. Stattdessen liefert die Integration ihre Bilder selbst aus, im Ordner **`custom_components/streckenwacht/brand/`** (`icon.png`, `icon@2x.png`, `logo.png`, `logo@2x.png` + `dark_`-Varianten). Funktioniert ab **Home Assistant 2026.3**; lokale Bilder haben Vorrang vor dem CDN ([Ankündigung](https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api/), [Doku](https://developers.home-assistant.io/docs/core/integration/brand_images/)). Die acht Dateien liegen im Paket bereits genau dort. Bekannte Einschränkung: Das **HACS-Dashboard** zeigt lokale Brand-Icons evtl. noch nicht an (offenes [HACS-Issue #5171](https://github.com/hacs/integration/issues/5171), Fix-PRs in Arbeit) – in den HA-Einstellungen/Integrationsliste erscheinen sie trotzdem. Deshalb `homeassistant: "2026.3.0"` in `hacs.json`.
- **Quality Scale:** Orientierung an Home Assistants „Integration Quality Scale" (Bronze/Silver-Niveau als realistisches erstes Ziel) – u. a. sauberes Error-Handling, Config-Flow mit Validierung, keine blockierenden I/O-Calls im Event-Loop.

---

## 8a. Projektlizenz (entschieden: MIT)

Für den Code des Projekts (nicht zu verwechseln mit den Datenlizenzen der drei Quellen, siehe Abschnitt 8) wurde **MIT** gewählt.

**Abwägung MIT vs. Apache-2.0:**

| | MIT | Apache-2.0 |
|---|---|---|
| Umfang | kurz, ein Absatz | deutlich länger, detaillierter |
| Pflicht für Nutzer | Copyright-Hinweis + Lizenztext beibehalten | zusätzlich: geänderte Dateien als geändert kennzeichnen (NOTICE-Mechanismus) |
| Patentschutz | keiner | explizite Patent-Lizenz + Patent-Retaliation-Klausel |
| Pflegeaufwand | minimal | etwas höher |

**Begründung für MIT:**
- Kein reales Patentrisiko bei einer Integration, die öffentliche Verkehrsdaten anzeigt – der Apache-2.0-Patentschutz bringt hier keinen praktischen Mehrwert.
- Kürzer, verständlicher, kein NOTICE-File-Pflegeaufwand bei jeder Änderung.
- Entspricht der Konvention im direkten Umfeld: HACS selbst ([hacs/integration](https://github.com/hacs/integration)) ist MIT-lizenziert, obwohl Home Assistant Core (Apache-2.0) darunterliegt. MIT ist der De-facto-Standard für kleinere Custom-Integrationen im HACS-Ökosystem.
- HACS selbst schreibt keine bestimmte Lizenz vor ([hacs.xyz/docs/publish/integration](https://www.hacs.xyz/docs/publish/integration/)) – die Wahl war frei, MIT ist aber das naheliegende Standardfeld im GitHub-Lizenz-Picker für ein Projekt dieser Art.

**Praktisch:** `LICENSE`-Datei mit Standard-MIT-Text im Repo-Root, Copyright-Zeile mit Name/Handle + Jahr. Ohne jede Lizenzangabe gilt sonst automatisch „All rights reserved" – ein öffentliches Repo ohne Lizenzdatei dürfte von niemandem geforkt, verändert oder weiterverwendet werden.

## 8. Rechtliche Hinweise (keine Rechtsberatung, nur Einordnung)

- **Impressumspflicht (§ 5 DDG, ehem. § 5 TMG):** gilt für „geschäftsmäßige" digitale Dienste; Gerichte legen das breit aus. Ein rein privates Hobbyprojekt ohne Monetarisierung fällt in der Regel nicht darunter, die Grenze ist aber nicht immer trennscharf.
  - **Empfehlung:** keine Spenden-Links, keine Werbung/externe monetarisierte Website – das hält das Projekt näher an der privaten Hobby-Ausnahme.
  - Bei echtem Zweifel: kurze anwaltliche Einschätzung einholen.
- **Attribution/Namensnennung ist erforderlich** für alle drei Datenquellen, unabhängig von der Impressumsfrage:
  - Stadt Stuttgart: CC BY 4.0 → Namensnennung „Stadt Stuttgart" im README/UI.
  - MobiData BW: „Datenlizenz Deutschland – Namensnennung 2.0" → Namensnennung entsprechend der Lizenzvorgaben.
  - Autobahn GmbH: keine explizite Lizenz gefunden, Attribution trotzdem als Best Practice einbauen.
- **INRIX-Daten (via Autobahn-API):** siehe Risiken oben – vor Veröffentlichung Lizenzlage klären.

---

## 9. Promotion-Plan (nachgelagert, aber für Kontext relevant)

1. **Eigenes GitHub-Repo** – **Entscheidung revidiert:** statt persönlichem Account nun eine **projektspezifische GitHub-Organisation `streckenwacht`** mit Repo-Name **`integration`** (folgt der Namenskonvention von HACS selbst, [hacs/integration](https://github.com/hacs/integration)) → `github.com/streckenwacht/integration`. Beide Namen wurden live geprüft und sind frei (GitHub-Org sowie `streckenwacht.de/.com/.io`). Kein rechtlicher/technischer Nachteil gegenüber einem persönlichen Account – Präzedenzfälle im HACS-Umfeld: [custom-components](https://github.com/orgs/custom-components/repositories) (Sammel-Org vieler Maintainer), [ha-warmup](https://github.com/ha-warmup/hacs-warmup) (projektspezifische Org). Einziger Hinweis: `codeowners` in `manifest.json` bleibt der persönliche GitHub-Handle, ändert sich durch die Org nicht. Repo direkt als Custom Repository in HACS nutzbar (kein Freigabeprozess nötig).
2. **Ankündigen** (Links live verifiziert, Stand dieses Dokuments) – gezielt um Feedback zur Nützlichkeit bitten:
   - International: [HA Community Forum – „Share your Projects!"](https://community.home-assistant.io/c/projects/9) (bzw. Unterkategorie [Custom Integrations](https://community.home-assistant.io/c/projects/custom-integrations/47)), r/homeassistant (vorher Sub-Regeln zu Eigenwerbung prüfen), [Awesome Home Assistant](https://www.awesome-ha.com/) (PR für dauerhafte Listung).
   - Deutschsprachig, inhaltlich passender: [simon42 Community](https://community.simon42.com/), [Community Smart Home](https://community-smarthome.com/), [Smart Home Community](https://smart-home-community.de/board/55-home-assistant/), [heimnetz.de](https://forum.heimnetz.de/forums/home-assistant.27/).
   - Gezielt/klein aber passend: GitHub-Discussions von [`bundesAPI/autobahn-api`](https://github.com/bundesAPI/autobahn-api); MobiData BW direkt informieren (`mobidata-bw@nvbw.de`).
3. **Später**, bei ausreichend Nutzern/Reife: Aufnahme in die offizielle HACS-Default-Liste beantragen (Review-Prozess von `hacs/default`).

## 9a. Konkrete Schritte: GitHub-Organisation & Repo anlegen

Diese Schritte führt der Nutzer (oder die implementierende KI/der Entwickler gemeinsam mit ihm) manuell auf github.com aus, bevor der Code das erste Mal gepusht wird:

1. **Organisation anlegen:** Auf github.com oben rechts auf das „+"-Icon → „New organization". Plan „Free" wählen (für öffentliche Open-Source-Repos kostenlos, unbegrenzte Mitglieder). Als Organisationsname **`streckenwacht`** eintragen (live geprüft, Stand dieses Dokuments: frei).
2. **Kontaktdaten/Einordnung:** GitHub fragt nach E-Mail und ob die Organisation für ein Unternehmen oder privat genutzt wird – hier die unverbindlichste/persönliche Option wählen; das ist nur eine GitHub-interne Einordnung ohne rechtliche Bindungswirkung.
3. **Repository innerhalb der Organisation erstellen:** „New repository" → als Owner die Organisation `streckenwacht` auswählen (nicht den persönlichen Account) → Name **`integration`** → Sichtbarkeit **Public** → **leer anlegen**: kein README, keine `.gitignore`, keine Lizenz ankreuzen – all das liegt schon im Übergabe-Paket (inkl. MIT-`LICENSE`), und ein vorbefülltes Repo führt beim ersten Push zu einem Konflikt. Beschreibung eintragen, z. B. „Baustellen, Sperrungen, Staus und Unfälle auf deiner Strecke – Home-Assistant-Integration (Autobahn, MobiData BW, Stuttgart)".
4. **Paket einspielen:** Den Inhalt des Ordners `streckenwacht-integration/` aus dem ZIP in einen lokalen Ordner legen, dort `git init`, `git remote add origin https://github.com/streckenwacht/integration.git`, committen, pushen. Danach baut die implementierende KI die Struktur aus Abschnitt 4 auf (`custom_components/streckenwacht/…`). Der Ordnername bleibt `streckenwacht` (das ist die Home-Assistant-Domain), auch wenn das Repo selbst `integration` heißt.
   - Unter *Settings → General → Social preview* das Bild `assets/github/social-preview-1280x640.png` hochladen; als Org-Avatar `assets/github/org-avatar-500.png` (bzw. `-1024`).
5. **`manifest.json`/`hacs.json` auf die neue URL ausrichten:** Felder `documentation` und `issue_tracker` auf `https://github.com/streckenwacht/integration` setzen. `codeowners` bleibt der persönliche GitHub-Handle des Nutzers (z. B. `["@dein-username"]`) – ändert sich durch die Organisation nicht, der Nutzer ist als Org-Owner weiterhin voll zugriffsberechtigt.
6. **Optional – Org-Profilseite:** Ein zusätzliches Repo namens exakt `streckenwacht` mit einer `README.md` anlegen – GitHub zeigt deren Inhalt automatisch als Beschreibung auf der Organisations-Startseite an. Für den Start nicht notwendig, nur sinnvoll, falls später weitere Repos in die Org kommen.

---

## 10. Offene Entscheidungen – Status

Alle ursprünglich offenen Punkte wurden durchgesprochen und entschieden (Stand: siehe unten), bis auf einen bewusst offengelassenen Punkt.

**Entschieden:**
- ~~Geografischer/technischer Scope für v1~~ → **alle drei Provider von Anfang an** (Abschnitt 5).
- ~~GitHub-Organisation/Repo-Name~~ → **Organisation `streckenwacht`, Repo `integration`** (`github.com/streckenwacht/integration`, revidiert von ursprünglich persönlichem Account – Abschnitt 9).
- ~~Exakte MobiData-BW-API-Struktur~~ → **verifiziert: GeoJSON-Endpoint, WGS84, siehe Abschnitt 2.2.**
- ~~Lizenz des Projekt-Codes~~ → **MIT** (Abschnitt 8a).
- ~~Entwicklungsumgebung~~ → **produktive HA-Instanz** (kein separates Dev-Setup) – siehe Sicherheitshinweis in Abschnitt 5.
- ~~Testfall/Beobachtungsbereich für die Entwicklung~~ → **A8/A81 im Raum Stuttgart** (Abschnitt 5).
- ~~Umgang mit INRIX-Lizenzfrage~~ → als Risiko markiert lassen, **vor dem öffentlichen Release** aktiv bei der Autobahn GmbH klären (Abschnitt 6/8).
- ~~Umgang mit Impressumspflicht-Frage~~ → zurückgestellt, **vor dem öffentlichen Release** aktiv prüfen, bis dahin keine Spenden-Links/Werbung einbauen (Abschnitt 8).
- ~~README-Erwartungsmanagement~~ → fertiger Textbaustein in Abschnitt 13.

**Entschieden beim Onboarding (2026-10-02):**
- **Struktur:** **ein** Config-Entry „Streckenwacht" (gewählte Quellen, Intervall) + **Config-Subentries** je Beobachtungsbereich. Daraus folgt: **ein Coordinator pro Provider** (lädt einmal pro Poll alles, was die Bereiche brauchen – MobiData eine Datei, Autobahn die Vereinigungsmenge der gewählten Autobahnen, Stuttgart zwei Layer); die Bereiche filtern lokal.
- **Tests:** Fixtures statt Live-Calls. Reine Provider-/Parsing-Tests laufen lokal unter Windows mit `uv`; HA-Tests (`pytest-homeassistant-custom-component`) laufen in **GitHub Actions** (Linux), weil die HA-Testbibliothek unter Windows nicht läuft (kein WSL/Docker auf dem Entwicklungsrechner).
- **Deployment auf die produktive Instanz:** HA OS, Installation **über HACS aus dem GitHub-Repo** (wie bei späteren Nutzern). Konsequenz: Bevor die Integration erstmals in HA geladen wird, müssen GitHub-Org und Repo existieren und der Code gepusht sein; Provider-Logik vorher vollständig lokal testen.
- **Bereiche (nach Beta-Test, 2026-10-02):** Quellenauswahl **pro Bereich** (z. B. nur Autobahn für den Arbeitsweg) und optionaler Schritt **Fahrtrichtungen** (Auswahl aus den real vorkommenden „Start -> Ziel“-Richtungen der gewählten Autobahnen; Anschlussstellen und Meldungen ohne Richtung bleiben immer sichtbar). Sensor „Ereignisse“ hat das Attribut `by_source`.
- **Git:** lokal initialisiert; GitHub-Org `streckenwacht` legt der Projektinhaber an, sobald der erste HA-Test ansteht. `codeowners`: `@n42net`.

---

## 11. Nützliche Links (zum Nachschlagen bei Implementierung)

- Autobahn-API: `https://verkehr.autobahn.de/o/autobahn` (Basis-URL, Endpoints wie oben beschrieben)
- MobiData BW Portal: `https://www.mobidata-bw.de`
- OpenData Stuttgart: `https://opendata.stuttgart.de`
- Stuttgart GeoServer (WFS): `https://geoserver.stuttgart.de`
- HACS-Dokumentation: `https://hacs.xyz`
- Home Assistant Developer Docs (Integrationen): `https://developers.home-assistant.io`
- Home Assistant Integration Quality Scale: `https://developers.home-assistant.io/docs/core/integration-quality-scale/`
- Brand-Bilder für Custom-Integrationen (ab HA 2026.3): `https://developers.home-assistant.io/docs/core/integration/brand_images/`
- HACS – Anforderungen an Repos und `hacs.json`: `https://www.hacs.xyz/docs/publish/start/`
- Design-Canvas (Icon-Konzept, nur mit Freigabe durch den Projektinhaber einsehbar): `https://claude.ai/artifact/VbLtuZGvQcFd54MccfXHXb`

---

## 12. Ausgangslage für die KI, die dieses Dokument erhält

- Es existiert **noch kein Integrationscode** – dieses Dokument ist der Ausgangspunkt. Bereits vorhanden sind: `README.md`-Entwurf, `LICENSE` (MIT), `hacs.json`, `.gitignore`, `CLAUDE.md`, die Brand-Bilder in `custom_components/streckenwacht/brand/`, weitere Bilder in `assets/`, und `tools/fetch_fixtures.py`.
- Alle oben genannten API-Strukturen stammen aus Live-Recherche zum Zeitpunkt der Konzeption (September 2026) – **vor der Implementierung erneut gegen die Live-APIs validieren**, da sich Endpoints/Felder geändert haben können.
- **Erster Schritt: `uv run --python 3.13 --no-project tools/fetch_fixtures.py` ausführen** (erledigt am 2026-10-02, Befunde in Abschnitt 2b). Das Skript lädt echte Antworten aller drei Quellen nach `tests/fixtures/` (Autobahn A8/A81, MobiData-BW-GeoJSON, Stuttgart als GeoJSON). Diese Dateien sind die verbindliche Wahrheit für Feldnamen und Formate – nicht die Beschreibungen in diesem Dokument.
- Empfehlung an die implementierende KI: der Reihenfolge in Abschnitt 5 folgen (Grundgerüst → Autobahn-API → MobiData BW → Stuttgart-WFS → gemeinsame Entities), auch wenn alle drei Provider ins selbe erste Release gehen – so lässt sich die Pipeline früh an den einfacheren Providern durchtesten, bevor die komplexeste Quelle (Stuttgart) drankommt. Provider-Logik zuerst standalone testen (siehe Sicherheitshinweis Abschnitt 5), da auf einer produktiven HA-Instanz entwickelt wird.

## 13. README-Textbaustein: Erwartungsmanagement (einsatzbereit)

Der folgende Absatz sollte, leicht angepasst, in die README aufgenommen werden – er macht früh transparent, was die Integration **nicht** leisten kann, damit Nutzer nicht enttäuscht werden, wenn eine bestimmte Baustelle fehlt:

> **Was Streckenwacht nicht kann**
>
> Streckenwacht zeigt Baustellen, Sperrungen, Staus und Unfälle auf Basis dreier offizieller, kostenloser Datenquellen (Autobahn GmbH, MobiData BW, Stadt Stuttgart). Diese Quellen sind nicht vollständig:
> - Die Autobahn-API deckt nur Bundesautobahnen ab, nicht Landes-/Kreis- oder Kommunalstraßen.
> - MobiData BW deckt Bundes-, Landes- und Kreisstraßen in Baden-Württemberg ab, kommunale Straßen nur vereinzelt.
> - Der Stuttgart-Baustellenkalender deckt nur das „Vorbehaltsstraßennetz" (Hauptverkehrsachsen und Hauptradrouten) ab – Wohnstraßen, Notreparaturen und nicht-verkehrsrelevante Arbeiten von Versorgern fehlen bewusst.
> - Keine der drei Quellen garantiert Vollständigkeit oder eine feste Aktualisierungsfrequenz; alle Angaben stammen ungefiltert von den jeweiligen Behörden/Betreibern.
>
> Kurz: Streckenwacht eignet sich gut, um größere Störungen auf Hauptstrecken (Autobahnen, Bundesstraßen, Hauptachsen) im Blick zu behalten – nicht, um jede kleine Baustelle in jeder Nebenstraße zu erfassen.

**Zusätzlich für die README: Beispiel-Automationen.** Macht den Nutzen für potenzielle Nutzer viel greifbarer als eine reine Feature-Liste – z. B. als eigener README-Abschnitt "Was du damit bauen kannst":

- **Push-Benachrichtigung bei Reisezeitverlust:** Automation, die auslöst, wenn `sensor.streckenwacht_<bereich>_anzahl_ereignisse` (oder ein zukünftiges dediziertes Delay-Attribut) einen Reisezeitverlust über einem Schwellwert (z. B. 15 Minuten) auf der Pendelstrecke meldet.
- **Sprachansage beim Verlassen des Hauses:** Kombination mit einer `person`-Entity/Zone – beim Verlassen des Hauses eine Ansage über einen Smart Speaker, falls seit dem letzten Mal ein neues Ereignis (`event.streckenwacht_<bereich>_neues_ereignis`) auf der Pendelstrecke aufgetaucht ist.
- **Kalender-Widget auf dem Dashboard:** Der `calendar`-Entity direkt als Lovelace-Kalenderkarte einbinden, um kommende/aktive Baustellen auf einen Blick zu sehen.

## 14. Ideen-Backlog für spätere Versionen (nicht Teil von v1)

Diese Ideen kamen im Planungsgespräch auf, sind aber bewusst kein Bestandteil des ersten Umsetzungsschritts – hier festgehalten, damit sie nicht verloren gehen:

- **Lovelace-Kartenansicht:** Eine custom Lovelace-Karte, die die ohnehin im Datenmodell vorhandene Geometrie (`geometry`-Feld, GeoJSON LineStrings aus Autobahn-API und MobiData BW) visuell auf einer Karte darstellt – zeigt Baustellen/Sperrungen/Staus räumlich statt nur als Liste/Kalender. Die Rohdaten dafür fallen in v1 ohnehin schon an, es fehlt nur die Visualisierungsschicht.
- **Deduplizierung zwischen Quellen** (bereits in Abschnitt 6 als Risiko erwähnt): eine spätere Heuristik (räumliche Nähe + zeitliche Überlappung + Titel-Ähnlichkeit), um doppelte Meldungen zwischen Autobahn-API und MobiData BW zusammenzuführen.
- **Strecke statt Kreis:** Korridor entlang einer Route (Liste von Wegpunkten oder eine HA-Zone-Kette) statt eines Kreises – genauer für Pendelstrecken. Aus dem Beta-Test (2026-10-02).
- **Autobahn-Abschnitte:** Filter „A81 zwischen AS X und AS Y“. Die Abschnittsnamen sind Freitext in `title`/`description` – aufwendig und fehleranfällig, daher zurückgestellt zugunsten der Fahrtrichtungen.
- **Deduplizierung nur bei gleicher Straße:** siehe Messung in Abschnitt 6; reine Nähe-Heuristik würde echte Meldungen verstecken.
- **Langzeitstatistik:** z. B. "durchschnittlicher Reisezeitverlust pro Monat" oder "Anzahl Ereignisse pro Beobachtungsbereich über Zeit" als Statistics-Sensor, nutzbar für Home-Assistant-Graphen/History.
