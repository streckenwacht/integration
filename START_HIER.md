# Start hier

Dieser Ordner wird 1:1 zum Root des Repos `github.com/streckenwacht/integration`. Diese Datei kannst du nach dem Einrichten löschen.

## Was drin ist

| Pfad | Inhalt |
|---|---|
| `CLAUDE.md` | Projektkontext – Claude in VS Code liest ihn automatisch bei jeder Sitzung |
| `docs/HANDOVER.md` | Die vollständige Spezifikation (Datenquellen, Architektur, Entscheidungen, Risiken) |
| `docs/BRAND.md` | Farben, Schrift, alle Bilddateien und wofür sie gedacht sind |
| `README.md` | Entwurf der öffentlichen Projektseite (mit Header-Bild, Datenquellen, Einschränkungen) |
| `LICENSE`, `hacs.json`, `.gitignore` | Repo-Grundausstattung (MIT, HACS-Metadaten) |
| `custom_components/streckenwacht/brand/` | Die 8 Icon/Logo-Dateien, die Home Assistant ab 2026.3 direkt aus der Integration lädt |
| `assets/brand/` | SVG-Master, Icons 16–2048 px, Logos, Motiv ohne Kachel, Favicons |
| `assets/github/` | Social Preview, Org-Avatar, README-Header (hell/dunkel) |
| `tools/fetch_fixtures.py` | Lädt echte Antworten der drei APIs als Testdaten nach `tests/fixtures/` |
| `tools/brand/` | Skript, das alle Bilder neu erzeugt |
| `.vscode/extensions.json` | Empfohlene VS-Code-Erweiterungen |

## Einrichten – Schritt für Schritt

1. **GitHub:** Organisation `streckenwacht` anlegen, darin ein **leeres** öffentliches Repo `integration` (kein README, keine Lizenz, keine .gitignore ankreuzen). Details: `docs/HANDOVER.md`, Abschnitt 9a.
2. **Lokal:** Diesen Ordner an seinen Platz legen, dann im Terminal:
   ```bash
   git init -b main
   git add .
   git commit -m "Projektstart: Spezifikation, Brand-Assets, Repo-Grundausstattung"
   git remote add origin https://github.com/streckenwacht/integration.git
   git push -u origin main
   ```
3. **GitHub-Feinschliff:** Repo → *Settings → General → Social preview*: `assets/github/social-preview-1280x640.png`. Organisation → Profilbild: `assets/github/org-avatar-500.png`. Repo-Topics setzen (Vorschläge in `docs/HANDOVER.md`, Abschnitt 7).
4. **VS Code:** Ordner öffnen, Claude-Erweiterung starten.
5. **Testdaten holen:** `python3 tools/fetch_fixtures.py` (braucht nur Python). Der Stuttgart-Teil muss evtl. angepasst werden – das Skript sagt, was es gefunden hat.

## Erster Auftrag an Claude

Zum Einstieg kannst du so etwas schreiben:

> Lies CLAUDE.md und docs/HANDOVER.md vollständig. Führe dann tools/fetch_fixtures.py aus und vergleiche die echten API-Antworten mit Abschnitt 2 des Handovers; trag Abweichungen dort nach. Danach: Plan für Schritt 1 aus Abschnitt 5 (Grundgerüst) vorlegen, bevor du Code schreibst.

## Noch zu klären, bevor das Repo öffentlich beworben wird

- INRIX-Lizenzfrage bei der Autobahn GmbH (Stau-Daten) – `docs/HANDOVER.md`, Abschnitte 6 und 8
- Impressumspflicht – ebenda, Abschnitt 8
- Name im `LICENSE`-Copyright: steht auf „Streckenwacht contributors"; bei Bedarf durch deinen Namen ersetzen
