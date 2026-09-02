"""The team's checklist in test form: every stub has a skipped test here.

Delete the skip marker as you implement (TODO.md maps workstreams to tasks).
The imports below are NOT skipped - stubs must always stay importable.
"""

import base64
import json
from datetime import UTC, datetime, timedelta

import pytest

from wadr.adapters import openwa
from wadr.evaluation import judgments, metrics, run_eval
from wadr.indexing import inverted_index
from wadr.ingestion.extractors import audio_asr, docx, image_ocr, pdf
from wadr.retrieval import boolean_model, filters, fusion, tfidf_model

WS2 = pytest.mark.skip(reason="TODO: workstream 2 (extractors)")
WS3 = pytest.mark.skip(reason="TODO: workstream 3 (evaluation)")
WS4 = pytest.mark.skip(reason="TODO: workstream 4 (query experience)")
SHARED = pytest.mark.skip(reason="TODO: shared classical IR (viva-critical)")


# ---------------------------------------------------------------- WS1

def test_openwa_webhook_decodes_and_ingests():
    payload = {
        "chat_id": "123-456@g.us",
        "sender": "+911234567890",
        "timestamp": "2026-07-11T10:00:00+05:30",
        "filename": "note.txt",
        "mime_type": "text/plain",
        "data_base64": base64.b64encode(b"hello whatsapp").decode(),
    }
    resp = openwa.OpenWAAdapter().handle_webhook(payload)
    assert set(resp) == {"document_id", "duplicate"}
    # same bytes again -> a sighting on the same document, not a new one
    again = openwa.OpenWAAdapter().handle_webhook(payload)
    assert again == {"document_id": resp["document_id"], "duplicate": True}


def test_openwa_send_results_posts_to_bridge(monkeypatch):
    calls = []
    monkeypatch.setattr(openwa.urllib.request, "urlopen", lambda req, timeout: calls.append(req))
    openwa.OpenWAAdapter().send_results("123-456@g.us", [])
    (req,) = calls
    assert req.full_url.endswith("/send")
    assert json.loads(req.data) == {"chat_id": "123-456@g.us", "text": "No results."}


# ---------------------------------------------------------------- WS2

def test_docx_extracts_paragraph_text():
    # build a minimal .docx in-test (python-docx) and round-trip it
    import io

    from docx import Document

    d = Document()
    d.add_paragraph("hello from a paragraph")
    d.add_table(rows=1, cols=1).cell(0, 0).text = "table cell text"
    buf = io.BytesIO()
    d.save(buf)
    out = docx.extract(buf.getvalue())
    assert "hello" in out.lower()
    assert "table cell" in out.lower()


def test_image_ocr_reads_printed_text():
    # render "HELLO" onto a Pillow image, OCR it back
    import io

    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (340, 100), "white")
    ImageDraw.Draw(img).text(
        (16, 16), "HELLO", fill="black", font=ImageFont.load_default(size=48)
    )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    assert "hello" in image_ocr.extract(buf.getvalue()).lower()


def _scanned_pdf_bytes(text: str) -> bytes:
    # a one-page PDF whose only "content" is a raster image - no text layer
    import io

    import fitz  # PyMuPDF
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (340, 100), "white")
    ImageDraw.Draw(img).text(
        (16, 16), text, fill="black", font=ImageFont.load_default(size=48)
    )
    png = io.BytesIO()
    img.save(png, format="PNG")

    doc = fitz.open()
    doc.new_page(width=340, height=100)
    doc[0].insert_image(doc[0].rect, stream=png.getvalue())
    return doc.tobytes()


def test_pdf_ocrs_scanned_pages():
    out = pdf.extract(_scanned_pdf_bytes("HELLO"))
    assert "hello" in out.lower()


def test_pdf_keeps_text_layer_untouched():
    import fitz  # PyMuPDF

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "plain text layer")
    out = pdf.extract(doc.tobytes())
    assert "plain text layer" in out
    assert "HELLO" not in out.upper()


def test_audio_asr_transcribes_voice_note():
    # real voice fixture (tests/fixtures/voice.ogg) saying a known phrase
    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures" / "voice.ogg"
    out = audio_asr.extract(fixture.read_bytes()).strip()
    assert "hello" in out.lower()


# ---------------------------------------------------------------- WS3

