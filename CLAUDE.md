# Streckenwacht – Projektkontext für Claude

Home-Assistant-Custom-Integration (HACS), Domain `streckenwacht`. Zeigt Baustellen, Sperrungen, Staus und Unfälle für vom Nutzer definierte Beobachtungsbereiche – aus drei offenen Datenquellen: **Autobahn-API** (Autobahn GmbH), **MobiData BW** (GeoJSON), **Stadt Stuttgart** (WFS, als GeoJSON abgerufen).

## Die Spezifikation

**`docs/HANDOVER.md` ist die vollständige Spezifikation.** Vor jeder größeren Arbeit lesen. Wichtigste Abschnitte: 2 (Datenquellen) inkl. **2b (verifizierte Abweichungen)**, 3 (Datenmodell), 4 (Architektur), 5 (Reihenfolge + Sicherheitshinweis), 6 (Risiken), 7 (HA/HACS-Standards). Abschnitt 10 listet, was entschieden ist und was bewusst offen bleibt.

Stand: Es gibt noch **keinen Integrationscode**. Vorhanden sind Doku, `README.md`-Entwurf, `LICENSE` (MIT), `hacs.json`, Brand-Bilder und Tools.

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

1. **Feldnamen nie raten.** Fixtures mit `uv run --python 3.13 --no-project tools/fetch_fixtures.py` aktualisieren (auf diesem Windows-Rechner gibt es kein systemweites Python, nur `uv`); die Dateien in `tests/fixtures/` sind die Wahrheit über Formate. Weicht die Live-API von `docs/HANDOVER.md` ab, gilt die API – und die Abweichung wird im Handover nachgetragen.
2. **Entwickelt wird gegen eine produktive Home-Assistant-Instanz.** Provider-Logik (HTTP + Parsing) deshalb erst als reines Python außerhalb von HA testen, bevor die Integration geladen wird. Ein fehlerhafter Provider darf nie die ganze Integration oder HA blockieren: Fehler pro Provider fangen und über die Repairs/Issue-Registry melden.
3. Alle HTTP-Requests mit User-Agent `Streckenwacht/<version> (+https://github.com/streckenwacht/integration)`. Polling konservativ (Default 10–15 min).
4. Stuttgart: per `outputFormat=application/json&srsName=EPSG:4326` abrufen – der Server liefert dann GeoJSON in WGS84, kein `pyproj` nötig. Datumsfelder dort sind Freitext → robust parsen, bei Fehlschlag Event trotzdem behalten. Autobahn-API hat **kein Endfeld** – Ende steht nur in `description` (Details: `docs/HANDOVER.md` 2b).
5. Attribution pro Quelle mitführen (Stuttgart CC BY 4.0, MobiData BW DL-DE-BY-2.0, Autobahn GmbH).
6. Code, Kommentare, Entity-IDs auf Englisch; UI-Texte über `strings.json` + `translations/de.json` und `en.json`.
7. Tests mit `pytest-homeassistant-custom-component`, gegen Fixtures – nicht gegen Live-APIs.
8. **Lokale Umgebung:** Das Repo liegt auf einem Netzlaufwerk (`Z:` → Diskstation). Eine `.venv` dort braucht >10 min. Deshalb jeden `uv`-Befehl mit `UV_PROJECT_ENVIRONMENT=C:/Users/andy/.venvs/streckenwacht` ausführen (in VS-Code-Terminals über `.vscode/settings.json` automatisch gesetzt). Typisch: `uv run pytest`, `uv run ruff check .`, `uv run ruff format .`. Die HA-Testbibliothek (`--group ha-tests`) läuft unter Windows nicht (`fcntl`), nur in GitHub Actions. Ihre Version muss dieselbe `homeassistant`-Version pinnen wie die `dev`-Gruppe.

## Brand-Bilder

Fertig in `custom_components/streckenwacht/brand/` (HA ≥ 2026.3 lädt sie von dort; das zentrale brands-Repo nimmt keine Custom-Integrationen mehr an). Nicht verändern oder neu erzeugen, außer auf ausdrücklichen Wunsch – Details, Farben und Regenerierung in `docs/BRAND.md`.

## Offen / vor öffentlichem Release klären (nicht Aufgabe beim Coden)

INRIX-Lizenzfrage (Stau-Daten der Autobahn-API), Impressumspflicht. Siehe `docs/HANDOVER.md` Abschnitte 6, 8, 10.
