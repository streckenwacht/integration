"""Short report for a bug report: what a GitHub issue needs, nothing else.

Many users do not want to post the diagnostics download: Home Assistant puts
its own header in front (every custom integration, OS, time zone), and the
file holds more than an issue needs. This report is plain text the user reads
before sharing it, shown as a notification by a button:

- versions;
- the mapping by role: integration, unit, classes and state of each source,
  without entity ids, names or areas (`private` roles: only whether the state
  is a number, not the number, e.g. a meter reading); integrations polling a
  web service add the status of each endpoint (`endpoints`);
- the settings: the entry's options, or `setting_lines` given instead (a
  whitelist where the settings hold entity ids, names, places or free text);
- which own entities have no value, with their `reason`;
- open repair issues of the entry: ids with the entry id in front or at the
  end, every issue of the domain when it has only this entry or the caller
  says so (`all_domain_issues`, issues shared by all entries); shown without
  the entry id, by kind (translation key) where the id holds an entity id;
- a few lines of the entry's own state (`extra`), further sections (`more`).

`show(intro=...)` replaces the notice above the report.

The same file in all six sister projects (Eilwacht, Einspeisewacht,
Speicherwacht, Streckenwacht, Tarifwacht, Wärmewacht); change it in all of
them. `render` and `issue_key` are pure; the rest reads Home Assistant.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Iterable, Mapping, Sequence
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir

Lines = list[tuple[str, str]]
Section = tuple[str, Lines]

NO_VALUE = (STATE_UNKNOWN, STATE_UNAVAILABLE)
# Text states longer than this are cut: a source may put anything there.
MAX_TEXT = 40
# Never "missing": a button has no value, an event entity none until it fires.
NO_STATE_DOMAINS = ("button", "event")

INTRO = {
    "de": (
        "Zum Kopieren für eine Fehlermeldung auf GitHub. Der Bericht enthält "
        "keine Entity-IDs, Namen oder Bereiche – lies ihn trotzdem, bevor du "
        "ihn teilst, und lösche, was du nicht zeigen willst."
    ),
    "en": (
        "To copy into a bug report on GitHub. The report holds no entity ids, "
        "names or areas - still read it before you share it and delete what "
        "you would rather not show."
    ),
}
TITLE = {
    "de": "{name}: Bericht für Fehlermeldung",
    "en": "{name}: report for a bug report",
}


def render(title: str, sections: Iterable[Section]) -> str:
    """The report as plain text: a title line, then `key: value` lines under
    each section heading. Empty sections are left out."""
    out = [title]
    for heading, lines in sections:
        if not lines:
            continue
        out.append("")
        out.append(f"[{heading}]")
        out.extend(f"{key}: {value}" for key, value in lines)
    return "\n".join(out)


def issue_key(issue_id: str, entry_id: str) -> str | None:
    """The kind of a repair issue of this entry: its id with the entry id
    taken off the front (`<entry>_<key>`) or the end (`<key>_<entry>`), None
    for another entry's."""
    if issue_id.startswith(f"{entry_id}_"):
        return issue_id.removeprefix(f"{entry_id}_")
    if issue_id.endswith(f"_{entry_id}"):
        return issue_id.removesuffix(f"_{entry_id}")
    return None


def _language(hass: HomeAssistant) -> str:
    return "de" if (hass.config.language or "").startswith("de") else "en"


def _short(text: str) -> str:
    return text if len(text) <= MAX_TEXT else text[: MAX_TEXT - 1] + "…"