@WS3
def test_precision_at_k():
    assert metrics.precision_at_k(["d1", "d2", "d3"], {"d1": 1, "d3": 2}, k=2) == 0.5


@WS3
def test_recall_at_k():
    assert metrics.recall_at_k(["d1", "d2", "d3"], {"d1": 1, "d3": 2}, k=2) == 0.5


@WS3
def test_f1_at_k():
    assert metrics.f1_at_k(["d1", "d2", "d3"], {"d1": 1, "d3": 2}, k=2) == 0.5


@WS3
def test_reciprocal_rank():
    assert metrics.reciprocal_rank(["x", "d1"], {"d1": 1}) == 0.5
    assert metrics.reciprocal_rank(["x", "y"], {"d1": 1}) == 0.0


@WS3
def test_ndcg_perfect_ranking_is_one():
    assert metrics.ndcg_at_k(["d3", "d1"], {"d3": 2, "d1": 1}, k=2) == pytest.approx(1.0)


@WS3
def test_ndcg_swapped_ranking_is_below_one():
    assert metrics.ndcg_at_k(["d1", "d3"], {"d3": 2, "d1": 1}, k=2) < 1.0


@WS3
def test_judgments_loader_parses_jsonl(tmp_path):
    p = tmp_path / "queries.jsonl"
    p.write_text('{"qid": "q01", "query": "biryani", "relevant": {"hash1": 3}}\n')
    (row,) = judgments.load(p)
    assert row["qid"] == "q01" and row["relevant"] == {"hash1": 3}


@WS3
def test_run_eval_produces_model_table():
    run_eval.main()  # should print the model x metric markdown table


# ---------------------------------------------------------------- WS4

def test_filters_parse_all_tokens():
    clean, f = filters.parse("invoice from:dad in:family after:2026-01-01 type:pdf")
    assert clean == "invoice"
    assert f.sender == "dad" and f.chat == "family"
    assert str(f.after) == "2026-01-01" and f.doc_type == "pdf"


def test_filters_leave_plain_queries_alone():
    clean, f = filters.parse("exam timetable")
    assert clean == "exam timetable" and f == filters.Filters()


def test_filters_reject_bad_dates():
    with pytest.raises(ValueError):
        filters.parse("notes before:last-tuesday")


def test_recency_boost_prefers_recent_docs():
    now = datetime(2026, 8, 12, tzinfo=UTC)
    fresh, stale = 1, 2
    # stale wins on relevance, but only just; a same-day re-share flips them
    ranked = fusion.recency_boost(
        [(stale, 0.020), (fresh, 0.019)],
        {fresh: now, stale: now - timedelta(days=365)},
        now=now,
    )
    assert [item for item, _ in ranked] == [fresh, stale]
    # unknown ids keep their score exactly, and order is score-descending
    assert fusion.recency_boost([(9, 0.5)], {}, now=now) == [(9, 0.5)]


def test_recency_boost_does_not_overrule_relevance():
    now = datetime(2026, 8, 12, tzinfo=UTC)
    # rank-1 vs rank-30 in RRF is a ~2x gap; a fresh doc must not close that
    ranked = fusion.recency_boost(
        [(1, 1 / 61), (2, 1 / 90)], {2: now}, now=now
    )
    assert [item for item, _ in ranked] == [1, 2]


@WS4
def test_similar_endpoint_returns_neighbors():
    pass  # GET /similar/{id}: pgvector neighbors, excludes the doc itself


@WS4
def test_feedback_is_logged():
    pass  # POST /feedback inserts a row into the feedback table


# ---------------------------------------------------------------- SHARED

@SHARED
def test_inverted_index_boolean_and_or_not():
    idx = inverted_index.InvertedIndex()
    idx.add_document(1, "cats and dogs")
    idx.add_document(2, "cats and birds")
    assert idx.query("cats AND dogs") == {1}
    assert idx.query("cats OR dogs") == {1, 2}
    assert idx.query("cats NOT birds") == {1}


@SHARED
def test_boolean_model_returns_matching_documents():
    boolean_model.search(None, "cats AND dogs")  # needs a DB with ingested docs


@SHARED
def test_tfidf_ranks_exact_term_match_first():
    tfidf_model.search(None, "biryani")  # needs a DB with ingested docs
