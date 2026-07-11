"""Speech-to-text for WhatsApp voice notes (.ogg/.opus/.m4a). TODO(WS2)."""


def extract(file_bytes: bytes) -> str:
    """Transcribe a voice note to text.

    Intended implementation: openai-whisper (add to pyproject; model size
    "base" is plenty). Whisper wants a file path + ffmpeg, so write bytes to a
    tempfile first. Return the transcript text.
    """
    raise NotImplementedError("TODO(WS2): audio ASR extractor")
