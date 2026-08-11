# Voice Gateway

A minimal web app to record from the microphone, save each clip as an `.ogg`
(Opus) file on the server, and transcribe it to text with a local
speech-to-text model.

This covers the full voice input -> speech-to-text -> Hermes gateway pipeline:
**phase 1** (record -> OGG), **phase 2** (OGG -> transcript `.txt`), and
**phase 3** (transcript -> Hermes gateway, reply saved and shown).

## Features

- One-button browser recorder (vanilla JS, no frontend build step).
- Uploads are stored as `recordings/{uuid}.ogg`.
- Cross-browser OGG output: Firefox records OGG/Opus directly; Chrome/Edge
  record WebM/Opus, which the server transcodes to OGG with `ffmpeg`.
- Local speech-to-text with [faster-whisper](https://github.com/SYSTRAN/faster-whisper):
  each recording is transcribed (language auto-detected) and the text is saved
  alongside the audio as `recordings/{uuid}.txt` and shown in the browser.
- Transcript forwarding to the Hermes OpenAI-compatible gateway: the reply is
  saved as `recordings/{uuid}.hermes.txt` and shown in the browser. Active only
  when a Hermes API key is configured.

## Requirements

- Python 3.11+
- `ffmpeg` on `PATH` (needed to transcode WebM uploads from Chrome/Edge)
- Python packages in [requirements.txt](requirements.txt): `fastapi`,
  `uvicorn[standard]`, `python-multipart`, `faster-whisper`
- Network access on first run to download the Whisper model (cached afterwards)

## Port

The app runs on **port 8095** by default. This box already uses several ports,
so 8095 was chosen to avoid conflicts:

| Port | Used by |
|------|---------|
| 3000 | pos-backend |
| 3001 | Hermes agent gateway |
| 5432 | pos-postgres |
| 8000 | vLLM (reserved in `deploy.conf`) |
| 8001 | gemma4-e4b vLLM |
| 8002-8006 | reserved for other vLLM models |
| 8080 | in use |
| 8088 | pos-frontend |
| 1883 / 9001 | pos-mqtt |
| **8095** | **voice gateway (this app)** |

## Setup and run

```bash
cd /data/voicegateway

# Recommended: virtualenv (needs the python3-venv package)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --host 0.0.0.0 --port 8095
```

Then open http://localhost:8095, allow the microphone, click **Start
recording**, speak, then **Stop & save**. The audio (`{uuid}.ogg`) and its
transcript (`{uuid}.txt`) appear under `recordings/`, and the transcript is
shown in the page.

> On the first recording, faster-whisper downloads the model (the default
> `small` model is ~460 MB) into `.models/`. This needs outbound network once;
> later runs use the cache. Transcription runs on CPU as part of the upload
> request, so short clips take a few seconds.

> Microphone capture requires a [secure context](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia#security):
> use `http://localhost` in dev, or serve over HTTPS when accessing from
> another machine.

### If `python3-venv` is unavailable (externally managed Python)

Install dependencies into a project-local folder and point `PYTHONPATH` at it:

```bash
cd /data/voicegateway
python3 -m pip install --target=.pylibs -r requirements.txt
PYTHONPATH=.pylibs python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8095
```

## Configuration

Set via environment variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `VOICEGATEWAY_RECORDINGS_DIR` | `./recordings` | Where `.ogg` and `.txt` files are written |
| `VOICEGATEWAY_MAX_UPLOAD_BYTES` | `26214400` (25 MB) | Max accepted upload size |
| `VOICEGATEWAY_WHISPER_MODEL` | `small` | Whisper model size: `tiny`/`base`/`small`/`medium`/`large-v3` |
| `VOICEGATEWAY_WHISPER_DEVICE` | `cpu` | Compute device for faster-whisper |
| `VOICEGATEWAY_WHISPER_COMPUTE_TYPE` | `int8` | CTranslate2 compute type (e.g. `int8`, `float32`) |
| `VOICEGATEWAY_WHISPER_BEAM_SIZE` | `5` | Beam size for decoding |
| `VOICEGATEWAY_WHISPER_VAD` | `1` | Drop silence with voice-activity detection (`0` to disable) |
| `VOICEGATEWAY_WHISPER_DIR` | `./.models` | Model download/cache directory |
| `HERMES_API_KEY` | *(unset)* | Hermes gateway API key. Forwarding is **enabled only when this is set** (alias: `VOICEGATEWAY_HERMES_API_KEY`) |
| `HERMES_BASE_URL` | `http://127.0.0.1:3001` | Hermes gateway base URL |
| `HERMES_MODEL` | `hermes-agent` | Model name sent to the gateway |
| `HERMES_TIMEOUT` | `120` | Per-request timeout (seconds) |
| `HERMES_SYSTEM_PROMPT` | *(unset)* | Optional system prompt prepended to each request |

Enable Hermes forwarding by launching with the key, for example:

```bash
HERMES_API_KEY=your-gateway-key \
  uvicorn app.main:app --host 0.0.0.0 --port 8095
```

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Serves the recorder web page |
| `GET` | `/api/health` | Returns `{"ok": true}` |
| `POST` | `/api/recordings` | `multipart/form-data` with field `audio`; saves the clip, transcribes it, forwards the transcript to Hermes, and returns `{ id, filename, path, size_bytes, transcript, language, transcript_file, stt_error, hermes_reply, hermes_file, hermes_error }` |

Example:

```bash
curl -X POST -F "audio=@clip.ogg;type=audio/ogg" \
  http://localhost:8095/api/recordings
```

Notes:

- If an upload is not OGG and `ffmpeg` is not installed, the server responds
  `503` rather than saving a mislabeled file.
- If transcription fails, the audio is still saved and the response returns
  `200` with `transcript: null` and a populated `stt_error`.
- If Hermes forwarding fails (or no key is configured), the audio and
  transcript are still saved; the response returns `200` with `hermes_reply:
  null` and, on failure, a populated `hermes_error`.

## Project layout

```
voicegateway/
  requirements.txt
  README.md
  app/
    main.py         # FastAPI app: routes + static serving + STT/Hermes wiring
    config.py       # recordings dir, size cap, Whisper + Hermes settings
    storage.py      # uuid naming + ffmpeg WebM -> OGG + transcript/reply writers
    stt.py          # faster-whisper model + transcribe_file()
    hermes_client.py# async send_to_hermes()
  static/
    index.html      # recorder UI + transcript + Hermes reply views
    app.js          # getUserMedia + MediaRecorder + upload + result display
  recordings/       # runtime (gitignored): {uuid}.ogg + {uuid}.txt + {uuid}.hermes.txt
  .models/          # Whisper model cache (gitignored)
```

## Roadmap (later ideas)

- Optional list/playback page for saved recordings, transcripts, and replies.
- Streaming Hermes responses to the browser.
