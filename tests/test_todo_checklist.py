"""The team's checklist in test form: every stub has a skipped test here.

Delete the skip marker as you implement (TODO.md maps workstreams to tasks).
The imports below are NOT skipped - stubs must always stay importable.
"""

import base64

import pytest

from wadr.adapters import openwa
from wadr.evaluation import judgments, metrics, run_eval
from wadr.indexing import inverted_index
from wadr.ingestion.extractors import audio_asr, docx, image_ocr
from wadr.retrieval import boolean_model, filters, fusion, tfidf_model

WS1 = pytest.mark.skip(reason="TODO: workstream 1 (WhatsApp integration)")
WS2 = pytest.mark.skip(reason="TODO: workstream 2 (extractors)")
WS3 = pytest.mark.skip(reason="TODO: workstream 3 (evaluation)")
WS4 = pytest.mark.skip(reason="TODO: workstream 4 (query experience)")
SHARED = pytest.mark.skip(reason="TODO: shared classical IR (viva-critical)")


# ---------------------------------------------------------------- WS1

@WS1
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


@WS1
def test_openwa_send_results_posts_to_bridge():
    # mock urllib/httpx: expect POST {chat_id, text} to WADR_OPENWA_BRIDGE_URL/send
    openwa.OpenWAAdapter().send_results("123-456@g.us", [])


# ---------------------------------------------------------------- WS2

@WS2
def test_docx_extracts_paragraph_text():
    # build a minimal .docx in-test (python-docx) and round-trip it
    assert "hello" in docx.extract(b"...").lower()


@WS2
def test_image_ocr_reads_printed_text():
    # render "HELLO" onto a Pillow image, OCR it back
    assert "hello" in image_ocr.extract(b"...").lower()


@WS2
def test_audio_asr_transcribes_voice_note():
    # tiny fixture .ogg saying a known word
    assert audio_asr.extract(b"...").strip() != ""


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

@WS4
def test_filters_parse_all_tokens():
    clean, f = filters.parse("invoice from:dad in:family after:2026-01-01 type:pdf")
    assert clean == "invoice"
    assert f.sender == "dad" and f.chat == "family"
    assert str(f.after) == "2026-01-01" and f.doc_type == "pdf"


@WS4
def test_filters_leave_plain_queries_alone():
    clean, f = filters.parse("exam timetable")
    assert clean == "exam timetable" and f == filters.Filters()


@WS4
def test_recency_boost_prefers_recent_docs():
    fusion.recency_boost([], {})  # newest sighting should lift a doc's fused score


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
