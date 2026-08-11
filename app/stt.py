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
    WHISPER_MODEL,
    WHISPER_VAD,
)

_model = None
_model_lock = threading.Lock()
_infer_lock = threading.Lock()


class TranscriptionError(RuntimeError):
    """Raised when audio cannot be transcribed."""


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


def transcribe_file(path: Path) -> dict:
    """Transcribe an audio file, auto-detecting the spoken language.

    Returns ``{"text", "language", "duration"}``. Raises TranscriptionError on
    failure so the caller can keep the saved audio and report the problem.
    """
    model = _get_model()
    try:
        with _infer_lock:
            segments, info = model.transcribe(
                str(path),
                language=None,
                task="transcribe",
                beam_size=WHISPER_BEAM_SIZE,
                vad_filter=WHISPER_VAD,
            )
            text = "".join(segment.text for segment in segments).strip()
    except Exception as exc:
        raise TranscriptionError(f"Transcription failed: {exc}") from exc

    return {
        "text": text,
        "language": getattr(info, "language", None),
        "duration": getattr(info, "duration", None),
    }
