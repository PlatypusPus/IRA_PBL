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



def test_image_ocr_straightens_rotated_photos():
    # phone cameras store pixels sideways + an EXIF orientation tag; tesseract
    # reads sideways text as garbage unless the tag is applied first
    import io

    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (340, 100), "white")
    ImageDraw.Draw(img).text(
        (16, 16), "HELLO", fill="black", font=ImageFont.load_default(size=48)
    )
    exif = Image.Exif()
    exif[274] = 6  # Orientation: "rotate 90 CW to display"
    buf = io.BytesIO()
    img.rotate(90, expand=True).save(buf, format="JPEG", exif=exif)
    assert "hello" in image_ocr.extract(buf.getvalue()).lower()


def test_pdf_ocrs_a_scan_that_has_a_stamped_page_number():
    # a real text layer of just "1" must not count as "this page has text"
    import io

    import fitz  # PyMuPDF
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (340, 100), "white")
    ImageDraw.Draw(img).text(
        (16, 16), "HELLO", fill="black", font=ImageFont.load_default(size=48)
    )
    png = io.BytesIO()
    img.save(png, format="PNG")
    doc = fitz.open()
    page = doc.new_page(width=340, height=140)
    page.insert_image(fitz.Rect(0, 0, 340, 100), stream=png.getvalue())
    page.insert_text((160, 130), "1")
    assert "hello" in pdf.extract(doc.tobytes()).lower()


def test_ingest_skips_a_corrupt_file_instead_of_raising(monkeypatch):
    # extractors shell out to tesseract/ffmpeg on arbitrary chat bytes; one bad
    # file must skip, not abort a folder ingest or 500 the webhook
    import contextlib
    from datetime import UTC, datetime

    from wadr.ingestion import router

    @contextlib.contextmanager
    def fake_conn():
        yield object()

    monkeypatch.setattr(router, "get_conn", fake_conn)
    monkeypatch.setattr(router.dedupe, "find_document", lambda conn, h: None)
    corrupt = b"this is not a PNG"  # PIL rejects it; tesseract never sees it
    assert router.ingest(corrupt, "photo.png", "p", "p", datetime.now(UTC)) is None


# ---------------------------------------------------------------- WS3

def test_precision_at_k():
    assert metrics.precision_at_k(["d1", "d2", "d3"], {"d1": 1, "d3": 2}, k=2) == 0.5


def test_recall_at_k():
    assert metrics.recall_at_k(["d1", "d2", "d3"], {"d1": 1, "d3": 2}, k=2) == 0.5


def test_f1_at_k():
    assert metrics.f1_at_k(["d1", "d2", "d3"], {"d1": 1, "d3": 2}, k=2) == 0.5


def test_reciprocal_rank():
    assert metrics.reciprocal_rank(["x", "d1"], {"d1": 1}) == 0.5
    assert metrics.reciprocal_rank(["x", "y"], {"d1": 1}) == 0.0


def test_ndcg_perfect_ranking_is_one():
    assert metrics.ndcg_at_k(["d3", "d1"], {"d3": 2, "d1": 1}, k=2) == pytest.approx(1.0)


def test_ndcg_swapped_ranking_is_below_one():
    assert metrics.ndcg_at_k(["d1", "d3"], {"d3": 2, "d1": 1}, k=2) < 1.0


def test_judgments_loader_parses_jsonl(tmp_path):
    p = tmp_path / "queries.jsonl"
    p.write_text('{"qid": "q01", "query": "biryani", "relevant": {"hash1": 3}}\n')
    (row,) = judgments.load(p)
    assert row["qid"] == "q01" and row["relevant"] == {"hash1": 3}


def test_judgments_loader_rejects_bad_input(tmp_path):
    # these files are hand-graded by several people; a silently dropped or
    # mistyped judgment corrupts every number in the report
    def load(body):
        path = tmp_path / "q.jsonl"
        path.write_text(body, encoding="utf-8")
        return judgments.load(path)

    good = '{"qid": "q01", "query": "a", "relevant": {"h": 3}}\n'
    assert len(load(good)) == 1
    for bad in [
        good + '{"qid": "q01", "query": "b", "relevant": {}}\n',  # duplicate qid
        '{"qid": "q01", "query": "a", "relevant": {"h": 0}}\n',   # grade 0
        '{"qid": "q01", "query": "a", "relevant": {"h": 9}}\n',   # out of range
        '{"qid": "q01", "query": "a", "relevant": {"h": true}}\n',  # bool is not a grade
        '{"qid": "q01", "query": "", "relevant": {}}\n',          # empty query
        '{"qid": "q01", "query": "a"}\n',                         # missing key
        "{oops\n",                                                # not JSON
    ]:
        with pytest.raises(ValueError):
            load(bad)


