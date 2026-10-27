# Streckenwacht – Projektkontext für Claude

Home-Assistant-Custom-Integration (HACS), Domain `streckenwacht`. Zeigt Baustellen, Sperrungen, Staus und Unfälle für vom Nutzer definierte Beobachtungsbereiche – aus offenen Datenquellen: **Autobahn-API** (Autobahn GmbH), **MobiData BW** (GeoJSON), **Stadt Stuttgart** (WFS, als GeoJSON abgerufen), **Norddeutschland** (WFS des LBV.SH: SH, HH, MV, NI), **Berlin** (VIZ), **Brandenburg**, **Sachsen-Anhalt** (WFS), **Sachsen** (ZIP, UTM), **Rheinland-Pfalz** (WFS Mobilitätsatlas), Städte **München**, **Köln**, **Frankfurt**, **Dortmund** (ab 0.2.0), **Aachen**, **Duisburg**, **Münster** (ab 0.3.0), **Luxemburg** (DATEX II), **Karlsruhe**, **Rostock**, **Kiel**, **Ingolstadt** (ab 0.4.0), **Freiburg**, **Landesmeldestelle BW** (Verkehrsmeldungen, DATEX II, ab 0.5.0).

## Dokumentation

- **`docs/ENTWICKLUNG.md`** – Architektur, verifizierte Eigenheiten der Datenquellen, Entscheidungen, Risiken, Release-Ablauf, Backlog. Vor größeren Arbeiten lesen.
- **`docs/DATENQUELLEN.md`** – Planungsgrundlage für neue Datenquellen (Länder, Städte, Endpunkte).
- **`docs/BRAND.md`** – Bilder, Farben, Regenerierung.
- **`CHANGELOG.md`** – Versionsgeschichte und was auf `dev` unveröffentlicht liegt (Abschnitt „Unveröffentlicht“).
- **`NOTES.md`** (lokal, nicht im Repo) – aktueller Arbeitsstand und offene Punkte (wird jede Sitzung fortgeschrieben).

Stand: **`NOTES.md`** (lokal, nicht im Repo: Arbeitsstand, offene Punkte, Beobachtungen) und `CHANGELOG.md` (Versionen, „Unveröffentlicht“). Nach jeder Sitzung `NOTES.md` aktualisieren, nicht diesen Absatz. Interna (Zahlen, Vorlieben, Einschätzungen zu Personen) gehören nur dorthin, nie in eingecheckte Dateien – das Repo ist öffentlich.

## Verbindliche Entscheidungen (nicht neu diskutieren)

- **Eine** Integration mit Provider-Muster (`providers/autobahn.py`, `mobidata_bw.py`, `stuttgart.py`, `norddeutschland.py` auf Basis von `wfs.py`), gemeinsames Datenmodell `StreckenwachtEvent`.
- Ein Config-Entry + **Config-Subentries** je Beobachtungsbereich; **ein Coordinator pro Provider**, Bereiche filtern lokal. Autobahnen wählt der Nutzer aus (die API kann keine Umkreissuche).
- Nur UI-Config-Flow, kein YAML. `DataUpdateCoordinator`, durchgängig async, `async_get_clientsession(hass)`.
- Plattformen: `calendar`, `binary_sensor`, `sensor`, `event`, `geo_location` (Kartenpunkte, seit 0.3.0, auf Wunsch des Projektinhabers). **Keine Webcams.** Deduplizierung zwischen Quellen seit 0.6.0 nur nach den engen Regeln in `docs/ENTWICKLUNG.md` Abschnitt 3 (gleiche Hauptstraße, ≤ 300 m, passender Zeitraum, nur Baustelle/Sperrung; abschaltbar).
- Lizenz MIT. Repo: `github.com/streckenwacht/integration`. `codeowners`: `@n42net`.
- Deployment auf die produktive HA-OS-Instanz über HACS aus GitHub.

## Arbeitsregeln

