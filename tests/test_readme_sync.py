"""README.md (German) and README.en.md (English) must tell the same.

Copy of waermewacht/tests/test_readme_sync.py (as of
d8c3da5). Do not change here; make changes there and copy them here
(tools/check_shared.py in the parent folder reports differences).

Both files are split at their headings into sections. Section by section the
heading level, the number of table rows, list items and code blocks, the
inline code, the images and the links must match; text is free. Every
internal link (``#anchor``) must point to a heading or an ``<a id>`` in the
same file. Deliberate differences go into ``tests/readme_sync_allow.json``:
``{"replace": {"mein_handy": "my_phone"}, "code": [...], "links": [...]}``.
``replace`` turns German spellings into English ones in the German code and
links before comparing; ``code`` and ``links`` are left out on both sides.

Stops a feature from landing in only one language (found 2026-11-16: the
English README of Wärmewacht had missed several releases).
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DE = ROOT / "README.md"
EN = ROOT / "README.en.md"
ALLOW = Path(__file__).resolve().parent / "readme_sync_allow.json"

HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
CODE_SPAN = re.compile(r"(`+)(.+?)\1")
LINK = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
HTML_SRC = re.compile(r"""\b(?:src|srcset|href)=["']([^"']+)["']""")
ANCHOR_ID = re.compile(r"""<a\s+(?:name|id)=["']([^"']+)["']""")


@dataclass
class Section:
    """One heading and the lines below it, up to the next heading."""

    title: str
    level: int
    line: int
    table_rows: int = 0
    list_items: int = 0
    code_blocks: int = 0
    code: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)


def _allow() -> tuple[dict[str, str], set[str], set[str]]:
    if not ALLOW.exists():
        return {}, set(), set()
    data = json.loads(ALLOW.read_text(encoding="utf-8"))
    return (
        dict(data.get("replace", {})),
        set(data.get("code", [])),
        set(data.get("links", [])),
    )


def _translate(value: str, replace: dict[str, str]) -> str:
    for german, english in replace.items():
        value = value.replace(german, english)
    return value


def _normalise_link(target: str) -> str | None:
    """Map a link to what both languages share; None for internal anchors."""
    if target.startswith("#"):
        return None
    target = re.sub(r"README(\.en)?\.md", "README.md", target)
    target = re.sub(r"([?&])lang=(de|en)\b", r"\1lang=", target)
    return target


def _strip_code(line: str) -> str:
    return CODE_SPAN.sub(" ", line)


def parse(path: Path) -> list[Section]:
    """Split a README into sections (the part before the first heading is one)."""
    sections = [Section(title="(top)", level=0, line=1)]
    fence: str | None = None
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        section = sections[-1]
        if fence:
            if stripped.startswith(fence):
                fence = None
            continue
        if stripped.startswith(("```", "~~~")):
            fence = stripped[:3]
            section.code_blocks += 1
            continue
        heading = HEADING.match(line)
        if heading:
            sections.append(
                Section(
                    title=heading.group(2), level=len(heading.group(1)), line=number
                )
            )
            continue
        if stripped.startswith("|") and not re.fullmatch(r"\|?[\s:|-]+\|?", stripped):
            section.table_rows += 1
        elif LIST_ITEM.match(line):
            section.list_items += 1
        section.code += [m.group(2).strip() for m in CODE_SPAN.finditer(line)]
        plain = _strip_code(line)
        for target in LINK.findall(plain) + HTML_SRC.findall(plain):
            for part in target.split(","):
                normal = _normalise_link(part.strip().split(" ")[0])
                if normal:
                    section.links.append(normal)
    return sections


def slug(title: str) -> str:
    """GitHub's heading anchor: lower case, punctuation dropped, spaces to '-'."""
    text = re.sub(r"<[^>]+>", "", title)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.replace("`", "").lower()
    kept = []
    for char in text:
        category = unicodedata.category(char)
        if char in "-_" or category[0] in "LNM":
            kept.append(char)
        elif char == " ":
            kept.append("-")
    return "".join(kept)


def anchors(path: Path) -> set[str]:
    """All anchors a link inside the file can point to."""
    found: set[str] = set()
    counts: dict[str, int] = {}
    fence = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(("```", "~~~")):
            fence = not fence
            continue
        if fence:
            continue
        heading = HEADING.match(line)
        if heading:
            base = slug(heading.group(2))
            n = counts.get(base, 0)
            counts[base] = n + 1
            found.add(base if n == 0 else f"{base}-{n}")
        found.update(ANCHOR_ID.findall(line))
    return found


def internal_links(path: Path) -> list[tuple[int, str]]:
    result = []
    fence = False
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip().startswith(("```", "~~~")):
            fence = not fence
            continue
        if fence:
            continue
        for target in LINK.findall(_strip_code(line)):
            if target.startswith("#"):
                result.append((number, target[1:]))
    return result


def _differences(de: list[Section], en: list[Section]) -> list[str]:
    replace, allow_code, allow_links = _allow()
    problems = []
    if [s.level for s in de] != [s.level for s in en]:
        de_titles = [f"{'#' * s.level} {s.title}" for s in de[1:]]
        en_titles = [f"{'#' * s.level} {s.title}" for s in en[1:]]
        for index, (d, e) in enumerate(zip(de_titles, en_titles, strict=False)):
            if d.split(" ")[0] != e.split(" ")[0]:
                problems.append(f"headings differ from #{index + 1}: {d!r} / {e!r}")
                break
        else:
            problems.append(
                f"{len(de_titles)} headings in README.md, {len(en_titles)} in README.en.md"
            )
        return problems
    for d, e in zip(de, en, strict=True):
        where = f"README.md:{d.line} {d.title!r} / README.en.md:{e.line} {e.title!r}"
        for name in ("table_rows", "list_items", "code_blocks"):
            if getattr(d, name) != getattr(e, name):
                problems.append(
                    f"{where}: {name} {getattr(d, name)} / {getattr(e, name)}"
                )
        code_de = sorted(_translate(c, replace) for c in d.code if c not in allow_code)
        code_en = sorted(c for c in e.code if c not in allow_code)
        if code_de != code_en:
            only_de = sorted(set(code_de) - set(code_en)) or "(count)"
            only_en = sorted(set(code_en) - set(code_de)) or "(count)"
            problems.append(f"{where}: code only de {only_de}, only en {only_en}")
        links_de = sorted(
            _translate(x, replace) for x in d.links if x not in allow_links
        )
        links_en = sorted(x for x in e.links if x not in allow_links)
        if links_de != links_en:
            only_de = sorted(set(links_de) - set(links_en)) or "(count)"
            only_en = sorted(set(links_en) - set(links_de)) or "(count)"
            problems.append(f"{where}: links only de {only_de}, only en {only_en}")
    return problems


@pytest.mark.skipif(not EN.exists(), reason="no English README")
def test_readme_languages_match() -> None:
    problems = _differences(parse(DE), parse(EN))
    assert not problems, "README.md and README.en.md differ:\n" + "\n".join(problems)


@pytest.mark.parametrize("path", [DE, EN], ids=["de", "en"])
def test_readme_internal_links_resolve(path: Path) -> None:
    if not path.exists():
        pytest.skip("no such README")
    known = anchors(path)
    broken = [
        f"{path.name}:{n} #{a}" for n, a in internal_links(path) if a not in known
    ]
    assert not broken, "links to missing anchors:\n" + "\n".join(broken)
