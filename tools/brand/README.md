# Brand-Bilder neu erzeugen

Alle Icons, Logos und GitHub-Bilder werden aus `build.mjs` erzeugt (Farben und Proportionen stehen oben im Skript). Nur nötig, wenn sich am Design etwas ändert.

```bash
cd tools/brand
npm install
node build.mjs            # schreibt nach tools/brand/out/assets/
```

Danach die Ergebnisse an ihre Plätze im Repo kopieren:

| Aus `out/assets/` | Nach |
|---|---|
| `home-assistant-brand/*.png` | `custom_components/streckenwacht/brand/` |
| `svg/`, `png/`, `favicon/` | `assets/brand/` |
| `github/*.png` | `assets/github/` |

`favicon.ico` wird nicht vom Skript erzeugt, sondern mit ImageMagick:

```bash
convert favicon/favicon-16.png favicon/favicon-32.png favicon/favicon-48.png favicon/favicon.ico
```

Technische Notiz: Die Wortmarke wird mit opentype.js in Pfade umgewandelt. `font.getPath()` und `Path.toPathData()` von opentype.js 2.0.0 erzeugen bei dieser Schrift für manche Koordinaten `NaN`; das Skript setzt die Buchstaben deshalb selbst und serialisiert die Pfade selbst (`serialize()`). Nicht auf die Bibliotheksfunktionen zurückstellen, ohne die Ausgabe auf `NaN` zu prüfen.
