# Streckenwacht – Marke & Bilddateien

## Idee

Eine perspektivische Fahrbahn mit gestrichelter Mittellinie, die nach oben in ein leuchtendes Warn-Beacon mit Halo läuft: ein Wachlicht, das über die Strecke wacht. Die Kachelfarbe ist **RAL 5017 Verkehrsblau** – das Blau deutscher Autobahn-Wegweiser, als Bezug zur wichtigsten Datenquelle.

## Farben

| Rolle | Hex | Hinweis |
|---|---|---|
| Kachel, Wortmarke | `#005B8C` | RAL 5017 Verkehrsblau |
| Beacon, Mittellinie | `#F5A623` | Amber-Gold, Signalfarbe |
| Fahrbahn | `#FBF7EE` | warmes Off-White |
| Heller Hintergrund | `#FAF7F2` | README-Header, Social Preview |
| Dunkler Hintergrund | `#14181D` | README-Header (Dark Mode) |
| Tagline hell / dunkel | `#6B6357` / `#B9B2A6` | |

Halo: Amber mit 35 % Deckkraft. Auf dem Blau wirkt er dadurch gedämpft – das ist gewollt, damit das Beacon selbst der hellste Punkt bleibt.

## Schrift

**Space Grotesk** (Google Fonts, SIL Open Font License), Bold 700 für die Wortmarke, Medium 500 für Tagline und Zusatzzeilen. In allen SVGs ist der Text bereits in Pfade umgewandelt – keine installierte Schrift nötig.

## Dateien

### Home Assistant – `custom_components/streckenwacht/brand/`

Wird ab **Home Assistant 2026.3** automatisch aus der Integration geladen. Das zentrale Repo `home-assistant/brands` nimmt seit Februar 2026 keine Custom-Integrationen mehr an.

| Datei | Größe | Inhalt |
|---|---|---|
| `icon.png` / `icon@2x.png` | 256×256 / 512×512 | Icon-Kachel, transparente Ecken |
| `dark_icon.png` / `dark_icon@2x.png` | 256×256 / 512×512 | identisch – die blaue Kachel funktioniert auf beiden Themes |
| `logo.png` / `logo@2x.png` | 587×128 / 1174×256 | Kachel + Wortmarke in Verkehrsblau, für helle Oberflächen |
| `dark_logo.png` / `dark_logo@2x.png` | 587×128 / 1174×256 | Wortmarke in Off-White, für dunkle Oberflächen |

Alle PNGs: transparent, interlaced, verlustfrei komprimiert, randlos beschnitten – entspricht den HA-Vorgaben.

### GitHub – `assets/github/`

| Datei | Größe | Wofür |
|---|---|---|
| `social-preview-1280x640.png` | 1280×640 | Repo → Settings → General → Social preview |
| `org-avatar-500.png`, `org-avatar-1024.png` | quadratisch, vollflächig | Profilbild der Organisation `streckenwacht` |
| `readme-header-light(@2x).png` | 960×220 (1920×440) | README-Kopf, helles Theme |
| `readme-header-dark(@2x).png` | 960×220 (1920×440) | README-Kopf, dunkles Theme (per `<picture>` im README eingebunden) |

### Master & Größenreihe – `assets/brand/`

| Ordner | Inhalt |
|---|---|
| `svg/` | Vektor-Master: `icon.svg`, `icon-mini.svg`, `icon-square-fullbleed.svg`, `mark-on-light.svg`, `mark-on-dark.svg`, `logo-on-light.svg`, `logo-on-dark.svg`, `readme-header-*.svg`, `social-preview.svg` |
| `png/icon/` | Icon-Kachel in 16, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512, 1024, 2048 px |
| `png/mark/` | Nur das Motiv ohne Kachel, transparent, für helle bzw. dunkle Hintergründe, 128–1024 px hoch |
| `png/logo/` | Kachel + Wortmarke, für hell bzw. dunkel, 64–512 px hoch |
| `favicon/` | `favicon.ico` (16/32/48), `favicon.svg`, PNG 16/32/48, `apple-touch-icon-180.png`, `android-chrome-192/512.png` – falls es mal eine Projektseite gibt |

## Regeln

- **≤ 32 px immer die Mini-Variante** (`icon-mini.svg`, bzw. die 16/24/32-px-PNGs – die sind es bereits): ein Mittelstrich, größeres Beacon, kein Halo. Die volle Variante verschwimmt dort.
- Motiv ohne Kachel (`mark-*`): auf hellem Grund die Fahrbahn in Verkehrsblau (`mark-on-light`), auf dunklem in Off-White (`mark-on-dark`). Die Off-White-Fahrbahn verschwindet auf Weiß.
- Farben nicht verändern, Motiv nicht verzerren, keine Schatten oder Verläufe ergänzen.
- Um Logo und Icon mindestens ¼ der Kachelbreite frei lassen.

## Neu erzeugen

Alles entsteht aus Code: `tools/brand/build.mjs` (Anleitung in `tools/brand/README.md`).

## Entstehung

Iteriert im Design-Canvas (für Eingeladene: `https://claude.ai/artifact/VbLtuZGvQcFd54MccfXHXb`). Verworfen: dunkles Navy `#1B2430` (zu schwer), generisches Blau `#3E7CB1` und Petrol `#2E8F82` (beliebig). Gewählt: Verkehrsblau wegen des echten Bezugs zur Autobahn.
