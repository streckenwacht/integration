# Mitmachen

Danke, dass du Streckenwacht verbessern willst! Fehler und Ideen bitte als [Issue](https://github.com/streckenwacht/integration/issues/new/choose). Sicherheitslücken bitte vertraulich melden, siehe [SECURITY.md](SECURITY.md).

## Pull Requests

- Kleine Änderungen (Fehlerbehebungen, Übersetzungen, Doku) gern direkt als Pull Request. Neue Funktionen, Datenquellen oder Umbauten bitte erst in einem Issue besprechen, damit niemand umsonst arbeitet.
- **Basis ist `dev`**, nicht `main`. `main` enthält nur veröffentlichte Stände, an denen die HACS-Installationen hängen.
- Vor dem Pull Request: `uv run pytest`, `uv run ruff check .` und `uv run ruff format .`. Die Home-Assistant-Tests (`tests/ha/`) laufen nur in GitHub Actions, unter Windows nicht. Bei Pull Requests aus Forks startet die CI erst, wenn ich sie freigebe.
- Code, Kommentare und Entity-IDs auf Englisch. UI-Texte stehen in `strings.json` und `translations/de.json` + `en.json`, immer in beiden Sprachen.
- `CHANGELOG.md` und Versionsnummer bitte nicht ändern. Den Eintrag und das Release übernehme ich.

## KI-Assistenten

Beiträge mit Hilfe von KI-Assistenten (z. B. Claude Code) sind willkommen, wenn du die Änderung selbst verstanden und getestet hast. Bitte im Pull Request kurz erwähnen; ein `Co-Authored-By`-Trailer im Commit genügt.

[`CLAUDE.md`](CLAUDE.md) und [`docs/ENTWICKLUNG.md`](docs/ENTWICKLUNG.md) enthalten die Projektregeln, die dein Assistent lesen sollte. Release, Veröffentlichen und alles an `main` mache nur ich.

## Besonderheiten von Streckenwacht

- **Neue Datenquelle:** Die Lizenz muss die Nutzung erlauben und wird in der Namensnennung und in der README genannt. Das Format mit einer echten Antwort als Fixture in `tests/fixtures/` belegen, Feldnamen nie raten. Abfragen enthalten keine genauen Koordinaten (WFS: grobes 0,5°-Raster). Eine fehlerhafte Quelle darf die anderen nicht stören. Kandidaten stehen in [`docs/DATENQUELLEN.md`](docs/DATENQUELLEN.md).
- Tests laufen gegen Fixtures, nicht gegen Live-APIs. Echte INRIX-Verkehrsdaten (Staus) bitte nicht als Fixture committen.

## English

Contributions are welcome. Small fixes, translations and docs can go straight to a pull request; for new features, data sources or larger changes please open an issue first. Target the **`dev`** branch, run `uv run pytest` and `uv run ruff check .` before opening the PR, and keep code and comments in English (UI texts in both German and English). AI-assisted contributions are fine if you have reviewed and tested them yourself; please mention it in the PR. Issues and pull requests in English are welcome.
