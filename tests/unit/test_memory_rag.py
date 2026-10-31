"""Mémoire RAG sur un PDF fabriqué pour le test (aucun texte du PMBOK)."""

import logging
import uuid
from pathlib import Path

import pytest
from fpdf import FPDF

from boussole.platform.memory_rag.chunking import chunk_document, heading_sections, read_pages
from boussole.platform.memory_rag.embedders import FakeEmbedder
from boussole.platform.memory_rag.local_store import LocalVectorStore
from boussole.platform.memory_rag.memory import (
    NO_SOURCE,
    OutsideLocalDataError,
    RagMemory,
    format_sources,
)
from boussole.platform.memory_rag.port import Chunk

SECTIONS = [
    ("1 Introduction", "Ce guide présente la boussole des projets et son vocabulaire général."),
    ("2.1 Risques", "Le registre des risques note la probabilité et l'impact de chaque menace."),
    ("2.2 Parties prenantes", "La cartographie des parties prenantes mesure influence et intérêt."),
    ("3 Clôture", "La clôture rassemble les livrables acceptés et les leçons apprises."),
]


def _make_pdf(path: Path, with_outline: bool = True) -> Path:
    pdf = FPDF()
    pdf.set_font("Helvetica", size=11)
    for title, body in SECTIONS:
        pdf.add_page()
        if with_outline:
            pdf.start_section(title, level=title.count("."))
        pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        pdf.multi_cell(0, 8, " ".join([body] * 4))
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(path))
    return path


@pytest.fixture
def local_root(tmp_path: Path) -> Path:
    return tmp_path / "data" / "local"


@pytest.fixture
def memory(local_root: Path) -> RagMemory:
    return RagMemory(FakeEmbedder(), LocalVectorStore(), local_root=local_root)


def test_sections_and_pages_come_from_bookmarks(memory: RagMemory, local_root: Path) -> None:
    report = memory.ingest_pdf(_make_pdf(local_root / "guide.pdf"), "Guide test")
    assert (report.pages, report.sections, report.sections_from) == (4, 4, "signets")
    hit = memory.search("registre des risques probabilité impact", k=1)[0]
    assert hit.chunk.citation() == "Guide test, section 2.1 « Risques », p. 2"


def test_numbered_headings_are_used_without_bookmarks(local_root: Path) -> None:
    pages = read_pages(_make_pdf(local_root / "plain.pdf", with_outline=False))
    sections = heading_sections(pages)
    assert [s.number for s in sections] == ["1", "2.1", "2.2", "3"]
    chunks = chunk_document(pages, sections, "Guide test")
    assert {c.section for c in chunks} == {"1", "2.1", "2.2", "3"}


def test_long_sections_are_split_with_overlap(local_root: Path) -> None:
    pages = read_pages(_make_pdf(local_root / "guide.pdf"))
    long_pages = [type(p)(p.number, p.text * 40) for p in pages[:1]]
    chunks = chunk_document(long_pages, heading_sections(long_pages), "Guide test")
    assert len(chunks) > 1
    assert chunks[0].text[-100:] in chunks[1].text


def test_pdf_outside_local_data_is_refused(memory: RagMemory, tmp_path: Path) -> None:
    with pytest.raises(OutsideLocalDataError):
        memory.ingest_pdf(_make_pdf(tmp_path / "ailleurs.pdf"), "Guide test")


def test_reingesting_replaces_the_source(memory: RagMemory, local_root: Path) -> None:
    pdf = _make_pdf(local_root / "guide.pdf")
    first = memory.ingest_pdf(pdf, "Guide test")
    memory.ingest_pdf(pdf, "Guide test")
    assert memory.search("clôture", k=100).__len__() == first.chunks


def test_logs_never_contain_document_text(
    memory: RagMemory, local_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    memory.ingest_pdf(_make_pdf(local_root / "guide.pdf"), "Guide test")
    memory.search("cartographie des parties prenantes")
    assert caplog.text
    for _, body in SECTIONS:
        assert body[:30] not in caplog.text


def test_format_sources_numbers_citations(memory: RagMemory, local_root: Path) -> None:
    memory.ingest_pdf(_make_pdf(local_root / "guide.pdf"), "Guide test")
    block = format_sources(memory.search("leçons apprises clôture", k=2))
    assert block.startswith("[1] Guide test, section")
    assert "[2]" in block


def test_no_hit_says_there_is_no_source() -> None:
    assert format_sources([]) == NO_SOURCE


def _chunk(chunk_id: str, project: uuid.UUID | None) -> Chunk:
    return Chunk(chunk_id, "Projet", "1", "", 1, 1, "budget du projet", project)


def test_project_chunks_stay_inside_their_project() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    store, embedder = LocalVectorStore(), FakeEmbedder()
    chunks = [_chunk("commun", None), _chunk("a", a), _chunk("b", b)]
    store.add(chunks, embedder.embed_documents([c.text for c in chunks]), embedder.model_name)
    query = embedder.embed_query("budget")
    seen_by_a = {h.chunk.id for h in store.search(query, 10, embedder.model_name, a)}
    seen_without_project = {h.chunk.id for h in store.search(query, 10, embedder.model_name, None)}
    assert seen_by_a == {"commun", "a"}
    assert seen_without_project == {"commun"}


def test_vectors_from_another_model_are_ignored() -> None:
    store, embedder = LocalVectorStore(), FakeEmbedder()
    store.add([_chunk("x", None)], [embedder.embed_query("budget")], "autre/modele")
    assert store.search(embedder.embed_query("budget"), 5, embedder.model_name, None) == []


def test_file_store_survives_a_restart(tmp_path: Path) -> None:
    path, embedder = tmp_path / "index.jsonl", FakeEmbedder()
    project = uuid.uuid4()
    LocalVectorStore(path).add([_chunk("p", project)], [embedder.embed_query("budget")], "m")
    reloaded = LocalVectorStore(path)
    assert reloaded.count() == 1
    assert (
        reloaded.search(embedder.embed_query("budget"), 1, "m", project)[0].chunk.project_id
        == project
    )


def test_mismatched_vectors_are_rejected() -> None:
    with pytest.raises(ValueError, match="Autant"):
        LocalVectorStore().add([_chunk("x", None)], [], "m")
