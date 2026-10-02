// Builds all Streckenwacht brand assets (SVG masters + PNG exports) into ./out/assets
import fs from 'node:fs';
import path from 'node:path';
import opentype from 'opentype.js';
import sharp from 'sharp';

const OUT = path.resolve('out');
const A = path.join(OUT, 'assets');

// ---------- Brand tokens ----------
const C = {
  blue: '#005B8C',      // RAL 5017 Verkehrsblau
  amber: '#F5A623',     // Beacon / Mittellinie
  road: '#FBF7EE',      // Fahrbahn (warmes Off-White)
  cream: '#FAF7F2',     // heller Hintergrund
  night: '#14181D',     // dunkler Hintergrund
  grey: '#6B6357',      // Tagline hell
  greyDark: '#B9B2A6',  // Tagline dunkel
};

const fontBold = opentype.parse(bufToAB(fs.readFileSync('node_modules/@fontsource/space-grotesk/files/space-grotesk-latin-700-normal.woff')));
const fontMed = opentype.parse(bufToAB(fs.readFileSync('node_modules/@fontsource/space-grotesk/files/space-grotesk-latin-500-normal.woff')));
function bufToAB(b) { return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength); }

// ---------- Mark (viewBox 0 0 100 100) ----------
function mark({ road = C.road, accent = C.amber, halo = true } = {}) {
  return `
    <polygon points="32,82 68,82 56,28 44,28" fill="${road}"/>
    <rect x="48.3" y="65" width="3.4" height="9" fill="${accent}"/>
    <rect x="48.8" y="51" width="2.4" height="7" fill="${accent}"/>
    <rect x="49.2" y="38" width="1.6" height="5" fill="${accent}"/>
    ${halo ? `<circle cx="50" cy="20" r="12" fill="none" stroke="${accent}" stroke-width="2.5" opacity="0.35"/>` : ''}
    <circle cx="50" cy="20" r="7" fill="${accent}"/>`;
}
// Simplified mark for tiny sizes (<= 32 px): one dash, bigger beacon, no halo
function markMini({ road = C.road, accent = C.amber } = {}) {
  return `
    <polygon points="27,90 73,90 57,38 43,38" fill="${road}"/>
    <rect x="47.5" y="58" width="5" height="20" fill="${accent}"/>
    <circle cx="50" cy="21" r="11" fill="${accent}"/>`;
}

// Tile: rounded square, mark at 68.75 % (same proportions as the approved canvas design)
function tileGroup(size, { mini = false, radiusRatio = 72 / 320, fullBleed = false } = {}) {
  const r = fullBleed ? 0 : size * radiusRatio;
  const inner = mini ? size * 0.86 : size * 0.6875;
  const off = (size - inner) / 2;
  const s = inner / 100;
  return `<rect width="${size}" height="${size}" rx="${r}" fill="${C.blue}"/>
    <g transform="translate(${off},${off}) scale(${s})">${mini ? markMini() : mark()}</g>`;
}

function svg(w, h, body, { vbW = w, vbH = h, bg } = {}) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${vbW} ${vbH}">${bg ? `<rect width="${vbW}" height="${vbH}" fill="${bg}"/>` : ''}${body}</svg>`;
}

// ---------- Text as outlined paths ----------
function serialize(cmds) {
  const n = (v) => { if (!Number.isFinite(v)) throw new Error('bad coord ' + v); return (+v.toFixed(3)).toString(); };
  return cmds.map((c) => {
    switch (c.type) {
      case 'M': case 'L': return `${c.type}${n(c.x)} ${n(c.y)}`;
      case 'Q': return `Q${n(c.x1)} ${n(c.y1)} ${n(c.x)} ${n(c.y)}`;
      case 'C': return `C${n(c.x1)} ${n(c.y1)} ${n(c.x2)} ${n(c.y2)} ${n(c.x)} ${n(c.y)}`;
      case 'Z': return 'Z';
      default: throw new Error('unknown cmd ' + c.type);
    }
  }).join('');
}
// Manual glyph-by-glyph layout (opentype.js 2.0 font.getPath() emits NaN for this font)
function textPath(font, text, fontSize) {
  const scale = fontSize / font.unitsPerEm;
  const parts = [];
  const bb = { x1: Infinity, y1: Infinity, x2: -Infinity, y2: -Infinity };
  let x = 0, prev = null;
  for (const ch of text) {
    const g = font.charToGlyph(ch);
    if (prev) { const k = font.getKerningValue(prev, g); if (Number.isFinite(k)) x += k * scale; }
    const gp = g.getPath(x, 0, fontSize);
    const gd = serialize(gp.commands); // own serializer: opentype.js' toPathData() emits NaN for some coordinates
    if (gd) {
      parts.push(gd);
      const b = gp.getBoundingBox();
      bb.x1 = Math.min(bb.x1, b.x1); bb.y1 = Math.min(bb.y1, b.y1);
      bb.x2 = Math.max(bb.x2, b.x2); bb.y2 = Math.max(bb.y2, b.y2);
    }
    x += g.advanceWidth * scale;
    prev = g;
  }
  const d = parts.join(' ');
  if (d.includes('NaN')) throw new Error('NaN in path for ' + text);
  return { d, bb, adv: x };
}
function placedText(font, text, fontSize, x, baselineY, fill) {
  const { d } = textPath(font, text, fontSize);
  return `<path transform="translate(${x},${baselineY})" d="${d}" fill="${fill}"/>`;
}

