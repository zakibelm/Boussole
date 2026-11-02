"""Extraction d'un PDF et découpage par section, avec section et pages."""

import hashlib
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from boussole.platform.memory_rag.port import Chunk

WINDOW_CHARS = 1500
OVERLAP_CHARS = 200
_NUMBERED_TITLE = re.compile(r"^(?P<num>(?:\d+|[A-Z]\d*)(?:\.\d+){0,3})\.?\s+(?P<title>\S.{2,80})$")


@dataclass(frozen=True)
class Section:
    number: str
    title: str
    page: int  # première page, numérotée à partir de 1


@dataclass(frozen=True)
class Page:
    number: int
    text: str


def read_pages(pdf: Path) -> list[Page]:
    reader = PdfReader(pdf)
    return [Page(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]


def outline_sections(pdf: Path) -> list[Section]:
    """Sections tirées des signets du PDF, triées par page."""
    reader = PdfReader(pdf)
    sections = [_section(reader, item) for item in _flatten(reader.outline)]
    return sorted((s for s in sections if s), key=lambda s: s.page)


def heading_sections(pages: Iterable[Page]) -> list[Section]:
    """Repli : titres numérotés (« 2.3 Titre ») en début de ligne."""
    found: list[Section] = []
    for page in pages:
        for line in page.text.splitlines():
            match = _NUMBERED_TITLE.match(line.strip())
            if match:
                found.append(Section(match["num"], match["title"].strip(), page.number))
    return found


def chunk_document(pages: list[Page], sections: list[Section], source: str) -> list[Chunk]:
    """Découpe chaque section en fenêtres qui se recouvrent."""
    chunks: list[Chunk] = []
    for section, section_pages in _pages_by_section(pages, sections):
        for text, first, last in _windows(section_pages):
            chunks.append(_chunk(source, section, text, first, last))
    return chunks


def _chunk(source: str, section: Section, text: str, first: int, last: int) -> Chunk:
    key = f"{source}|{section.number}|{first}|{text[:64]}"
    digest = hashlib.sha256(key.encode()).hexdigest()[:24]
    return Chunk(digest, source, section.number, section.title, first, last, text)


def _pages_by_section(
    pages: list[Page], sections: list[Section]
) -> Iterator[tuple[Section, list[Page]]]:
    if not sections:
        yield Section("—", "", 1), pages
        return
    if sections[0].page > 1:
        yield Section("0", "Pages liminaires", 1), [p for p in pages if p.number < sections[0].page]
    for current, following in zip(sections, [*sections[1:], None], strict=True):
        end = following.page if following else len(pages) + 1
        last = max(end, current.page + 1)
        selected = [p for p in pages if current.page <= p.number < last]
        if following and following.page == current.page:
            continue  # sous-section sur la même page : rattachée à la suivante
        yield current, selected


def _windows(pages: list[Page]) -> Iterator[tuple[str, int, int]]:
    """Fenêtres de texte avec la première et la dernière page couvertes."""
    marks: list[tuple[int, int]] = []  # (position de début, numéro de page)
    parts: list[str] = []
    position = 0
    for page in pages:
        cleaned = " ".join(page.text.split())
        if cleaned:
            marks.append((position, page.number))
            parts.append(cleaned)
            position += len(cleaned) + 1
    text = " ".join(parts)
    start = 0
    while start < len(text):
        end = min(start + WINDOW_CHARS, len(text))
        yield text[start:end], _page_at(marks, start), _page_at(marks, end - 1)
        if end == len(text):
            break
        start = end - OVERLAP_CHARS


def _page_at(marks: list[tuple[int, int]], position: int) -> int:
    page = marks[0][1]
    for start, number in marks:
        if start > position:
            break
        page = number
    return page


def _flatten(outline: Any) -> Iterator[Any]:
    for item in outline:
        if isinstance(item, list):
            yield from _flatten(item)
        else:
            yield item


def _section(reader: PdfReader, item: Any) -> Section | None:
    try:
        index = reader.get_destination_page_number(item)
    except (KeyError, TypeError, ValueError):
        return None
    if index is None:
        return None
    page = index + 1
    title = str(item.title).strip()
    match = re.match(r"^((?:\d+|[A-Z]\d*)(?:\.\d+)*)\.?\s+(.*)$", title)
    number, label = (match[1], match[2]) if match else (title[:40], title)
    return Section(number, label, page)