def _is_number(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


def source(hass: HomeAssistant, entity_id: str | None, *, private: bool = False) -> str:
    """One source by its properties, not its id: integration, unit, classes,
    and the state (numbers as they are, text cut short). `private`: a number
    only as "numeric state" (e.g. a meter reading)."""
    if not entity_id:
        return "-"
    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    state = hass.states.get(entity_id)
    parts = [entry.platform if entry else "no registry entry"]
    if entry is not None and entry.disabled_by:
        parts.append(f"disabled ({entry.disabled_by})")
    if state is None:
        parts.append("no state")
        return ", ".join(parts)
    attributes = state.attributes
    for key in ("unit_of_measurement", "device_class", "state_class"):
        if (value := attributes.get(key)) is not None:
            parts.append(str(value))
    if private and _is_number(state.state):
        parts.append("numeric state")
    else:
        parts.append(f"state {_short(state.state)}")
    return ", ".join(parts)


def sources(
    hass: HomeAssistant, mapping: Mapping[str, str], private: Collection[str] = ()
) -> Lines:
    return [
        (role, source(hass, entity_id, private=role in private))
        for role, entity_id in mapping.items()
    ]


def settings(options: Mapping[str, Any]) -> Lines:
    return [(key, str(value)) for key, value in sorted(options.items())]


def own_entities(hass: HomeAssistant, entry: ConfigEntry) -> Lines:
    """How many own entities have a value, and every one without, with the
    `reason` attribute it gives. Buttons, event entities and disabled
    entities are skipped."""
    registry = er.async_get(hass)
    valued = 0
    missing: Lines = []
    for item in er.async_entries_for_config_entry(registry, entry.entry_id):
        if item.disabled_by or item.domain in NO_STATE_DOMAINS:
            continue
        key = item.translation_key or item.unique_id
        state = hass.states.get(item.entity_id)
        if state is None or state.state in NO_VALUE:
            reason = state.attributes.get("reason") if state else None
            value = state.state if state else "no state"
            missing.append((key, f"{value} ({reason})" if reason else value))
        else:
            valued += 1
    return [("with a value", str(valued)), *sorted(missing)]


def repairs(
    hass: HomeAssistant,
    domain: str,
    entry: ConfigEntry,
    *,
    all_domain_issues: bool = False,
) -> Lines:
    """Open repair issues of the entry, without the entry id; by kind
    (translation key) where the rest of the id holds an entity id (a dot).
    Several of one kind with a count. With a single entry of the domain, or
    `all_domain_issues`, every issue of the domain counts."""
    registry = ir.async_get(hass)
    only_entry = (
        all_domain_issues or len(hass.config_entries.async_entries(domain)) == 1
    )
    found: Counter[str] = Counter()
    for (issue_domain, issue_id), issue in registry.issues.items():
        if (
            issue_domain != domain
            or not issue.active
            or issue.dismissed_version is not None
        ):
            continue
        key = issue_key(issue_id, entry.entry_id)
        if key is None and not only_entry:
            continue
        label = key or issue_id
        if "." in label:
            label = issue.translation_key or "issue"
        found[label] += 1
    kinds = [f"{key} ({n})" if n > 1 else key for key, n in sorted(found.items())]
    return [("open", ", ".join(kinds) if kinds else "none")]


def build(
    hass: HomeAssistant,
    domain: str,
    name: str,
    version: str,
    entry: ConfigEntry,
    *,
    extra: Lines,
    mapping: Mapping[str, str] | None = None,
    private: Collection[str] = (),
    endpoints: Sequence[tuple[str, str]] = (),
    setting_lines: Lines | None = None,
    more: Iterable[Section] = (),
    all_domain_issues: bool = False,
) -> str:
    """The whole report of one entry. `mapping`: role -> source entity;
    `private`: roles whose number is not shown; `endpoints`: status lines of
    polled web services; `setting_lines`: instead of all options; `more`:
    sections after `entry`; `all_domain_issues`: see `repairs`."""
    return render(
        f"{name} {version}, Home Assistant {HA_VERSION}",
        [
            ("entry", extra),
            *more,
            ("sources", [*sources(hass, mapping or {}, private), *endpoints]),
            (
                "settings",
                settings(entry.options) if setting_lines is None else setting_lines,
            ),
            ("own entities", own_entities(hass, entry)),
            (
                "repairs",
                repairs(hass, domain, entry, all_domain_issues=all_domain_issues),
            ),
        ],
    )


def show(
    hass: HomeAssistant,
    domain: str,
    name: str,
    entry: ConfigEntry,
    report: str,
    *,
    intro: Mapping[str, str] | None = None,
) -> None:
    """The report as a notification, in a code block to copy as is. One per
    entry: pressing again replaces it. `intro` replaces the notice above it
    (keys "de" and "en")."""
    language = _language(hass)
    persistent_notification.async_create(
        hass,
        f"{(intro or INTRO)[language]}\n\n```text\n{report}\n```",
        title=TITLE[language].format(name=name),
        notification_id=f"{domain}_issue_report_{entry.entry_id}",
    )