// ---------- Compositions ----------
// Horizontal logo (tile + wordmark), trimmed, for HA logo.png & general use
function logoSVG(textColor, outH) {
  const T = 140, gap = 36, fs = 64;
  const w = textPath(fontBold, 'Streckenwacht', fs);
  const capTop = w.bb.y1, base = w.bb.y2; // y1 negative (above baseline)
  const textH = base - capTop;
  const baseline = T / 2 + textH / 2 - base; // center glyph bbox on tile center
  const textX = T + gap - w.bb.x1;
  const W = Math.ceil(T + gap + (w.bb.x2 - w.bb.x1) + 2);
  const body = `<g>${tileGroup(T, { radiusRatio: 31 / 140 })}</g>` + placedText(fontBold, 'Streckenwacht', fs, textX, baseline, textColor);
  const scale = outH / T;
  return svg(Math.round(W * scale), outH, body, { vbW: W, vbH: T });
}

// README header banner 960x220 (tile + wordmark + tagline)
function headerSVG({ bg, text, tag }, scale = 1) {
  const W = 960, H = 220, T = 140, pad = 48, gap = 36;
  const wm = textPath(fontBold, 'Streckenwacht', 48);
  const tg = textPath(fontMed, 'wacht über deine Strecke.', 20);
  const wmH = -wm.bb.y1; // cap height above baseline
  const tgH = -tg.bb.y1;
  const lineGap = 16;
  const blockH = wmH + lineGap + tgH + (tg.bb.y2); // include descenders of tagline
  const top = (H - blockH) / 2;
  const x = pad + T + gap;
  const body = `<g transform="translate(${pad},${(H - T) / 2})">${tileGroup(T, { radiusRatio: 31 / 140 })}</g>`
    + placedText(fontBold, 'Streckenwacht', 48, x - wm.bb.x1, top + wmH, text)
    + placedText(fontMed, 'wacht über deine Strecke.', 20, x - tg.bb.x1, top + wmH + lineGap + tgH, tag);
  return svg(W * scale, H * scale, body, { vbW: W, vbH: H, bg });
}

// GitHub social preview 1280x640
function socialSVG() {
  const W = 1280, H = 640, T = 220, gap = 52;
  const wm = textPath(fontBold, 'Streckenwacht', 92);
  const tg = textPath(fontMed, 'wacht über deine Strecke.', 36);
  const sub = textPath(fontMed, 'Home-Assistant-Integration  ·  Autobahn  ·  MobiData BW  ·  Stuttgart', 24);
  const blockW = T + gap + Math.max(wm.bb.x2 - wm.bb.x1, tg.bb.x2 - tg.bb.x1);
  const x0 = (W - blockW) / 2;
  const tileY = 170;
  const wmBase = tileY + 108;
  const tgBase = wmBase + 62;
  const subW = sub.bb.x2 - sub.bb.x1;
  const body = `<g transform="translate(${x0},${tileY})">${tileGroup(T)}</g>`
    + placedText(fontBold, 'Streckenwacht', 92, x0 + T + gap - wm.bb.x1, wmBase, C.blue)
    + placedText(fontMed, 'wacht über deine Strecke.', 36, x0 + T + gap - tg.bb.x1, tgBase, C.grey)
    + `<rect x="${(W - subW) / 2 - 24}" y="496" width="${subW + 48}" height="52" rx="26" fill="${C.blue}" opacity="0.08"/>`
    + placedText(fontMed, 'Home-Assistant-Integration  ·  Autobahn  ·  MobiData BW  ·  Stuttgart', 24, (W - subW) / 2 - sub.bb.x1, 530, C.blue);
  return svg(W, H, body, { bg: C.cream });
}

