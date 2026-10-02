<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/streckenwacht/integration/main/assets/github/readme-header-dark@2x.png">
  <img alt="Streckenwacht – wacht über deine Strecke." src="https://raw.githubusercontent.com/streckenwacht/integration/main/assets/github/readme-header-light@2x.png" width="640">
</picture>

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-005B8C.svg)](https://hacs.xyz/)
[![Release](https://img.shields.io/github/v/release/streckenwacht/integration?include_prereleases&color=005B8C)](https://github.com/streckenwacht/integration/releases)
[![CI](https://github.com/streckenwacht/integration/actions/workflows/ci.yml/badge.svg)](https://github.com/streckenwacht/integration/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-F5A623.svg)](LICENSE)

> ⚠️ **Testphase.** Es gibt bisher nur Vorabversionen (Beta). Rückmeldungen sind willkommen – siehe [Fehler melden](#fehler-melden).

Streckenwacht wacht über deine Strecke – ob Autobahn, Bundesstraße oder dein täglicher Arbeitsweg. Baustellen, Sperrungen, Staus und Unfälle, direkt in deinem Home Assistant: als Kalender, Sensoren und Events für Automationen.

*In English:* Streckenwacht is a Home Assistant integration for roads in Germany. It shows roadworks, closures, traffic jams and accidents within areas you define, using open data from Autobahn GmbH (motorways, nationwide), MobiData BW (Baden-Württemberg) and the City of Stuttgart. The UI is available in German and English.

## Was Streckenwacht kann

- **Beobachtungsbereiche** frei festlegen: Kreis auf der Karte, z. B. „Zuhause“ oder „Arbeitsweg“.
- Pro Bereich wählbar: **Datenquellen**, **Autobahnen** und **Fahrtrichtungen** – etwa nur die A81 Richtung Stuttgart.
- Pro Bereich ein **Kalender** mit allen Baustellen und Sperrungen; Nachtbaustellen erscheinen als einzelne Termine pro Nacht.
- **„Störung aktiv“**, sobald im Bereich eine Sperrung, ein Unfall oder ein Stau aktiv ist – normale Dauerbaustellen lösen ihn bewusst nicht aus.
- **Reisezeitverlust** in Minuten (größter aktueller Wert im Bereich).
- **Event bei neuen und beendeten Meldungen** – ideal für Push-Nachrichten.
- Fällt eine Quelle aus, laufen die anderen weiter; nach wiederholten Fehlern erscheint ein Hinweis unter *Reparaturen*.

## Datenquellen

| Quelle | Abdeckung | Lizenz / Namensnennung |
|---|---|---|
| [Autobahn GmbH – Autobahn-API](https://verkehr.autobahn.de/o/autobahn) | Bundesautobahnen, bundesweit: Baustellen, Sperrungen, Warnungen inkl. Staus | Die Autobahn GmbH des Bundes |
| ↳ Staumeldungen darin | Verkehrslage aus Fahrzeugdaten | Verkehrslage: INRIX (abschaltbar, siehe [Optionen](#optionen)) |
| [MobiData BW](https://mobidata-bw.de/dataset/baustelleninformationen-baden-wurttemberg) | Bundes-, Landes- und Kreisstraßen in Baden-Württemberg, vereinzelt Gemeindestraßen | Datenlizenz Deutschland – Namensnennung 2.0 |
| [Stadt Stuttgart – Baustellenkalender](https://www.stuttgart.de/baustellenkalender) | Hauptverkehrsstraßen (Vorbehaltsstraßennetz) in Stuttgart | CC BY 4.0, © Landeshauptstadt Stuttgart |

Alle Entitäten tragen die jeweilige Namensnennung im Attribut `attribution`.

## Was Streckenwacht nicht kann

Die Quellen sind nicht vollständig:

- Die Autobahn-API deckt nur Bundesautobahnen ab, nicht Landes-, Kreis- oder Kommunalstraßen.
- MobiData BW deckt Bundes-, Landes- und Kreisstraßen in Baden-Württemberg ab, kommunale Straßen nur vereinzelt.
- Der Stuttgarter Baustellenkalender deckt nur das „Vorbehaltsstraßennetz“ ab – Wohnstraßen, Notreparaturen und nicht verkehrsrelevante Arbeiten von Versorgern fehlen bewusst.
- Außerhalb von Baden-Württemberg stehen nur die Autobahnen zur Verfügung.
- Unfälle haben in keiner Quelle eine eigene Kategorie; Streckenwacht erkennt sie am Wort „Unfall“ in Autobahn-Warnungen.
- Keine der Quellen garantiert Vollständigkeit oder eine feste Aktualisierungsfrequenz; alle Angaben stammen ungefiltert von den jeweiligen Behörden und Betreibern.

Kurz: Streckenwacht eignet sich gut, um größere Störungen auf Hauptstrecken im Blick zu behalten – nicht, um jede kleine Baustelle in jeder Nebenstraße zu erfassen.

## Datenschutz

Dein Standort verlässt Home Assistant nicht. Streckenwacht lädt die Meldungen ganzer Autobahnen bzw. die landesweite MobiData-Datei und die Stuttgarter Liste herunter und filtert erst lokal auf deine Bereiche. Die Abrufe enthalten keine Koordinaten und keine persönlichen Daten, nur eine Kennung der Integration (User-Agent). Unveränderte Daten werden dank ETag nicht erneut übertragen.

## Installation (HACS, benutzerdefiniertes Repository)

Voraussetzung: Home Assistant **2026.3** oder neuer und [HACS](https://hacs.xyz/).

**Mit einem Klick:** [![In HACS öffnen](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=streckenwacht&repository=integration&category=integration) → herunterladen, Home Assistant neu starten → [![Integration hinzufügen](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=streckenwacht)

Oder von Hand:

1. HACS öffnen → Menü (⋮) → **Benutzerdefinierte Repositories**.
2. URL `https://github.com/streckenwacht/integration` eintragen, Typ **Integration**, hinzufügen.
3. **Streckenwacht** in HACS öffnen → **Herunterladen**. Solange es nur Testversionen gibt, im Dialog die neueste Version wählen (ggf. Beta-Versionen anzeigen lassen).
4. Home Assistant neu starten.
5. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Streckenwacht**.

Hinweis: Im HACS-Dashboard fehlt das Icon derzeit ([HACS-Issue #5171](https://github.com/hacs/integration/issues/5171)); in den Home-Assistant-Einstellungen wird es angezeigt.

## Einrichtung

### Datenquellen und Optionen

Beim Hinzufügen wählst du die Datenquellen. Liegt dein Home-Assistant-Standort in Baden-Württemberg, sind alle drei vorausgewählt, sonst nur die Autobahn.

<a id="optionen"></a>Später änderbar über **Geräte & Dienste → Streckenwacht → Konfigurieren**:

| Option | Standard | Bedeutung |
|---|---|---|
| Datenquellen | je nach Standort | Welche Quellen überhaupt abgefragt werden |
| Abrufintervall | 15 min | 10–60 Minuten |
| Staumeldungen einbeziehen (INRIX) | an | Staus und Reisezeitverlust aus der Autobahn-API |

### Beobachtungsbereiche

Auf der Streckenwacht-Seite **Beobachtungsbereich hinzufügen**. Der Dialog führt in bis zu drei Schritten durch die Einrichtung:

1. **Bereich** – Name (wird Teil der Entity-IDs, z. B. „Arbeitsweg“), Kreis auf der Karte (max. 100 km) und die **Datenquellen** für diesen Bereich, z. B. nur Autobahn für den Arbeitsweg.
2. **Autobahnen** – nur wenn „Autobahn GmbH“ gewählt ist. Angezeigt werden nur ihre Meldungen innerhalb des Kreises. Die Auswahl ist nötig, weil die Autobahn-API immer eine ganze Autobahn liefert und keine Umkreissuche kennt.
3. **Fahrtrichtungen** – zur Auswahl stehen die Richtungen, die auf den gewählten Autobahnen aktuell vorkommen. Leer lassen für alle Richtungen. Meldungen an Anschlussstellen und ohne Richtung werden immer angezeigt.

> **Tipp für Arbeitswege über ein Autobahnkreuz:** Die Richtungsangabe wechselt am Kreuz. Wer z. B. auf der A81 von Böblingen nach Stuttgart-Feuerbach fährt, braucht „Singen -> Stuttgart“ **und** „Stuttgart -> Heilbronn“.

Bereiche lassen sich jederzeit über ⋮ → **Neu konfigurieren** ändern.

## Entitäten pro Beobachtungsbereich

Beispiel für den Bereich „Arbeitsweg“ (Gerät *Streckenwacht Arbeitsweg*). Die Entity-IDs sind englisch, die angezeigten Namen folgen der Sprache von Home Assistant.

| Entität | Anzeigename | Inhalt |
|---|---|---|
| `calendar.streckenwacht_arbeitsweg` | Streckenwacht Arbeitsweg | Alle Meldungen als Termine |
| `binary_sensor.streckenwacht_arbeitsweg_disruption_active` | Störung aktiv | An bei aktiver Sperrung, Unfall oder Stau. Attribute: `count`, `disruptions` |
| `sensor.streckenwacht_arbeitsweg_events` | Ereignisse | Anzahl aktiver Meldungen. Attribute: Anzahl je Typ, `by_source`, `events` (bis zu 20, schwerste zuerst) |
| `sensor.streckenwacht_arbeitsweg_travel_time_loss` | Reisezeitverlust | Größter aktueller Reisezeitverlust in Minuten (nur mit Staumeldungen) |
| `event.streckenwacht_arbeitsweg_event_change` | Ereignisänderung | Event-Typ `new` oder `ended` |

**Typen** (`type`): `roadworks` (Baustelle), `closure` (Sperrung), `traffic_jam` (Stau), `accident` (Unfall), `warning` (sonstige Warnung).

Alle Entitäten haben das Attribut `unavailable_sources`: Ist eine Quelle gerade nicht erreichbar, steht sie dort – die angezeigten Daten sind dann der letzte bekannte Stand.

Ein `new`-Event enthält `id`, `title`, `type`, `source`, `road`, `direction`, `start`, `end`, `delay_minutes`, `latitude`, `longitude`; ein `ended`-Event `id`, `title`, `type` und `source`. Nach einem Neustart oder einer Bereichsänderung werden bekannte Meldungen nicht erneut als neu gemeldet.

## Was du damit bauen kannst

### Fertige Blueprints

Ohne YAML: Blueprint importieren, Bereich und Handy auswählen, fertig.

| Blueprint | Was sie tut | |
|---|---|---|
| **Stau-Benachrichtigung** | Push-Nachricht, sobald der Reisezeitverlust einen Schwellwert überschreitet; optional nur in einem Zeitfenster | [![Blueprint importieren](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fstreckenwacht%2Fintegration%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fstreckenwacht%2Fstau_benachrichtigung.yaml) |
| **Neue oder beendete Meldung** | Push-Nachricht bei neuen Meldungen der gewählten Arten (z. B. Sperrung, Unfall), auf Wunsch auch bei deren Ende | [![Blueprint importieren](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fstreckenwacht%2Fintegration%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fstreckenwacht%2Fneue_meldung.yaml) |

Die Benachrichtigungen gehen an ein Handy mit der offiziellen Home-Assistant-App. Wer es anders braucht, findet unten die Beispiele als YAML zum Anpassen.

### Push-Nachricht bei Reisezeitverlust

```yaml
alias: Stau auf dem Arbeitsweg
triggers:
  - trigger: numeric_state
    entity_id: sensor.streckenwacht_arbeitsweg_travel_time_loss
    above: 15
actions:
  - action: notify.mobile_app_mein_telefon
    data:
      title: "Stau auf dem Arbeitsweg"
      message: >-
        +{{ states('sensor.streckenwacht_arbeitsweg_travel_time_loss') }} min:
        {{ state_attr('sensor.streckenwacht_arbeitsweg_travel_time_loss', 'title') }}
```

### Benachrichtigung bei neuer Sperrung oder neuem Unfall

```yaml
alias: Neue Sperrung auf dem Arbeitsweg
triggers:
  - trigger: state
    entity_id: event.streckenwacht_arbeitsweg_event_change
conditions:
  - condition: template
    value_template: >-
      {{ trigger.to_state.attributes.event_type == 'new'
         and trigger.to_state.attributes.type in ['closure', 'accident'] }}
actions:
  - action: notify.mobile_app_mein_telefon
    data:
      title: "Neu auf dem Arbeitsweg"
      message: "{{ trigger.to_state.attributes.title }}"
```

### Ansage beim Verlassen des Hauses

```yaml
alias: Störung auf dem Arbeitsweg ansagen
triggers:
  - trigger: state
    entity_id: person.ich
    from: home
conditions:
  - condition: state
    entity_id: binary_sensor.streckenwacht_arbeitsweg_disruption_active
    state: "on"
actions:
  - action: tts.speak
    target:
      entity_id: tts.home_assistant_cloud
    data:
      media_player_entity_id: media_player.flur
      message: >-
        Achtung, auf dem Arbeitsweg:
        {{ state_attr('binary_sensor.streckenwacht_arbeitsweg_disruption_active', 'disruptions')
           | map(attribute='title') | join(', ') }}
```

### Kalender im Dashboard

```yaml
type: calendar
initial_view: listWeek
entities:
  - calendar.streckenwacht_arbeitsweg
```

## Fehlerbehebung

- **Reparaturen:** Ist eine Quelle dreimal in Folge nicht erreichbar, erscheint unter *Einstellungen → System → Reparaturen* ein Hinweis. Er verschwindet von selbst, sobald der Abruf wieder klappt.
- **Diagnose:** *Geräte & Dienste → Streckenwacht → ⋮ → Diagnose herunterladen*. Die Koordinaten deiner Bereiche sind darin geschwärzt.
- **Ausführliches Protokoll:**

  ```yaml
  logger:
    logs:
      custom_components.streckenwacht: debug
  ```

## Fehler melden

Fehler und Ideen bitte als [GitHub-Issue](https://github.com/streckenwacht/integration/issues), möglichst mit Diagnose-Datei und Home-Assistant-Version.

## Lizenz

Code: [MIT](LICENSE). Die angezeigten Daten unterliegen den Lizenzen der jeweiligen Quellen (siehe [Datenquellen](#datenquellen)).
