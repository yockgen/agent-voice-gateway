"""Runtime configuration for the voice gateway.

Storage settings drive where recordings and transcripts land. The Whisper
settings configure the phase 2 speech-to-text step. The Hermes placeholders are
declared for a later phase (forwarding transcripts to the Hermes gateway).
"""

import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

RECORDINGS_DIR = Path(
    os.environ.get("VOICEGATEWAY_RECORDINGS_DIR", _PROJECT_ROOT / "recordings")
)

# Cap uploads to avoid accidental huge blobs (25 MB).
MAX_UPLOAD_BYTES = int(os.environ.get("VOICEGATEWAY_MAX_UPLOAD_BYTES", 25 * 1024 * 1024))

# --- Speech-to-text (faster-whisper) ---
# Model size trades accuracy for speed: tiny/base/small/medium/large-v3.
WHISPER_MODEL = os.environ.get("VOICEGATEWAY_WHISPER_MODEL", "small")
WHISPER_DEVICE = os.environ.get("VOICEGATEWAY_WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.environ.get("VOICEGATEWAY_WHISPER_COMPUTE_TYPE", "int8")
WHISPER_BEAM_SIZE = int(os.environ.get("VOICEGATEWAY_WHISPER_BEAM_SIZE", 5))
# Drop silence with the built-in VAD for cleaner transcripts.
WHISPER_VAD = os.environ.get("VOICEGATEWAY_WHISPER_VAD", "1") not in ("0", "false", "False", "")
# Where model weights are downloaded/cached (kept inside the project, gitignored).
WHISPER_DIR = Path(os.environ.get("VOICEGATEWAY_WHISPER_DIR", _PROJECT_ROOT / ".models"))

# --- Hermes gateway forwarding ---
# Transcripts are forwarded to the Hermes OpenAI-compatible gateway when an API
# key is configured. Provide HERMES_API_KEY (or VOICEGATEWAY_HERMES_API_KEY) at
# launch; the key is never stored in the repo.
HERMES_BASE_URL = os.environ.get("HERMES_BASE_URL", "http://127.0.0.1:3001")
HERMES_API_KEY = os.environ.get(
    "HERMES_API_KEY", os.environ.get("VOICEGATEWAY_HERMES_API_KEY", "")
)
HERMES_MODEL = os.environ.get("HERMES_MODEL", "hermes-agent")
HERMES_TIMEOUT = float(os.environ.get("HERMES_TIMEOUT", 120))
# Optional system prompt prepended to each request.
HERMES_SYSTEM_PROMPT = os.environ.get("HERMES_SYSTEM_PROMPT", "")

# Forwarding is active only when a key is present.
HERMES_ENABLED = bool(HERMES_API_KEY)
