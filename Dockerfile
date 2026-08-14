# ── Build stage ──────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build deps and ffmpeg (required by faster-whisper)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# ffmpeg must be present at runtime for audio transcoding
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY app/ ./app/
COPY static/ ./static/

# Recordings and model weights are kept on volumes; create the default dirs
RUN mkdir -p /data/recordings /data/models

ENV VOICEGATEWAY_RECORDINGS_DIR=/data/recordings \
    VOICEGATEWAY_WHISPER_DIR=/data/models \
    VOICEGATEWAY_WHISPER_MODEL=small \
    VOICEGATEWAY_WHISPER_DEVICE=cpu \
    VOICEGATEWAY_WHISPER_COMPUTE_TYPE=int8

EXPOSE 8095

# Use exec form so SIGTERM reaches uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8095"]