// ---------- Writers ----------
function write(rel, content) {
  const f = path.join(A, rel);
  fs.mkdirSync(path.dirname(f), { recursive: true });
  fs.writeFileSync(f, content);
}
async function png(svgStr, rel) {
  const f = path.join(A, rel);
  fs.mkdirSync(path.dirname(f), { recursive: true });
  await sharp(Buffer.from(svgStr), { density: 72 }).png({ compressionLevel: 9, progressive: true }).toFile(f);
}

// Size-parametrised icon SVGs
const iconAt = (n, opts = {}) => svg(n, n, tileGroup(100, opts), { vbW: 100, vbH: 100 });
const markTrim = { x: 31, y: 6.5, w: 38, h: 76.5 };
const markSVG = (road, h = 765) => svg(Math.round(h * markTrim.w / markTrim.h), h,
  `<g transform="translate(${-markTrim.x},${-markTrim.y})">${mark({ road })}</g>`, { vbW: markTrim.w, vbH: markTrim.h });

// ---------- Build ----------
fs.rmSync(OUT, { recursive: true, force: true });

// SVG masters
write('svg/icon.svg', iconAt(512));
write('svg/icon-mini.svg', iconAt(512, { mini: true }));
write('svg/icon-square-fullbleed.svg', iconAt(512, { fullBleed: true }));
write('svg/mark-on-light.svg', markSVG(C.blue));
write('svg/mark-on-dark.svg', markSVG(C.road));
write('svg/logo-on-light.svg', logoSVG(C.blue, 280));
write('svg/logo-on-dark.svg', logoSVG(C.road, 280));
write('svg/readme-header-light.svg', headerSVG({ bg: C.cream, text: C.blue, tag: C.grey }));
write('svg/readme-header-dark.svg', headerSVG({ bg: C.night, text: C.road, tag: C.greyDark }));
write('svg/social-preview.svg', socialSVG());

// Home Assistant brand images (custom_components/streckenwacht/brand/)
const HA = 'home-assistant-brand/';
await png(iconAt(256), HA + 'icon.png');
await png(iconAt(512), HA + 'icon@2x.png');
await png(iconAt(256), HA + 'dark_icon.png');
await png(iconAt(512), HA + 'dark_icon@2x.png');
await png(logoSVG(C.blue, 128), HA + 'logo.png');
await png(logoSVG(C.blue, 256), HA + 'logo@2x.png');
await png(logoSVG(C.road, 128), HA + 'dark_logo.png');
await png(logoSVG(C.road, 256), HA + 'dark_logo@2x.png');

// Icon size ladder (mini artwork for <= 32 px)
for (const n of [16, 24, 32]) await png(iconAt(n, { mini: true }), `png/icon/icon-${n}.png`);
for (const n of [48, 64, 96, 128, 192, 256, 384, 512, 1024, 2048]) await png(iconAt(n), `png/icon/icon-${n}.png`);
// Mark only (transparent)
for (const h of [128, 256, 512, 1024]) {
  await png(markSVG(C.blue, h), `png/mark/mark-on-light-${h}h.png`);
  await png(markSVG(C.road, h), `png/mark/mark-on-dark-${h}h.png`);
}
// Logo
for (const h of [64, 128, 256, 512]) {
  await png(logoSVG(C.blue, h), `png/logo/logo-on-light-${h}h.png`);
  await png(logoSVG(C.road, h), `png/logo/logo-on-dark-${h}h.png`);
}

// GitHub
await png(headerSVG({ bg: C.cream, text: C.blue, tag: C.grey }, 1), 'github/readme-header-light.png');
await png(headerSVG({ bg: C.cream, text: C.blue, tag: C.grey }, 2), 'github/readme-header-light@2x.png');
await png(headerSVG({ bg: C.night, text: C.road, tag: C.greyDark }, 1), 'github/readme-header-dark.png');
await png(headerSVG({ bg: C.night, text: C.road, tag: C.greyDark }, 2), 'github/readme-header-dark@2x.png');
await png(socialSVG(), 'github/social-preview-1280x640.png');
await png(iconAt(500, { fullBleed: true }), 'github/org-avatar-500.png');
await png(iconAt(1024, { fullBleed: true }), 'github/org-avatar-1024.png');

// Web / Favicons
for (const n of [16, 32, 48]) await png(iconAt(n, { mini: n <= 32 }), `favicon/favicon-${n}.png`);
await png(iconAt(180, { fullBleed: true }), 'favicon/apple-touch-icon-180.png');
await png(iconAt(192), 'favicon/android-chrome-192.png');
await png(iconAt(512), 'favicon/android-chrome-512.png');
write('favicon/favicon.svg', iconAt(64, { mini: true }));

console.log('done');
