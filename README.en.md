<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/streckenwacht/integration/main/assets/github/readme-header-dark@2x.png">
  <img alt="Streckenwacht – watches over your route." src="https://raw.githubusercontent.com/streckenwacht/integration/main/assets/github/readme-header-light@2x.png" width="640">
</picture>

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-005B8C.svg)](https://hacs.xyz/)
[![Release](https://img.shields.io/github/v/release/streckenwacht/integration?include_prereleases&color=005B8C)](https://github.com/streckenwacht/integration/releases)
[![CI](https://github.com/streckenwacht/integration/actions/workflows/ci.yml/badge.svg)](https://github.com/streckenwacht/integration/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-F5A623.svg)](LICENSE)

🇩🇪 [Deutsch](https://github.com/streckenwacht/integration/blob/main/README.md) · 🇬🇧 **English**

> ⚠️ **Testing phase.** Only pre-releases (beta) so far. Feedback is welcome – see [Reporting issues](#reporting-issues).

Streckenwacht ("route watch") keeps an eye on your route – motorway, federal road or your daily commute. Roadworks, closures, traffic jams and accidents in Germany, right in your Home Assistant: as a calendar, sensors and events for automations.

The integration's UI is available in German and English and follows your Home Assistant language. The screenshots below show the German UI.

## What Streckenwacht does

- Define **observation areas** freely: a circle on the map, e.g. "Home" or "Commute".
- Per area: choose **data sources**, **motorways** and **directions of travel** – e.g. only the A81 towards Stuttgart.
- Per area a **calendar** with all roadworks and closures; night-time roadworks appear as one entry per night.
- **"Disruption active"** as soon as a closure, an accident or a significant traffic jam is active in the area – ordinary long-term roadworks and minor delays deliberately do not trigger it.
- **Travel time loss** in minutes (largest current value in the area).
- **Event for new and ended reports** – ideal for push notifications.
- If one source fails, the others keep working; after repeated failures a notice appears under *Repairs*.

<img src="https://raw.githubusercontent.com/streckenwacht/integration/main/assets/screenshots/geraet.png" alt="Device of an observation area with calendar, events, travel time loss, disruption active and event change" width="720">

## Data sources

| Source | Coverage | License / attribution |
|---|---|---|
| [Autobahn GmbH – Autobahn API](https://verkehr.autobahn.de/o/autobahn) | Federal motorways, nationwide: roadworks, closures, warnings incl. traffic jams | Die Autobahn GmbH des Bundes |
| ↳ traffic jams within it | Traffic situation from vehicle data | Verkehrslage: INRIX (can be switched off, see [Options](#options)) |
| [MobiData BW](https://mobidata-bw.de/dataset/baustelleninformationen-baden-wurttemberg) | Federal, state and district roads in Baden-Württemberg, some municipal roads | Datenlizenz Deutschland – Namensnennung 2.0 |
| [City of Stuttgart – roadworks calendar](https://www.stuttgart.de/baustellenkalender) | Main roads (Vorbehaltsstraßennetz) in Stuttgart | CC BY 4.0, © Landeshauptstadt Stuttgart |

Every entity carries the required attribution in its `attribution` attribute.

## What Streckenwacht cannot do

The sources are not complete:

- The Autobahn API only covers federal motorways, not state, district or municipal roads.
- MobiData BW covers federal, state and district roads in Baden-Württemberg, municipal roads only occasionally.
- The Stuttgart roadworks calendar only covers the main road network – residential streets, emergency repairs and utility works without traffic impact are deliberately missing.
- Outside Baden-Württemberg only motorways are available.
- No source has a dedicated accident category; Streckenwacht recognizes accidents by the word "Unfall" in motorway warnings.
- None of the sources guarantees completeness or a fixed update frequency; all information comes unfiltered from the respective authorities and operators.

In short: Streckenwacht is well suited to keep an eye on major disruptions on main routes – not to catch every small construction site in every side street.

## Privacy

Your location never leaves Home Assistant. Streckenwacht downloads the reports of whole motorways, the statewide MobiData file and the Stuttgart list, and filters them locally to your areas. The requests contain no coordinates and no personal data, only an identifier of the integration (user agent). Unchanged data is not transferred again thanks to ETags.

## Installation (HACS, custom repository)

Requires Home Assistant **2026.3** or newer and [HACS](https://hacs.xyz/).

**One click:** [![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=streckenwacht&repository=integration&category=integration) → download, restart Home Assistant → [![Add integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=streckenwacht)

Or manually:

1. Open HACS → menu (⋮) → **Custom repositories**.
2. Enter `https://github.com/streckenwacht/integration`, type **Integration**, add.
3. Open **Streckenwacht** in HACS → **Download**. As long as there are only pre-releases, pick the newest version in the dialog (enable showing beta versions if needed).
4. Restart Home Assistant.
5. **Settings → Devices & services → Add integration → Streckenwacht**.

Note: the icon is currently missing in the HACS dashboard ([HACS issue #5171](https://github.com/hacs/integration/issues/5171)); it is shown in the Home Assistant settings.

## Setup

### Data sources and options

When adding the integration you choose the data sources. If your Home Assistant location is in Baden-Württemberg, all three are preselected, otherwise only the motorways.

<a id="options"></a>Change them later via **Devices & services → Streckenwacht → Configure**:

| Option | Default | Meaning |
|---|---|---|
| Data sources | depends on location | Which sources are queried at all |
| Update interval | 15 min | 10–60 minutes |
| Include traffic jams (INRIX) | on | Traffic jams and travel time loss from the Autobahn API |

<img src="https://raw.githubusercontent.com/streckenwacht/integration/main/assets/screenshots/optionen.png" alt="Options: data sources, update interval, traffic jams" width="400">

### Observation areas

On the Streckenwacht page choose **Add observation area**. The dialog guides you through up to three steps:

1. **Area** – name (becomes part of the entity IDs, e.g. "Commute"), circle on the map (max. 100 km) and the **data sources** for this area, e.g. only motorways for a commute.
2. **Motorways** – only if "Autobahn GmbH" is selected. Only their events within the circle are shown. The selection is needed because the Autobahn API always returns a whole motorway and cannot search by area. Here you also set **from how many minutes of travel time loss a traffic jam counts as a disruption** (default 10, 0 = every jam).
3. **Directions of travel** – you can choose from the directions currently used on the selected motorways. Leave empty for all directions. Events at junction ramps and events without a direction are always shown.

<table>
  <tr>
    <td valign="top"><img src="https://raw.githubusercontent.com/streckenwacht/integration/main/assets/screenshots/bereich_1_bereich.png" alt="Step 1: name, circle on the map, data sources" width="260"></td>
    <td valign="top"><img src="https://raw.githubusercontent.com/streckenwacht/integration/main/assets/screenshots/bereich_2_autobahnen.png" alt="Step 2: motorways and traffic jam threshold" width="260"></td>
    <td valign="top"><img src="https://raw.githubusercontent.com/streckenwacht/integration/main/assets/screenshots/bereich_3_richtungen.png" alt="Step 3: directions of travel" width="260"></td>
  </tr>
  <tr>
    <td>1. Area and sources</td>
    <td>2. Motorways</td>
    <td>3. Directions</td>
  </tr>
</table>

> **Tip for commutes across a motorway junction:** the direction name changes at the junction. Driving the A81 from Böblingen to Stuttgart-Feuerbach, for example, you need "Singen -> Stuttgart" **and** "Stuttgart -> Heilbronn".

Areas can be changed at any time via ⋮ → **Reconfigure**.

## Entities per observation area

Example for an area named "Commute" (device *Streckenwacht Commute*). Entity IDs are always English; displayed names follow your Home Assistant language.

| Entity | Name | Content |
|---|---|---|
| `calendar.streckenwacht_commute` | Streckenwacht Commute | All reports as calendar entries |
| `binary_sensor.streckenwacht_commute_disruption_active` | Disruption active | On while a closure, accident or traffic jam above the configured threshold is active. Attributes: `count`, `disruptions` |
| `sensor.streckenwacht_commute_events` | Events | Number of active reports. Attributes: count per type, `by_source`, `events` (up to 20, most severe first) |
| `sensor.streckenwacht_commute_travel_time_loss` | Travel time loss | Largest current travel time loss in minutes (only with traffic jam data) |
| `event.streckenwacht_commute_event_change` | Event change | Event type `new` or `ended` |

<img src="https://raw.githubusercontent.com/streckenwacht/integration/main/assets/screenshots/kalender.png" alt="Calendar in list view: night closures as single entries, current traffic jam" width="600">

**Types** (`type`): `roadworks`, `closure`, `traffic_jam`, `accident`, `warning` (other warning).

All entities have the attribute `unavailable_sources`: if a source cannot be reached right now, it is listed there – the data shown is then the last known state.

A `new` event contains `id`, `title`, `type`, `source`, `road`, `direction`, `start`, `end`, `delay_minutes`, `latitude`, `longitude`; an `ended` event `id`, `title`, `type` and `source`. After a restart or a change of the area, known reports are not announced as new again. Traffic jams are only announced as new from the area's jam threshold on (and only then as ended); when the traffic data assigns a new identifier to a jam, it is not announced as a new jam.

## What you can build with it

### Ready-made blueprints

No YAML: import the blueprint, select the area and your phone, done. *The blueprints currently use German texts (names and notifications).*

| Blueprint | What it does | |
|---|---|---|
| **Stau-Benachrichtigung** (traffic jam notification) | Push notification as soon as the travel time loss exceeds a threshold; optionally only within a time window | [![Import blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fstreckenwacht%2Fintegration%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fstreckenwacht%2Fstau_benachrichtigung.yaml) |
| **Neue oder beendete Meldung** (new or ended report) | Push notification for new reports of the selected types (e.g. closure, accident), optionally also when they end | [![Import blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fstreckenwacht%2Fintegration%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fstreckenwacht%2Fneue_meldung.yaml) |

Notifications go to a phone running the official Home Assistant app. If you need something else, adapt the YAML examples below.

### Push notification on travel time loss

```yaml
alias: Traffic jam on my commute
triggers:
  - trigger: numeric_state
    entity_id: sensor.streckenwacht_commute_travel_time_loss
    above: 15
actions:
  - action: notify.mobile_app_my_phone
    data:
      title: "Traffic jam on my commute"
      message: >-
        +{{ states('sensor.streckenwacht_commute_travel_time_loss') }} min:
        {{ state_attr('sensor.streckenwacht_commute_travel_time_loss', 'title') }}
```

### Notification on a new closure or accident

```yaml
alias: New closure on my commute
triggers:
  - trigger: state
    entity_id: event.streckenwacht_commute_event_change
conditions:
  - condition: template
    value_template: >-
      {{ trigger.to_state.attributes.event_type == 'new'
         and trigger.to_state.attributes.type in ['closure', 'accident'] }}
actions:
  - action: notify.mobile_app_my_phone
    data:
      title: "New on my commute"
      message: "{{ trigger.to_state.attributes.title }}"
```

### Announcement when leaving home

```yaml
alias: Announce disruptions on my commute
triggers:
  - trigger: state
    entity_id: person.me
    from: home
conditions:
  - condition: state
    entity_id: binary_sensor.streckenwacht_commute_disruption_active
    state: "on"
actions:
  - action: tts.speak
    target:
      entity_id: tts.home_assistant_cloud
    data:
      media_player_entity_id: media_player.hallway
      message: >-
        Attention, on your commute:
        {{ state_attr('binary_sensor.streckenwacht_commute_disruption_active', 'disruptions')
           | map(attribute='title') | join(', ') }}
```

### Calendar on the dashboard

```yaml
type: calendar
initial_view: listWeek
entities:
  - calendar.streckenwacht_commute
```

## Troubleshooting

- **Repairs:** if a source cannot be reached three times in a row, a notice appears under *Settings → System → Repairs*. It disappears by itself as soon as fetching works again.
- **Diagnostics:** *Devices & services → Streckenwacht → ⋮ → Download diagnostics*. The coordinates of your areas are redacted.
- **Detailed log:**

  ```yaml
  logger:
    logs:
      custom_components.streckenwacht: debug
  ```

## Reporting issues

Please report bugs and ideas as a [GitHub issue](https://github.com/streckenwacht/integration/issues), ideally with the diagnostics file and your Home Assistant version. Issues in English are welcome.

## License

Code: [MIT](LICENSE). The data shown is subject to the licenses of the respective sources (see [Data sources](#data-sources)).
