"""Speech-to-text for WhatsApp voice notes (.ogg/.opus/.m4a) via faster-whisper.

faster-whisper runs the same OpenAI Whisper "base" model through CTranslate2:
a fraction of openai-whisper's install size (no torch) and much faster on CPU.
The model is downloaded from HuggingFace on first use (~150 MB, cached under
~/.cache/huggingface). Needs ffmpeg on the system to demux the audio - see
the README.
"""

import io

from faster_whisper import WhisperModel

MODEL_SIZE = "base"

_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    """Load the model once per process; later calls reuse it."""
    global _model
    if _model is None:
        # int8 on CPU: ~2-4x faster than float32 with negligible accuracy loss.
        _model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    return _model


def extract(file_bytes: bytes) -> str:
    """Transcribe a voice note to text.

    faster-whisper accepts a BinaryIO directly - av/PyAV demuxes the container
    from the bytes, so no tempfile is needed.
    """
    segments, _info = _get_model().transcribe(io.BytesIO(file_bytes))
    return "".join(seg.text for seg in segments).strip()