def test_run_eval_produces_model_table(tmp_path, monkeypatch, capsys):
    # a 2-query fixture, not the real 90-search benchmark: this checks the
    # harness wiring (search -> hash mapping -> metrics -> table), which is the
    # part that breaks. Needs a live DB; dense degrades to empty without Ollama.
    import json

    from wadr.db import get_conn

    with get_conn() as conn:
        hashes = [r[0] for r in conn.execute(
            "SELECT file_hash FROM documents LIMIT 2"
        ).fetchall()]
    if not hashes:
        pytest.skip("no ingested documents to evaluate against")

    path = tmp_path / "queries.jsonl"
    path.write_text(
        "".join(
            json.dumps({"qid": f"q{i:02d}", "query": "exam timetable", "relevant": {h: 3}}) + "\n"
            for i, h in enumerate(hashes, 1)
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(run_eval.sys, "argv", ["run_eval", str(path)])
    run_eval.main()

    out = capsys.readouterr().out
    assert "| model" in out
    for model in run_eval.MODELS:
        assert f"| {model:<7} |" in out


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


def test_similar_returns_neighbors_excluding_itself():
    from wadr.db import get_conn
    from wadr.retrieval import service

    with get_conn() as conn:
        row = conn.execute(
            "SELECT document_id FROM chunks WHERE embedding IS NOT NULL LIMIT 1"
        ).fetchone()
    if row is None:
        pytest.skip("no embedded documents to compare against")
    doc_id = row[0]

    hits = service.similar(doc_id, top_k=3)
    assert all(h.document_id != doc_id for h in hits), "a document is not its own neighbour"
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True), "neighbours must come back ranked"
    with pytest.raises(LookupError):
        service.similar(999_999_999)


def test_feedback_is_logged():
    from wadr.db import get_conn
    from wadr.retrieval import service

    with get_conn() as conn:
        row = conn.execute("SELECT id FROM documents LIMIT 1").fetchone()
    if row is None:
        pytest.skip("no documents to attach feedback to")
    doc_id = row[0]

    feedback_id = service.log_feedback("exam timetable", doc_id, "thumbs_up")
    try:
        with get_conn() as conn:
            stored = conn.execute(
                "SELECT query_text, document_id, action FROM feedback WHERE id = %s",
                (feedback_id,),
            ).fetchone()
        assert stored == ("exam timetable", doc_id, "thumbs_up")
    finally:
        with get_conn() as conn:
            conn.execute("DELETE FROM feedback WHERE id = %s", (feedback_id,))

    # the payload arrives off an HTTP request, so bad input is rejected loudly
    for query_text, document_id, action in [
        ("q", doc_id, "nonsense"),      # unknown action
        ("q", 999_999_999, "opened"),   # unknown document
        ("", doc_id, "opened"),         # empty query
    ]:
        with pytest.raises(ValueError):
            service.log_feedback(query_text, document_id, action)


def test_standing_query_notifies_only_on_a_match():
    from datetime import UTC, datetime

    from wadr.adapters.base import MessagingInterface
    from wadr.db import get_conn

    pushed = []

    class ProbeAdapter(MessagingInterface):
        def send_results(self, chat_id, results):
            pass

        def notify_standing_match(self, chat_id, query_text, filename):
            pushed.append((chat_id, query_text, filename))

    stamp = datetime.now(UTC)
    with get_conn() as conn:
        conn.execute("DELETE FROM standing_queries WHERE chat_id = %s", ("test-probe",))
        conn.execute(
            "INSERT INTO standing_queries (query_text, chat_id) VALUES (%s, %s)",
            ("quantum entanglement", "test-probe"),
        )
    try:
        ProbeAdapter().on_document(
            f"Notes on quantum entanglement and Bell inequalities {stamp}".encode(),
            "probe_physics.txt", "probe", "probe", stamp,
        )
        assert pushed == [("test-probe", "quantum entanglement", "probe_physics.txt")]

        pushed.clear()
        ProbeAdapter().on_document(
            f"A biryani recipe, nothing to do with physics {stamp}".encode(),
            "probe_food.txt", "probe", "probe", stamp,
        )
        assert pushed == [], "an unrelated document must not trigger a saved search"
    finally:
        with get_conn() as conn:
            conn.execute("DELETE FROM standing_queries WHERE chat_id = %s", ("test-probe",))
            conn.execute(
                "DELETE FROM documents WHERE filename IN (%s, %s)",
                ("probe_physics.txt", "probe_food.txt"),
            )


# ---------------------------------------------------------------- SHARED

class _FakeConn:
    """Each classical model issues exactly one execute(), so one canned result
    set stands in for Postgres - these tests are about the IR maths, not SQL."""

    def __init__(self, rows):
        self.rows = rows

    def execute(self, *a, **k):
        return self

    def fetchall(self):
        return self.rows


def test_inverted_index_boolean_and_or_not():
    idx = inverted_index.InvertedIndex()
    idx.add_document(1, "cats and dogs")
    idx.add_document(2, "cats and birds")
    assert idx.query("cats AND dogs") == {1}
    assert idx.query("cats OR dogs") == {1, 2}
    assert idx.query("cats NOT birds") == {1}


def test_inverted_index_merges_match_set_semantics():
    # posting lists are kept sorted so AND/OR/NOT can run as linear merges;
    # those merges must agree with Python's set operations on every input
    import random

    random.seed(0)
    idx = inverted_index.InvertedIndex
    for _ in range(500):
        a = sorted(random.sample(range(30), random.randint(0, 12)))
        b = sorted(random.sample(range(30), random.randint(0, 12)))
        assert idx._intersect(a, b) == sorted(set(a) & set(b))
        assert idx._union(a, b) == sorted(set(a) | set(b))
        assert idx._difference(a, b) == sorted(set(a) - set(b))


def test_inverted_index_operators_are_case_sensitive():
    # uppercase AND is the operator; lowercase "and" is a searchable word
    idx = inverted_index.InvertedIndex()
    idx.add_document(1, "cats and dogs")
    idx.add_document(2, "cats or dogs")
    assert idx.query("and") == {1}


def test_inverted_index_query_terms_use_the_indexer_tokenizer():
    # documents store "tf-idf" as two terms (tf, idf); a query must be split the
    # same way or a hyphenated term silently matches nothing
    idx = inverted_index.InvertedIndex()
    idx.add_document(1, "tf-idf weighting explained")
    idx.add_document(2, "bm25 weighting explained")
    assert idx.query("tf-idf") == {1}
    assert idx.query("tf-idf weighting") == {1}
    assert idx.query("bm25 NOT tf-idf") == {2}


def test_boolean_model_returns_matching_documents():
    conn = _FakeConn([
        (1, "pets.txt", "cats and dogs"),
        (2, "aviary.txt", "cats and birds"),
        (3, "exam.txt", "exam timetable"),
    ])
    hits = boolean_model.search(conn, "cats AND dogs")
    assert [h.filename for h in hits] == ["pets.txt"]
    # Boolean retrieval is set-based: every hit scores the same
    assert {h.score for h in hits} == {1.0}
    assert len(boolean_model.search(conn, "cats NOT birds")) == 1
    assert boolean_model.search(conn, "unicorns") == []


def test_tfidf_ranks_exact_term_match_first():
    conn = _FakeConn([
        (10, 1, "biryani recipe", "recipe.txt"),
        (11, 2, "exam timetable", "exam.txt"),
        (12, 3, "biryani biryani spice", "spice.txt"),
    ])
    hits = tfidf_model.search(conn, "biryani")
    # the chunk mentioning it twice outranks the one mentioning it once, and
    # the chunk that never mentions it is not returned at all
    assert [h.filename for h in hits] == ["spice.txt", "recipe.txt"]
    # hand-computed: tf=1+log10(2), idf=log10(3/2), L2-normalized, cosine
    assert hits[0].score == pytest.approx(0.4329, abs=1e-4)
    assert hits[1].score == pytest.approx(0.3462, abs=1e-4)
    # a term absent from the whole corpus has no direction to compare against
    assert tfidf_model.search(conn, "nonexistentword") == []


def test_tfidf_ignores_a_term_present_in_every_document():
    # df == N -> idf = log10(1) = 0. A term everyone shares cannot discriminate,
    # so it weighs nothing and the query vector has no direction left. That is
    # textbook TF-IDF, not a bug - do not "fix" it by flooring idf.
    conn = _FakeConn([
        (10, 1, "biryani recipe", "recipe.txt"),
        (12, 3, "biryani spice", "spice.txt"),
    ])
    assert tfidf_model.search(conn, "biryani") == []