1. **Feldnamen nie raten.** Fixtures mit `uv run --python 3.13 --no-project tools/fetch_fixtures.py` aktualisieren; die Dateien in `tests/fixtures/` sind die Wahrheit über Formate. Weicht die Live-API von `docs/ENTWICKLUNG.md` ab, gilt die API – und die Abweichung wird dort nachgetragen.
2. **Entwickelt wird gegen eine produktive Home-Assistant-Instanz.** Provider-Logik (HTTP + Parsing) erst als reines Python außerhalb von HA testen. Ein fehlerhafter Provider darf nie die ganze Integration oder HA blockieren: Fehler pro Provider fangen und über die Repairs/Issue-Registry melden.
3. Alle HTTP-Requests mit User-Agent `Streckenwacht/<version> (+https://github.com/streckenwacht/integration)`. Polling konservativ (Default 15 min).
4. Attribution pro Quelle mitführen (Stuttgart CC BY 4.0, MobiData BW DL-DE-BY-2.0, Norddeutschland CC BY 4.0, Berlin/Brandenburg DL-DE-BY-2.0, Sachsen CC BY 4.0, Sachsen-Anhalt nur nichtkommerziell, Rheinland-Pfalz Landesbetrieb Mobilität, München dl-de-by-2.0, Köln/Dortmund dl-de-zero, Frankfurt Stadt Frankfurt, Aachen/Münster dl-de-by-2.0, Duisburg CC BY 3.0 DE, Luxemburg/Rostock CC0, Karlsruhe/Kiel/Ingolstadt CC BY 4.0, Freiburg/LMS BW dl-de-by-2.0, Autobahn GmbH, Verkehrslage INRIX). Abfragen dürfen keine genauen Bereichskoordinaten enthalten (WFS: nur grobes 0,5°-Raster).
5. Code, Kommentare, Entity-IDs auf Englisch; UI-Texte über `strings.json` + `translations/de.json` und `en.json`. Reine Logik (Provider, `model`, `geo`, `summary`, `changes`) ohne HA-Importe, damit sie lokal testbar bleibt.
6. Tests gegen Fixtures, nicht gegen Live-APIs. Logik- und Provider-Tests lokal; HA-Tests (`tests/ha/`, `pytest-homeassistant-custom-component`) nur in GitHub Actions.
7. **Branches:** Entwickelt wird auf `dev`; `main` erhält nur freigegebene Stände (Ablauf unter „Release“), weil die HACS-Installationen daran hängen. Ein Ruleset erzwingt grüne CI (`test`, `hassfest`, `compat`) für `main`. Kein Force-Push, Tags `v*` sind unveränderlich. Ausnahmen (z. B. reine Doku nach `main`) nur nach Rücksprache. Neue Actions müssen unter *Settings → Actions → General* erst erlaubt werden.
8. **Werkzeuge:** `uv run pytest`, `uv run ruff check .`, `uv run ruff format .`. Rechnerspezifisches (z. B. Pfad der virtuellen Umgebung) steht in `CLAUDE.local.md`; `UV_PROJECT_ENVIRONMENT` setzt `.claude/settings.local.json` (beide nicht im Repo). Die HA-Testbibliothek (`--group ha-tests`) läuft unter Windows nicht (`fcntl`). Ihre Version muss dieselbe `homeassistant`-Version pinnen wie die `dev`-Gruppe.
9. **Live-Check außerhalb von HA:** `uv run tools/live_check.py --lat 48.7758 --lon 9.1829 --radius 15 --roads A8 A81`; alle Quellen auf einmal: `uv run tools/source_check.py`. Unter Windows findet `aiodns` (kommt mit HA) keine DNS-Server – lokale Live-Skripte brauchen `aiohttp.ThreadedResolver()` (im Skript bereits drin).
10. **Warnungs-Fixtures (echte INRIX-Daten) nur lokal, nie committen.**

## Release

Gleicher Ablauf in allen Schwesterprojekten (Eilwacht, Einspeisewacht, Streckenwacht, Tarifwacht). Neue Erkenntnisse zum Ablauf hier eintragen und für die Schwestern melden.

