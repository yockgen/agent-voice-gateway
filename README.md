# Voice Gateway

A minimal web app to record from the microphone, save each clip as an `.ogg`
(Opus) file on the server, transcribe it to text with a local speech-to-text
model, and forward the transcript to an agent gateway.

The gateway step targets any **OpenAI-compatible chat completions endpoint**
(`POST /v1/chat/completions`), so it works with a wide range of agent
backends. [Hermes](https://github.com/NousResearch/Hermes) is the example it
was tested against, but you can point it at any compatible gateway (vLLM,
Ollama, LM Studio, OpenAI, other agent frameworks, etc.) via configuration.

The pipeline has three stages: **record -> OGG**, **OGG -> transcript `.txt`**,
and **transcript -> agent gateway** (the reply is saved and shown).

## Features

- One-button browser recorder (vanilla JS, no frontend build step).
- Uploads are stored as `recordings/{uuid}.ogg`.
- Cross-browser OGG output: Firefox records OGG/Opus directly; Chrome/Edge
  record WebM/Opus, which the server transcodes to OGG with `ffmpeg`.
- Local speech-to-text with [faster-whisper](https://github.com/SYSTRAN/faster-whisper):
  each recording is transcribed (language auto-detected) and the text is saved
  alongside the audio as `recordings/{uuid}.txt` and shown in the browser.
- Transcript forwarding to any OpenAI-compatible agent gateway: the reply is
  saved as `recordings/{uuid}.agent.txt` and shown in the browser. Active only
  when a gateway API key is configured.

## Requirements

- Python 3.11+
- `ffmpeg` on `PATH` (needed to transcode WebM uploads from Chrome/Edge)
- Python packages in [requirements.txt](requirements.txt): `fastapi`,
  `uvicorn[standard]`, `python-multipart`, `faster-whisper`
- Network access on first run to download the Whisper model (cached afterwards)

## Port

The app runs on **port 8095** by default. Pass `--port <PORT>` to `uvicorn` to
use a different port if it conflicts with another service.

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
| `AGENT_API_KEY` | *(unset)* | Agent gateway API key. Forwarding is **enabled only when this is set** (alias: `VOICEGATEWAY_AGENT_API_KEY`) |
| `AGENT_BASE_URL` | `http://127.0.0.1:3001` | Agent gateway base URL (any OpenAI-compatible endpoint) |
| `AGENT_MODEL` | `hermes-agent` | Model name sent to the gateway (set to your gateway's model id) |
| `AGENT_TIMEOUT` | `120` | Per-request timeout (seconds) |
| `AGENT_SYSTEM_PROMPT` | *(unset)* | Optional system prompt prepended to each request |

> The gateway settings are gateway-agnostic: point `AGENT_BASE_URL`,
> `AGENT_MODEL`, and `AGENT_API_KEY` at any OpenAI-compatible endpoint. The
> defaults target a local gateway; `AGENT_MODEL` defaults to `hermes-agent`
> only because that is the model id of the local example gateway.

Enable forwarding by launching with the key, for example:

```bash
# Example: local gateway (default base URL/model)
AGENT_API_KEY=your-gateway-key \
  uvicorn app.main:app --host 0.0.0.0 --port 8095

# Example: a different OpenAI-compatible gateway
AGENT_BASE_URL=https://my-gateway.example.com \
AGENT_MODEL=my-model \
AGENT_API_KEY=your-gateway-key \
  uvicorn app.main:app --host 0.0.0.0 --port 8095
```

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Serves the recorder web page |
| `GET` | `/api/health` | Returns `{"ok": true}` |
| `POST` | `/api/recordings` | `multipart/form-data` with field `audio`; saves the clip, transcribes it, forwards the transcript to the configured agent gateway, and returns `{ id, filename, path, size_bytes, transcript, language, transcript_file, stt_error, agent_reply, agent_file, agent_error }` |

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
- If gateway forwarding fails (or no key is configured), the audio and
  transcript are still saved; the response returns `200` with `agent_reply:
  null` and, on failure, a populated `agent_error`.

## Project layout

```
voicegateway/
  requirements.txt
  README.md
  app/
    main.py         # FastAPI app: routes + static serving + STT/gateway wiring
    config.py       # recordings dir, size cap, Whisper + gateway settings
    storage.py      # uuid naming + ffmpeg WebM -> OGG + transcript/reply writers
    stt.py          # faster-whisper model + transcribe_file()
    agent_client.py # async gateway client (send_to_agent())
  static/
    index.html      # recorder UI + transcript + agent reply views
    app.js          # getUserMedia + MediaRecorder + upload + result display
  recordings/       # runtime (gitignored): {uuid}.ogg + {uuid}.txt + {uuid}.agent.txt
  .models/          # Whisper model cache (gitignored)
```

## Roadmap (later ideas)

- Optional list/playback page for saved recordings, transcripts, and replies.
- Streaming gateway responses to the browser.
