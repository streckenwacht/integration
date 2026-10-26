<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/streckenwacht/integration/main/assets/github/readme-header-dark@2x.png">
  <img alt="Streckenwacht – watches over your route." src="https://raw.githubusercontent.com/streckenwacht/integration/main/assets/github/readme-header-light@2x.png" width="640">
</picture>

[![HACS Default](https://img.shields.io/badge/HACS-Default-005B8C.svg)](https://hacs.xyz/)
[![Release](https://img.shields.io/github/v/release/streckenwacht/integration?color=005B8C)](https://github.com/streckenwacht/integration/releases)
[![CI](https://github.com/streckenwacht/integration/actions/workflows/ci.yml/badge.svg)](https://github.com/streckenwacht/integration/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-F5A623.svg)](LICENSE)

🇩🇪 [Deutsch](https://github.com/streckenwacht/integration/blob/main/README.md) · 🇬🇧 **English**

> ℹ️ **Young project.** Version 0.7 – the core runs stably, new data sources and features were just added. Feedback is very welcome – see [Reporting issues](#reporting-issues).

Streckenwacht ("route watch") keeps an eye on your route – motorway, federal road or your daily commute. Roadworks, closures, traffic jams and accidents in Germany, right in your Home Assistant: as a calendar, sensors and events for automations.

The integration's UI is available in German and English and follows your Home Assistant language. The screenshots below show the German UI.

## What Streckenwacht does

- Define **observation areas** freely: a circle on the map, e.g. "Home" or "Commute".
- Per area: choose **data sources**, **motorways** and **directions of travel** – e.g. only the A81 towards Stuttgart.
- Per area a **calendar** with all roadworks and closures; night-time roadworks appear as one entry per night.
- **"Disruption active"** as soon as a closure, an accident or a significant traffic jam is active in the area – long-term roadworks, closures lasting months (after their first week) and minor delays deliberately do not trigger it.
- **Travel time loss** in minutes (largest current value in the area).
- **Event for new and ended reports** – ideal for push notifications.
- **Map:** all current reports as markers on the dashboard map card.
- If one source fails, the others keep working; after repeated failures a notice appears under *Repairs*.

<img src="https://raw.githubusercontent.com/streckenwacht/integration/main/assets/screenshots/geraet.png" alt="Device of an observation area with calendar, events, travel time loss, disruption active and event change" width="720">

## Data sources

| Source | Coverage | License / attribution |
|---|---|---|
| [Autobahn GmbH – Autobahn API](https://verkehr.autobahn.de/o/autobahn) | Federal motorways, nationwide: roadworks, closures, warnings incl. traffic jams | Die Autobahn GmbH des Bundes |
| ↳ traffic jams within it | Traffic situation from vehicle data | Verkehrslage: INRIX (can be switched off, see [Options](#options)) |
| [MobiData BW](https://mobidata-bw.de/dataset/baustelleninformationen-baden-wurttemberg) | Federal, state and district roads in Baden-Württemberg, some municipal roads | Datenlizenz Deutschland – Namensnennung 2.0 |
| [Landesmeldestelle Baden-Württemberg](https://mobidata-bw.de/dataset/f5459a52-a06e-4a1b-bf68-75d3788c716f) | Radio traffic messages outside the motorways: closures with diversions, accidents, jams and hazards – mostly around Stuttgart | Landesmeldestelle Baden-Württemberg / MobiData BW, dl-de/by-2-0 |
| [City of Stuttgart – roadworks calendar](https://www.stuttgart.de/baustellenkalender) | Main roads (Vorbehaltsstraßennetz) in Stuttgart | CC BY 4.0, © Landeshauptstadt Stuttgart |
| [Roadworks information northern Germany (LBV.SH)](https://dienste.gdi-sh.de/WFS_SH_Baustelleninformationen?SERVICE=WFS&REQUEST=GetCapabilities) | Schleswig-Holstein (all road classes, plus current traffic disruptions and accidents), Hamburg, Mecklenburg-Vorpommern, federal roads in Lower Saxony | CC BY 4.0, © Geokompetenz/LVermGeo SH |
| [VIZ Berlin](https://daten.berlin.de/datensaetze/baustellen-sperrungen-und-sonstige-storungen-von-besonderem-verkehrlichem-interesse) | Berlin's main roads: roadworks, closures, incidents (motorway works come from Autobahn GmbH) | Digitale Plattform Stadtverkehr Berlin, dl-de/by-2-0 |
| [Landesbetrieb Straßenwesen Brandenburg](https://isk.geobasis-bb.de/ows/baustelleninfo_wfs?SERVICE=WFS&REQUEST=GetCapabilities) | Federal, state and district roads in Brandenburg | © Landesbetrieb Straßenwesen Brandenburg, dl-de/by-2-0 |
| [Sperrinfo Sachsen-Anhalt](https://service.ifak.eu/sperrinfo/wfs?SERVICE=WFS&REQUEST=GetCapabilities) | All road classes in Saxony-Anhalt incl. municipal roads | Ministerium für Landesentwicklung und Verkehr; according to the service **non-commercial use only** |
| [Baustelleninformationssystem Sachsen](https://www.baustellen.sachsen.de/baustellendaten-dienste-3997.html) | All road classes in Saxony incl. municipal roads (motorways come from Autobahn GmbH) | Baustelleninformationssystem Sachsen, CC BY 4.0 |
| [Mobilitätsatlas Rheinland-Pfalz](https://verkehr.rlp.de) | All road classes in Rhineland-Palatinate (reports of state and local authorities) | Landesbetrieb Mobilität Rheinland-Pfalz; published openly, no license declared |
| [Landeshauptstadt München](https://opendata.muenchen.de/dataset/baustellen_4_weeks_opendata) | Roadworks on the carriageway in Munich (next four weeks; parking and footpath restrictions left out) | dl-de/by-2-0: Landeshauptstadt München – opendata.muenchen.de |
| [City of Cologne – traffic calendar](https://www.stadt-koeln.de/leben-in-koeln/verkehr/verkehrskalender/) | Traffic-relevant roadworks, closures and events on Cologne's main roads | Stadt Köln, dl-de/zero-2-0 |
| [City of Frankfurt am Main](https://geowebdienste.frankfurt.de/Baustellen?SERVICE=WFS&REQUEST=GetCapabilities) | Roadworks and traffic messages in Frankfurt | Stadt Frankfurt am Main; published openly, no license declared |
| [City of Dortmund](https://open-data.dortmund.de/explore/dataset/fb66-baustellen-tagesaktuell/) | Roadworks in Dortmund (current and planned) | Stadt Dortmund, dl-de/zero-2-0 |
| [City of Aachen](https://bsis.aachen.de) | Roadworks in Aachen (without footpath- and parking-only restrictions) | Stadt Aachen, dl-de/by-2-0 |
| [City of Duisburg](https://opendata-duisburg.de/dataset/baustellen-duisburg) | Current roadworks in Duisburg | Stadt Duisburg, CC BY 3.0 DE |
| [City of Münster](https://opendata.stadt-muenster.de/dataset/baustellen) | Major roadworks in Münster | Stadt Münster, dl-de/by-2-0 |
| [Ponts et Chaussées Luxembourg](https://data.public.lu/fr/datasets/pch-les-chantiers-actuels/) | Current and planned roadworks on Luxembourg's roads – for commuters from Trier, Saarland and the Eifel | Administration des Ponts et Chaussées, CC0 |
| [Mobilitätsportal Technologieregion Karlsruhe](https://mobil.trk.de/) | Roadworks with closures or traffic impact in Karlsruhe and its region | Stadt Karlsruhe / Mobilitätsportal Technologieregion Karlsruhe, CC BY 4.0 |
| [City of Rostock](https://www.opendata-hro.de/dataset/baustellen) | Roadworks in Rostock (without footpath- and façade-only works) | Hanse- und Universitätsstadt Rostock, CC0 |
| [City of Kiel](https://ims.kiel.de/geodatenextern/services/Stadtplan/LHKielWmsWfs/MapServer/WFSServer?SERVICE=WFS&REQUEST=GetCapabilities) | Current and planned roadworks in Kiel | Landeshauptstadt Kiel, CC BY 4.0 |
| [City of Ingolstadt](https://open.bydata.de/datasets/baustellen_stadt_ingolstadt) | Roadworks with full or one-sided closures in Ingolstadt (next 14 days) | Stadt Ingolstadt, CC BY 4.0 |
| [City of Freiburg im Breisgau](https://geoportal.freiburg.de/wfs/gut_baustellen/gut_baustellen?SERVICE=WFS&REQUEST=GetCapabilities) | Major roadworks on Freiburg's main roads | Stadt Freiburg i. Br. – Garten- und Tiefbauamt, dl-de/by-2-0 |

Every entity carries the required attribution in its `attribution` attribute.

### Duplicate reports

Some roadworks are reported by several sources – in Stuttgart, for example, the Landesmeldestelle reports the closure and the city the works behind it. Streckenwacht merges such reports into one: same road, at most 300 m apart, matching time window, roadworks and closures only. The closure leads; the other sources are listed in the description, in `also_reported_by` and in the attribution. You are notified once. It can be switched off under *Configure*.

## What Streckenwacht cannot do

The sources are not complete:

- The Autobahn API only covers federal motorways, not state, district or municipal roads.
- MobiData BW covers federal, state and district roads in Baden-Württemberg, municipal roads only occasionally.
- The Stuttgart roadworks calendar only covers the main road network – residential streets, emergency repairs and utility works without traffic impact are deliberately missing.
- The northern German data differs per state: Lower Saxony only has federal roads, Mecklenburg-Vorpommern often lacks road names.
- In Bavaria, Hesse and North Rhine-Westphalia there are only single cities so far (Munich, Frankfurt, Cologne, Dortmund, Aachen, Duisburg, Münster); in Thuringia, Bremen and Saarland only motorways.
- No source has a dedicated accident category; Streckenwacht recognizes accidents by the word "Unfall" in warnings and traffic disruptions.
- None of the sources guarantees completeness or a fixed update frequency; all information comes unfiltered from the respective authorities and operators.

In short: Streckenwacht is well suited to keep an eye on major disruptions on main routes – not to catch every small construction site in every side street.

## Privacy

Your location never leaves Home Assistant. Streckenwacht downloads the reports of whole motorways or statewide and citywide files (e.g. MobiData BW, Saxony, Berlin), and filters them locally to your areas. Unchanged data is not transferred again thanks to ETags.

The exception are large state sources without ETag (northern Germany, Brandenburg): they are too large to download completely on every poll. Streckenwacht therefore requests a coarse map section there, rounded to a grid of about 55 × 35 km. The server only learns the rough region, not your area.

The requests contain no personal data, only an identifier of the integration (user agent). The Streckenwacht map card loads its base map through Home Assistant itself, not directly from OpenStreetMap.

## Installation (HACS)

Requires Home Assistant **2026.3** or newer and [HACS](https://hacs.xyz/).

**One click:** [![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=streckenwacht&repository=integration&category=integration) → download, restart Home Assistant → [![Add integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=streckenwacht)

Or manually – Streckenwacht has been in the HACS default list since October 2026, no custom repository needed:

1. Open HACS, search for **Streckenwacht** → **Download**.
2. Restart Home Assistant.
3. **Settings → Devices & services → Add integration → Streckenwacht**.

Note: the icon is currently missing in the HACS dashboard ([HACS issue #5171](https://github.com/hacs/integration/issues/5171)); it is shown in the Home Assistant settings.

## Setup

### Data sources and options

When adding the integration, Streckenwacht only asks for the update interval and traffic jams. Data sources are chosen per observation area (see below); whatever any area uses is queried.

<a id="options"></a>Change them later via **Devices & services → Streckenwacht → Configure**:

| Option | Default | Meaning |
|---|---|---|
| Update interval | 15 min | 10–60 minutes |
| Include traffic jams (INRIX) | on | Traffic jams and travel time loss from the Autobahn API |
| Merge duplicate reports | on | The same roadworks from several sources are shown once (see below) |

<img src="https://raw.githubusercontent.com/streckenwacht/integration/main/assets/screenshots/optionen.png" alt="Options: update interval, traffic jams" width="400">

### Observation areas

On the Streckenwacht page choose **Add observation area**. The dialog guides you through up to four steps:

1. **Area** – name (becomes part of the entity IDs, e.g. "Commute"), circle on the map (max. 100 km) and the **kinds of reports** (roadworks, closures, traffic jams, accidents, warnings). To see only closures and accidents in a city, deselect roadworks – this then applies to the calendar, sensors, map and notifications of this area.
2. **Data sources** – offered are the motorways and every source whose region touches the circle, all preselected. Deselect what you don't need, e.g. everything but the motorways for a commute. If only the motorways are available, this step is skipped.
3. **Motorways** – only if "Autobahn GmbH" is selected. Only their events within the circle are shown. The selection is needed because the Autobahn API always returns a whole motorway and cannot search by area. Here you also set **from how many minutes of travel time loss a traffic jam counts as a disruption** (default 10, 0 = every jam).
4. **Directions of travel** – you can choose from the directions currently used on the selected motorways. Leave empty for all directions. Events at junction ramps and events without a direction are always shown.

<table>
  <tr>
    <td valign="top"><img src="https://raw.githubusercontent.com/streckenwacht/integration/main/assets/screenshots/bereich_1_bereich.png" alt="Step 1: name, circle on the map, kinds of reports" width="200"></td>
    <td valign="top"><img src="https://raw.githubusercontent.com/streckenwacht/integration/main/assets/screenshots/bereich_2_quellen.png" alt="Step 2: data sources matching the circle" width="200"></td>
    <td valign="top"><img src="https://raw.githubusercontent.com/streckenwacht/integration/main/assets/screenshots/bereich_3_autobahnen.png" alt="Step 3: motorways and traffic jam threshold" width="200"></td>
    <td valign="top"><img src="https://raw.githubusercontent.com/streckenwacht/integration/main/assets/screenshots/bereich_4_richtungen.png" alt="Step 4: directions of travel" width="200"></td>
  </tr>
  <tr>
    <td>1. Area and kinds of reports</td>
    <td>2. Data sources</td>
    <td>3. Motorways</td>
    <td>4. Directions</td>
  </tr>
</table>

> **Tip for commutes across a motorway junction:** the direction name changes at the junction. Driving the A81 from Böblingen to Stuttgart-Feuerbach, for example, you need "Singen -> Stuttgart" **and** "Stuttgart -> Heilbronn".

Areas can be changed at any time via ⋮ → **Reconfigure**.

## Entities per observation area

Example for an area named "Commute" (device *Streckenwacht Commute*). Entity IDs are always English; displayed names follow your Home Assistant language.

| Entity | Name | Content |
|---|---|---|
| `calendar.streckenwacht_commute` | Streckenwacht Commute | All reports as calendar entries |
| `binary_sensor.streckenwacht_commute_disruption_active` | Disruption active | On while a closure, accident or traffic jam above the configured threshold is active. Closures whose current time window is longer than 30 days only count during their first week (they stay in the calendar and under "Events"). Attributes: `count`, `disruptions` |
| `sensor.streckenwacht_commute_events` | Events | Number of active reports. Attributes: count per type, `by_source`, `events` (up to 20, most severe first) |
| `sensor.streckenwacht_commute_travel_time_loss` | Travel time loss | Largest current travel time loss in minutes (only with traffic jam data). Attributes: `title`, `road`, `direction` of the report with the largest loss; `by_direction` = largest loss per route direction ("Start -> Destination", ramps excluded), e.g. `{"Karlsruhe -> Heidelberg": 14, "Heidelberg -> Karlsruhe": 5}`, so an automation can pick its own carriageway |
| `sensor.streckenwacht_commute_next_closure` | Next closure | Start of the next planned closure (within 14 days) as a timestamp. Attributes: `title`, `road`, `direction`, `end`, `source` |
| `event.streckenwacht_commute_event_change` | Event change | Event type `new` or `ended` |

<img src="https://raw.githubusercontent.com/streckenwacht/integration/main/assets/screenshots/kalender.png" alt="Calendar in list view: night closures as single entries, current traffic jam" width="600">

**Types** (`type`): `roadworks`, `closure`, `traffic_jam`, `accident`, `warning` (other warning).

All entities have the attribute `unavailable_sources`: if a source cannot be reached right now, it is listed there – the data shown is then the last known state.

A `new` event contains `id`, `title`, `type`, `source`, `road`, `direction`, `start`, `end`, `delay_minutes`, `latitude`, `longitude`, `also_reported_by`; an `ended` event `id`, `title`, `type` and `source`. After a restart or a change of the area, known reports are not announced as new again. Traffic jams are only announced as new from the area's jam threshold on (and only then as ended); when the traffic data assigns a new identifier to a jam, it is not announced as a new jam.

## What you can build with it

### Ready-made blueprints

No YAML: import the blueprint, select the area and your phone, done. *The blueprints currently use German texts (names and notifications).*

| Blueprint | What it does | |
|---|---|---|
| **Stau-Benachrichtigung** (traffic jam notification) | Push notification as soon as the travel time loss exceeds a threshold; optionally only within a time window | [![Import blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fstreckenwacht%2Fintegration%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fstreckenwacht%2Fstau_benachrichtigung.yaml) |
| **Vorwarnung vor geplanter Sperrung** (closure warning) | Push notification with a configurable lead time (default 12 hours) before a planned closure begins – e.g. the evening before a night closure | [![Import blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fstreckenwacht%2Fintegration%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fstreckenwacht%2Fvorwarnung_sperrung.yaml) |
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

### Dashboard with travel time loss

One status card per route (green, orange, red) with the current delay, the reports below, plus the history of the travel time loss:

<img src="https://raw.githubusercontent.com/streckenwacht/integration/main/assets/screenshots/dashboard_strecken.png" alt="Two routes with status card and list of reports" width="720">
<img src="https://raw.githubusercontent.com/streckenwacht/integration/main/assets/screenshots/dashboard_verlauf.png" alt="Travel time loss over 24 hours" width="360">

The list of reports is a standard Markdown card. The status card uses [Mushroom](https://github.com/piitaya/lovelace-mushroom), the history in the picture [ApexCharts](https://github.com/RomRider/apexcharts-card) (both via HACS); without extra cards, the built-in history graph (`history-graph`) does the job. Example for an area named "Commute":

```yaml
type: vertical-stack
cards:
  - type: custom:mushroom-template-card  # Mushroom (HACS)
    entity: sensor.streckenwacht_commute_events
    icon: mdi:car-clock
    primary: >-
      {% set d = states('sensor.streckenwacht_commute_travel_time_loss') | int(0) %}
      {{ 'Clear' if d == 0 else '+' ~ d ~ ' min delay' }}
    secondary: >-
      {% set ent = 'sensor.streckenwacht_commute_events' %}
      {% set labels = {'accident': ['accident', 'accidents'], 'traffic_jam': ['traffic jam', 'traffic jams'],
         'closure': ['closure', 'closures'], 'warning': ['warning', 'warnings'],
         'roadworks': ['roadworks', 'roadworks']} %}
      {% set ns = namespace(p=[]) %}
      {% for k, v in labels.items() %}{% set n = state_attr(ent, k) | int(0) %}
      {% if n > 0 %}{% set ns.p = ns.p + [n ~ ' ' ~ (v[0] if n == 1 else v[1])] %}{% endif %}{% endfor %}
      {{ ns.p | join(' · ') if ns.p else 'No reports' }}
    icon_color: >-
      {% set d = states('sensor.streckenwacht_commute_travel_time_loss') | int(0) %}
      {% if is_state('binary_sensor.streckenwacht_commute_disruption_active', 'on') or d >= 15 %}red
      {% elif d > 0 %}orange{% else %}green{% endif %}
    tap_action:
      action: more-info
  - type: markdown
    content: |
      {% set events = state_attr('sensor.streckenwacht_commute_events', 'events') or [] %}
      {% set meta = {'accident': ['mdi:car-emergency', 'Accident'], 'traffic_jam': ['mdi:car-multiple', 'Traffic jam'],
         'closure': ['mdi:road-variant', 'Closure'], 'warning': ['mdi:alert-outline', 'Warning'],
         'roadworks': ['mdi:sign-caution', 'Roadworks']} %}
      {% for e in events %}
      <ha-icon icon="{{ meta[e.type][0] }}"></ha-icon> **{{ e.title }}**{% if e.delay_minutes %} · **+{{ e.delay_minutes }} min**{% endif %}<br>
      <small>{{ meta[e.type][1] }}{% if e.direction %} · {{ e.direction }}{% endif %} · {{ 'until ' ~ (as_datetime(e.end) | as_local).strftime('%Y-%m-%d') if e.end else 'open end' }}</small>

      {% else %}
      <ha-icon icon="mdi:check-circle-outline"></ha-icon> No reports – clear road.
      {% endfor %}
  - type: history-graph
    title: Travel time loss (24 h)
    hours_to_show: 24
    entities:
      - entity: sensor.streckenwacht_commute_travel_time_loss
        name: Commute
```

### Travel time loss in the long run

Home Assistant automatically keeps long-term statistics for the "travel time loss" sensor. The statistics graph card can show, for example, the weekly average and the worst jam – handy to see whether roadworks slow down the route for good:

```yaml
type: statistics-graph
title: Travel time loss per week
entities:
  - sensor.streckenwacht_commute_travel_time_loss
period: week
days_to_show: 90
stat_types:
  - mean
  - max
chart_type: bar
```

The average includes the jam-free hours (0 minutes at night) and is therefore low; the maximum usually says more. Use `period: month` and `days_to_show: 365` for a yearly overview.

### Calendar on the dashboard

```yaml
type: calendar
initial_view: listWeek
entities:
  - calendar.streckenwacht_commute
```

### Streckenwacht map card

Streckenwacht ships its own dashboard card: it shows the reports of one or more areas with their real geometry – roadworks and closures as lines or areas along the road, coloured by type (closure red, roadworks orange, traffic jam dark red, accident purple, warning yellow). Reports starting within the next 14 days are drawn pale and dashed. Tapping one shows title, period, description and source(s); the map fits the areas' circles. A report lying in several areas is shown once. When zoomed out, nearby reports are grouped into circles with their count (coloured by the most severe one); tapping one zooms in, and from street level on every report is drawn on its own.

<img src="https://raw.githubusercontent.com/streckenwacht/integration/main/assets/screenshots/streckenwacht_karte.png" alt="Streckenwacht map card: traffic jam as a line on the A81 with popup, roadworks near Leonberg" width="726">

After the update the card is simply there: *Add card* → "Streckenwacht", then pick one or more areas in the editor (an entity of each area). Streckenwacht adds it to *Settings → Dashboards → ⋮ → Resources* by itself and keeps that entry up to date. Or in YAML:

```yaml
type: custom:streckenwacht-map-card
entities:                    # any entity of each area
  - sensor.streckenwacht_commute_events
  - sensor.streckenwacht_home_events
title: Commute               # optional
height: 400                  # optional, pixels
show_planned: true           # optional, show planned reports
cluster: true                # optional, group nearby reports
```

The card loads its base map through Home Assistant's map tile proxy (2026.9 and later): your browser only talks to Home Assistant, not to OpenStreetMap. On older versions the card shows the reports without a base map and a notice.

### Map in the dashboard (built-in map card)

All current reports of your areas appear as markers on the map card (one `geo_location` entity per report, at most 150, most severe and nearest first):

```yaml
type: map
cluster: false  # every report on its own instead of groups
geo_location_sources:
  - source: streckenwacht
    label_mode: icon
entities:
  - zone.home
```

<img src="https://raw.githubusercontent.com/streckenwacht/integration/main/assets/screenshots/karte.png" alt="Map card with roadworks icons on the A81 near Leonberg" width="420">

With `label_mode: icon` each marker shows the icon of its type (roadworks, closure, traffic jam, accident, warning) instead of initials. Tapping a marker shows title, type, road, period and the source's attribution. The markers come and go with the reports and do not end up in the entity list.

## Troubleshooting

- **Repairs:** if a source cannot be reached three times in a row, a notice appears under *Settings → System → Repairs*. It disappears by itself as soon as fetching works again.
- **Diagnostics:** *Devices & services → Streckenwacht → ⋮ → Download diagnostics*. The coordinates of your areas are redacted.
- **Map card shows "Custom element not found":** reload the page (in the Companion app: *Settings → Companion app → Troubleshooting → Reset frontend cache*). This can happen right after an update if the page was opened while Home Assistant was still starting. If it persists, check that *Settings → Dashboards → ⋮ → Resources* lists `/streckenwacht/frontend/streckenwacht-map-card.js` (added when Streckenwacht starts).
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
