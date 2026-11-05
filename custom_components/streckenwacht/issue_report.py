"""Short report for a bug report: what a GitHub issue needs, nothing else.

Many users do not want to post the diagnostics download: Home Assistant puts
its own header in front (every custom integration, OS, time zone), and the
file lists every entity of the source devices. This report is plain text the
user reads before sharing it, shown as a notification by a button:

- versions;
- the mapping by role: integration, unit, classes and state of each source,
  without entity ids, names or areas;
- the settings;
- which own entities have no value, with their `reason`;
- open repair issues of the entry;
- a few lines of the entry's own state (`extra`).

An integration whose sources are not entities (network services) passes its
own `source_lines`; one whose options name places or roads passes a positive
list as `settings_lines` instead of all options. Further sections go into
`more`, a different notice into `show(intro=...)`.

`render` is pure; the rest reads Home Assistant's registries.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
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
# Never "missing": a button has no value, an event entity none until it fires.
NO_STATE_DOMAINS = ("button", "event")
# Text states longer than this are cut: a source may put anything there.
MAX_TEXT = 40

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


def _language(hass: HomeAssistant) -> str:
    return "de" if (hass.config.language or "").startswith("de") else "en"


def _short(text: str) -> str:
    return text if len(text) <= MAX_TEXT else text[: MAX_TEXT - 1] + "…"


def source(hass: HomeAssistant, entity_id: str | None) -> str:
    """One source by its properties, not its id: integration, unit, classes,
    and the state (numbers as they are, text cut short)."""
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
    parts.append(f"state {_short(state.state)}")
    return ", ".join(parts)


def sources(hass: HomeAssistant, mapping: Mapping[str, str]) -> Lines:
    return [(role, source(hass, entity_id)) for role, entity_id in mapping.items()]


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
    hass: HomeAssistant, domain: str, entry: ConfigEntry, *, entry_only: bool = True
) -> Lines:
    """Open repair issues of the entry (ids start with the entry id); with
    `entry_only=False` all of the domain (an integration with one entry)."""
    registry = ir.async_get(hass)
    found = sorted(
        issue_id.removeprefix(f"{entry.entry_id}_")
        for (issue_domain, issue_id), issue in registry.issues.items()
        if issue_domain == domain
        and issue.active
        and issue.dismissed_version is None
        and (not entry_only or issue_id.startswith(entry.entry_id))
    )
    return [("open", ", ".join(found) if found else "none")]


def build(
    hass: HomeAssistant,
    domain: str,
    name: str,
    version: str,
    entry: ConfigEntry,
    *,
    extra: Lines,
    mapping: Mapping[str, str] | None = None,
    source_lines: Lines | None = None,
    settings_lines: Lines | None = None,
    more: Iterable[Section] = (),
    entry_issues_only: bool = True,
) -> str:
    """The whole report of one entry."""
    return render(
        f"{name} {version}, Home Assistant {HA_VERSION}",
        [
            ("entry", extra),
            *more,
            (
                "sources",
                source_lines
                if source_lines is not None
                else sources(hass, mapping or {}),
            ),
            (
                "settings",
                settings_lines
                if settings_lines is not None
                else settings(entry.options),
            ),
            ("own entities", own_entities(hass, entry)),
            ("repairs", repairs(hass, domain, entry, entry_only=entry_issues_only)),
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
