# Streckenwacht – Projektkontext für Claude

Home-Assistant-Custom-Integration (HACS), Domain `streckenwacht`. Zeigt Baustellen, Sperrungen, Staus und Unfälle für vom Nutzer definierte Beobachtungsbereiche – aus drei offenen Datenquellen: **Autobahn-API** (Autobahn GmbH), **MobiData BW** (GeoJSON), **Stadt Stuttgart** (WFS, als GeoJSON abgerufen).

## Die Spezifikation

**`docs/HANDOVER.md` ist die vollständige Spezifikation.** Vor jeder größeren Arbeit lesen. Wichtigste Abschnitte: 2 (Datenquellen) inkl. **2b (verifizierte Abweichungen)**, 3 (Datenmodell), 4 (Architektur), 5 (Reihenfolge + Sicherheitshinweis), 6 (Risiken), 7 (HA/HACS-Standards). Abschnitt 10 listet, was entschieden ist und was bewusst offen bleibt.

Stand (2026-10-02): v0.1.0b5 veröffentlicht und auf der produktiven Instanz installiert; README mit Screenshots (assets/screenshots/, Kalenderbild auf `dev`). Stau-Kennungen vermessen (2026-10-05, INRIX vergibt oft neue Kennungen) und „neu/beendet“ für Staus geglättet (`changes.py`, Handover 2b). **Nächste Schritte:** (1) Release v0.1.0 (erstes stabiles, HACS zeigt dann Versionsnamen). (2) Entwurf Forenbeitrag. Danach Backlog (Handover Abschnitt 14); für neue Datenquellen ist **`docs/DATENQUELLEN.md`** die Planungsgrundlage.

## Verbindliche Entscheidungen (nicht neu diskutieren)

- **Eine** Integration mit Provider-Muster (`providers/autobahn.py`, `mobidata_bw.py`, `stuttgart.py`), gemeinsames Datenmodell `StreckenwachtEvent`.
- **Alle drei Provider im ersten Release.** Reihenfolge beim Bauen: Grundgerüst → Autobahn → MobiData BW → Stuttgart → Entities → Politur.
- Nur UI-Config-Flow, kein YAML. `DataUpdateCoordinator`, durchgängig async, `async_get_clientsession(hass)`.
- Plattformen: `calendar`, `binary_sensor`, `sensor`, `event`. **Keine Webcams** (Quellen liefern keine öffentlichen Bilder).
- Deduplizierung zwischen Quellen ist **nicht** Teil von v1.
- Lizenz MIT. Repo: `github.com/streckenwacht/integration`. `codeowners`: `@n42net`.
- Ein Config-Entry + **Config-Subentries** je Beobachtungsbereich; **ein Coordinator pro Provider**, Bereiche filtern lokal. Autobahnen wählt der Nutzer aus (die API kann keine Umkreissuche).
- Tests: Provider-Tests lokal (Windows, `uv`), HA-Tests in GitHub Actions. Deployment auf die produktive HA-OS-Instanz über HACS aus GitHub.

## Arbeitsregeln

1. **Feldnamen nie raten.** Fixtures mit `uv run --python 3.13 --no-project tools/fetch_fixtures.py` aktualisieren; die Dateien in `tests/fixtures/` sind die Wahrheit über Formate. Weicht die Live-API von `docs/HANDOVER.md` ab, gilt die API – und die Abweichung wird im Handover nachgetragen.
2. **Entwickelt wird gegen eine produktive Home-Assistant-Instanz.** Provider-Logik (HTTP + Parsing) deshalb erst als reines Python außerhalb von HA testen, bevor die Integration geladen wird. Ein fehlerhafter Provider darf nie die ganze Integration oder HA blockieren: Fehler pro Provider fangen und über die Repairs/Issue-Registry melden.
3. Alle HTTP-Requests mit User-Agent `Streckenwacht/<version> (+https://github.com/streckenwacht/integration)`. Polling konservativ (Default 10–15 min).
4. Stuttgart: per `outputFormat=application/json&srsName=EPSG:4326` abrufen – der Server liefert dann GeoJSON in WGS84, kein `pyproj` nötig. Datumsfelder dort sind Freitext → robust parsen, bei Fehlschlag Event trotzdem behalten. Autobahn-API hat **kein Endfeld** – Ende steht nur in `description` (Details: `docs/HANDOVER.md` 2b).
5. Attribution pro Quelle mitführen (Stuttgart CC BY 4.0, MobiData BW DL-DE-BY-2.0, Autobahn GmbH).
6. Code, Kommentare, Entity-IDs auf Englisch; UI-Texte über `strings.json` + `translations/de.json` und `en.json`.
7. Tests mit `pytest-homeassistant-custom-component`, gegen Fixtures – nicht gegen Live-APIs.
8. **Branches:** Entwickelt wird auf `dev` (CI läuft dort auch). `main` erhält nur freigegebene Stände (Merge von `dev` + Versions-Bump + GitHub-Release). Grund: Die produktive HACS-Installation folgt `main`, jeder Commit dort erscheint als Update.
9. **Werkzeuge:** `uv run pytest`, `uv run ruff check .`, `uv run ruff format .`. Rechnerspezifisches (z. B. Pfad der virtuellen Umgebung) steht in `CLAUDE.local.md` (nicht im Repo). Die HA-Testbibliothek (`--group ha-tests`) läuft unter Windows nicht (`fcntl`), nur in GitHub Actions. Ihre Version muss dieselbe `homeassistant`-Version pinnen wie die `dev`-Gruppe.
10. **Live-Check außerhalb von HA:** `uv run tools/live_check.py --lat 48.7758 --lon 9.1829 --radius 15 --roads A8 A81`. Unter Windows findet `aiodns` (kommt mit HA) keine DNS-Server – lokale Live-Skripte brauchen `aiohttp.ThreadedResolver()` (im Skript bereits drin). Auf HA OS kein Thema.

## Brand-Bilder

Fertig in `custom_components/streckenwacht/brand/` (HA ≥ 2026.3 lädt sie von dort; das zentrale brands-Repo nimmt keine Custom-Integrationen mehr an). Nicht verändern oder neu erzeugen, außer auf ausdrücklichen Wunsch – Details, Farben und Regenerierung in `docs/BRAND.md`.

## Offen / vor öffentlichem Release klären (nicht Aufgabe beim Coden)

Impressumspflicht und Anfrage bei der Autobahn GmbH zu INRIX sind **auf Wunsch zurückgestellt** (2026-10-02) – nicht von sich aus erneut vorschlagen, erst beim öffentlichen Bewerben wieder aufgreifen. Die INRIX-Frage ist recherchiert und entschieden: Option „Staumeldungen (INRIX) einbeziehen“, Standard an; Warnungs-Fixtures (echte INRIX-Daten) nur lokal, nie committen. Siehe `docs/HANDOVER.md` Abschnitte 6, 8, 10.
