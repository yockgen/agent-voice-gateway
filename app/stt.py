"""Local speech-to-text with faster-whisper.

A single WhisperModel is lazily loaded on first use and reused across requests.
Inference is serialized with a lock because one CPU model instance is shared by
all callers in this single-user phase.
"""

import threading
from pathlib import Path

from .config import (
    WHISPER_BEAM_SIZE,
    WHISPER_COMPUTE_TYPE,
    WHISPER_DEVICE,
    WHISPER_DIR,
    WHISPER_LANGUAGE,
    WHISPER_LANGUAGE_DETECTION_SEGMENTS,
    WHISPER_LANGUAGE_DETECTION_THRESHOLD,
    WHISPER_MODEL,
    WHISPER_VAD,
)

_model = None
_model_lock = threading.Lock()
_infer_lock = threading.Lock()


class TranscriptionError(RuntimeError):
    """Raised when audio cannot be transcribed."""


def normalize_language_hint(value: str | None) -> str | None:
    """Map client/env hints to an ISO-639-1 code or None for auto-detect."""
    if value is None:
        return None
    cleaned = value.strip().lower()
    if not cleaned or cleaned in ("auto", "detect", "none"):
        return None
    # Common aliases from clients (ISO-639-1 codes pass through unchanged).
    aliases = {
        "english": "en",
        "chinese": "zh",
        "mandarin": "zh",
        "cmn": "zh",
    }
    return aliases.get(cleaned, cleaned)


def resolve_stt_language(request_hint: str | None) -> str | None:
    """Per-request hint overrides the server default; both empty means auto-detect."""
    hint = normalize_language_hint(request_hint)
    if hint is not None:
        return hint
    return WHISPER_LANGUAGE


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                try:
                    from faster_whisper import WhisperModel
                except ImportError as exc:  # pragma: no cover - dependency missing
                    raise TranscriptionError(
                        "faster-whisper is not installed. Add it via requirements.txt."
                    ) from exc
                WHISPER_DIR.mkdir(parents=True, exist_ok=True)
                try:
                    _model = WhisperModel(
                        WHISPER_MODEL,
                        device=WHISPER_DEVICE,
                        compute_type=WHISPER_COMPUTE_TYPE,
                        download_root=str(WHISPER_DIR),
                    )
                except Exception as exc:
                    raise TranscriptionError(
                        f"Failed to load Whisper model '{WHISPER_MODEL}': {exc}"
                    ) from exc
    return _model


def transcribe_file(path: Path, language_hint: str | None = None) -> dict:
    """Transcribe an audio file.

    ``language_hint`` comes from the client (or env default). ``None`` enables
    Whisper auto language detection.

    Returns ``{"text", "language", "language_probability", "duration"}``.
    """
    language = resolve_stt_language(language_hint)
    model = _get_model()
    transcribe_kwargs: dict = {
        "task": "transcribe",
        "beam_size": WHISPER_BEAM_SIZE,
        "vad_filter": WHISPER_VAD,
        "language": language,
    }
    if language is None:
        transcribe_kwargs["language_detection_threshold"] = (
            WHISPER_LANGUAGE_DETECTION_THRESHOLD
        )
        transcribe_kwargs["language_detection_segments"] = (
            WHISPER_LANGUAGE_DETECTION_SEGMENTS
        )

    try:
        with _infer_lock:
            segments, info = model.transcribe(str(path), **transcribe_kwargs)
            text = "".join(segment.text for segment in segments).strip()
    except Exception as exc:
        raise TranscriptionError(f"Transcription failed: {exc}") from exc

    return {
        "text": text,
        "language": getattr(info, "language", None),
        "language_probability": getattr(info, "language_probability", None),
        "duration": getattr(info, "duration", None),
    }
