"""Rendu Markdown minimal des réponses d'agents : titres, gras, listes et tableaux.

Le texte est d'abord échappé en entier; seules les balises produites ici sont du
HTML. Une réponse de modèle ne peut donc jamais injecter de balise ni de script.
"""

import re

from markupsafe import Markup, escape

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_HEADING = re.compile(r"^#{1,6}\s+(.*)$")
_BULLET = re.compile(r"^\s*[-*]\s+(.*)$")
_NUMBERED = re.compile(r"^\s*\d+[.)]\s+(.*)$")
_TABLE_RULE = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?$")


def render(text: str) -> Markup:
    blocks: list[str] = []
    lines = str(escape(text)).splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
        elif line.startswith("```"):
            i = _code(lines, i, blocks)
        elif heading := _HEADING.match(line):
            blocks.append(f"<h4>{_inline(heading.group(1))}</h4>")
            i += 1
        elif line.startswith("|"):
            i = _table(lines, i, blocks)
        elif _BULLET.match(line) or _NUMBERED.match(line):
            i = _list(lines, i, blocks)
        else:
            i = _paragraph(lines, i, blocks)
    return Markup("\n".join(blocks))  # noqa: S704 (texte échappé ci-dessus)


def _code(lines: list[str], i: int, blocks: list[str]) -> int:
    """Bloc de code : rendu tel quel (déjà échappé), sans autre mise en forme."""
    body: list[str] = []
    i += 1
    while i < len(lines) and not lines[i].strip().startswith("```"):
        body.append(lines[i])
        i += 1
    blocks.append(f'<pre class="code">{chr(10).join(body)}</pre>')
    return i + 1


def _inline(text: str) -> str:
    return _BOLD.sub(r"<strong>\1</strong>", text)


def _table(lines: list[str], i: int, blocks: list[str]) -> int:
    rows: list[list[str]] = []
    while i < len(lines) and lines[i].strip().startswith("|"):
        line = lines[i].strip()
        if not _TABLE_RULE.match(line):
            rows.append([_inline(c.strip()) for c in line.strip("|").split("|")])
        i += 1
    if rows:
        head = "".join(f"<th>{c}</th>" for c in rows[0])
        body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows[1:])
        blocks.append(
            f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead>'
            f"<tbody>{body}</tbody></table></div>"
        )
    return i


def _list(lines: list[str], i: int, blocks: list[str]) -> int:
    tag = "ol" if _NUMBERED.match(lines[i].strip()) else "ul"
    items: list[str] = []
    while i < len(lines) and (match := _BULLET.match(lines[i]) or _NUMBERED.match(lines[i])):
        items.append(f"<li>{_inline(match.group(1))}</li>")
        i += 1
    blocks.append(f"<{tag}>{''.join(items)}</{tag}>")
    return i


def _paragraph(lines: list[str], i: int, blocks: list[str]) -> int:
    parts: list[str] = []
    while i < len(lines) and lines[i].strip() and not _starts_block(lines[i].strip()):
        parts.append(_inline(lines[i].strip()))
        i += 1
    blocks.append(f"<p>{'<br>'.join(parts)}</p>")
    return i


def _starts_block(line: str) -> bool:
    return bool(
        _HEADING.match(line)
        or line.startswith(("|", "```"))
        or _BULLET.match(line)
        or _NUMBERED.match(line)
    )
