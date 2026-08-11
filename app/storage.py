"""Persist uploaded microphone recordings as OGG/Opus files.

Browsers differ on what MediaRecorder emits: Firefox can produce OGG/Opus
directly, while Chrome/Edge typically only emit WebM/Opus. To always store an
`.ogg` on disk, WebM uploads are transcoded with ffmpeg.
"""

import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from .config import RECORDINGS_DIR


class TranscodeError(RuntimeError):
    """Raised when a non-OGG upload cannot be converted to OGG."""


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _is_ogg(content_type: str | None) -> bool:
    return bool(content_type) and "ogg" in content_type.lower()


def save_recording(data: bytes, content_type: str | None) -> dict:
    """Store the raw upload as `{uuid}.ogg` and return metadata.

    OGG payloads are written straight to disk. Anything else (WebM in practice)
    is transcoded with ffmpeg, copying the Opus stream into an Ogg container.
    """
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

    rec_id = uuid.uuid4().hex
    final_path = RECORDINGS_DIR / f"{rec_id}.ogg"

    if _is_ogg(content_type):
        final_path.write_bytes(data)
        return _metadata(rec_id, final_path)

    if not _ffmpeg_available():
        raise TranscodeError(
            "Upload is not OGG and ffmpeg is not installed to transcode it. "
            "Install ffmpeg or use a browser that records OGG/Opus (e.g. Firefox)."
        )

    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)

    try:
        _transcode_to_ogg(tmp_path, final_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    return _metadata(rec_id, final_path)


def _transcode_to_ogg(src: Path, dst: Path) -> None:
    # Try a fast stream copy first (Opus -> Ogg), then fall back to re-encoding.
    for codec_args in (["-c:a", "copy"], ["-c:a", "libopus"]):
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", str(src), *codec_args, str(dst)],
            capture_output=True,
        )
        if result.returncode == 0 and dst.exists() and dst.stat().st_size > 0:
            return

    dst.unlink(missing_ok=True)
    raise TranscodeError("ffmpeg failed to convert the recording to OGG.")


def _metadata(rec_id: str, path: Path) -> dict:
    return {
        "id": rec_id,
        "filename": path.name,
        "path": str(path),
        "size_bytes": path.stat().st_size,
    }


def write_transcript(rec_id: str, text: str) -> Path:
    """Write the transcript for a recording to `{rec_id}.txt` (UTF-8)."""
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    txt_path = RECORDINGS_DIR / f"{rec_id}.txt"
    txt_path.write_text(text, encoding="utf-8")
    return txt_path


def write_agent_reply(rec_id: str, text: str) -> Path:
    """Write the agent gateway reply for a recording to `{rec_id}.agent.txt`."""
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    reply_path = RECORDINGS_DIR / f"{rec_id}.agent.txt"
    reply_path.write_text(text, encoding="utf-8")
    return reply_path