1. Version in `manifest.json`, `const.py` und `pyproject.toml` anheben, `uv lock`; `tests/test_manifest.py` prüft die Gleichheit. „Unveröffentlicht“ in `CHANGELOG.md` zur Version machen.
2. `dev` pushen und auf den CI-Lauf **genau dieses Commits** warten (`gh run list --commit <sha>`): Push-CI startet manchmal Minuten verspätet, ein älterer grüner Lauf täuscht.
3. `main` vorspulen mit `git push origin dev:main` – **ohne Branch-Wechsel** im Arbeitsverzeichnis (auf dem Netzlaufwerk hat `git switch` schon Dateien verloren, ein Release entstand so auf altem Stand). Danach prüfen, dass `origin/main` auf dem Versions-Commit steht.
4. `gh release create vX --target main --latest --notes-file …` (Text aus dem Changelog). Ziel `main`, kein Kurz-SHA (gibt 422). Immer ein **reguläres** Release, auch für Betas, nie `--prerelease`: Sonst nimmt HACS den letzten Commit und sucht dort vergeblich die ZIP. Blockiert der Auto-Modus das Veröffentlichen: Befehl nennen, der Inhaber führt ihn aus – nie umgehen.
5. Workflow „Release-ZIP“ prüfen: `streckenwacht.zip` muss am Release hängen. Der Workflow bricht ab, wenn Tag und `manifest.json` nicht passen; fehlt die ZIP, ihn per Hand mit dem Tag starten. Ohne ZIP scheitern HACS-Installationen.
6. Prüfen, dass HACS die neue Version sieht: `gh api repos/streckenwacht/integration/releases --jq '.[0].tag_name'` muss das neue Tag sein – HACS nimmt den **ersten** Eintrag dieser Liste, nicht „Latest“. GitHub sortiert sie offenbar nach der Basisversion; innerhalb derselben Basis (`0.1.0b1` … `0.1.0b10`, `0.1.0`) ist die Reihenfolge willkürlich (Tarifwacht 2026-10-27: b10 und 0.1.0 landeten hinter b6, HACS bot keine von beiden an). **Regel:** Nach Vorabversionen die nächste Version mit **höherer Basis** veröffentlichen (`0.1.1` statt `0.1.0` nach `0.1.0b…`), und Vorabnummern zweistellig gar nicht erst erreichen.
7. Bricht eine Sitzung mitten im Release ab: erst den Stand prüfen (`git log origin/dev origin/main`, CI des Commits, `gh release list`), dann weitermachen.

„Unveränderliche Releases“ bleibt in GitHub aus, weil der Workflow die ZIP erst nach dem Veröffentlichen anhängt; die Tags `v*` schützt das Ruleset.

## Fallstricke und Konventionen (dauerhaft)

- **Schreiblast klein halten** (viele laufen HA auf SD-Karten): `.storage` nur gedrosselt schreiben (`known_events.py`: höchstens stündlich, erste Änderung plant, `async_flush()` beim Entladen – nie `async_delay_save()` bei jeder Änderung neu aufrufen, das verschiebt den Schreibvorgang endlos). Große oder oft wechselnde Attribute gehören in `_unrecorded_attributes`.
- **Kartenkarte** wird als Dashboard-Ressource angemeldet (`frontend_resource.py`), nicht per `add_extra_js_url` (nur Rückfall bei YAML-Ressourcen) – sonst „Custom element not found“ nach HA-Neustarts. Das JS definiert das Element nur einmal.
- **Fremde Pull Requests** gehen gegen `dev`: CI-Läufe aus Forks muss der Inhaber im PR freigeben („Approve and run workflows“), Mergen und Issue-Schließen ebenfalls im Browser (der Auto-Modus von Claude Code blockiert das). „Schließt #N“ greift nur bei `main` – Issue nach dem Release von Hand schließen. Durchsicht mit Befund-Tabelle, dann Dank im PR.
- **GitHub Actions:** Pfadfilter gelten nicht für Tags (Push-Trigger deshalb auf `branches`); zeitgesteuerte Läufe können sich um Stunden verspäten. Dependabot-Warnungen stammen aus `uv.lock` (Entwicklungsumgebung): `homeassistant` und `pytest-homeassistant-custom-component` gemeinsam anheben.
- **Öffentliche Texte** (Forum, Release-Notes, Issues) auf Deutsch, Release-Notes nutzerorientiert mit „Neu/Verbessert/Behoben/Intern“; Posten in Foren macht der Inhaber selbst.

## Brand-Bilder

Fertig in `custom_components/streckenwacht/brand/` (HA ≥ 2026.3 lädt sie von dort). Nicht verändern oder neu erzeugen, außer auf ausdrücklichen Wunsch – Details in `docs/BRAND.md`.

## Zurückgestellt

Impressumspflicht und Anfrage bei der Autobahn GmbH zu INRIX sind **auf Wunsch zurückgestellt** (2026-10-02) – nicht von sich aus erneut vorschlagen, erst beim breiteren öffentlichen Bewerben wieder aufgreifen. Die INRIX-Frage selbst ist entschieden (`docs/ENTWICKLUNG.md` Abschnitt 4).
