from wadr.ingestion.chunker import chunk


def test_empty_text_gives_no_chunks():
    assert chunk("") == []
    assert chunk("   \n ") == []


def test_short_text_is_one_chunk():
    assert chunk("hello world", size=100, overlap=10) == ["hello world"]


def test_long_text_respects_size_and_keeps_every_word():
    words = [f"w{i:03d}x" for i in range(500)]  # unique, no word is a prefix of another
    text = " ".join(words)
    chunks = chunk(text, size=100, overlap=20)
    assert len(chunks) > 1
    assert all(len(c) <= 100 for c in chunks)
    for w in words:
        assert any(w in c for c in chunks), f"lost word {w}"


def test_consecutive_chunks_overlap():
    text = " ".join(f"w{i:03d}" for i in range(200))
    chunks = chunk(text, size=80, overlap=30)
    for a, b in zip(chunks, chunks[1:], strict=False):
        assert b[:10] in a, "next chunk should start inside the previous one"


def test_giant_unbroken_token_is_hard_cut():
    chunks = chunk("x" * 250, size=100, overlap=10)
    assert all(len(c) <= 100 for c in chunks)
    assert sum(len(c) for c in chunks) >= 250  # nothing lost (overlap may duplicate)
