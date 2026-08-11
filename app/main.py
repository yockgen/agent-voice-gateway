"""Voice gateway: record from the mic, save as OGG, transcribe to text.

Run:
    cd /data/voicegateway
    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt   # ffmpeg must also be on PATH
    uvicorn app.main:app --host 0.0.0.0 --port 8095
"""

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import AGENT_ENABLED, MAX_UPLOAD_BYTES
from .agent_client import AgentError, send_to_agent
from .stt import TranscriptionError, transcribe_file
from .storage import (
    TranscodeError,
    save_recording,
    write_agent_reply,
    write_transcript,
)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="Voice Gateway", version="0.3.0")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.post("/api/recordings")
async def create_recording(audio: UploadFile = File(...)) -> dict:
    data = await audio.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Recording too large.")

    try:
        result = save_recording(data, audio.content_type)
    except TranscodeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    result.update({
        "transcript": None,
        "language": None,
        "transcript_file": None,
        "stt_error": None,
        "agent_reply": None,
        "agent_file": None,
        "agent_error": None,
    })

    # Transcribe off the event loop. A failure here must not lose the audio,
    # which is already saved -- report it and return the recording metadata.
    try:
        stt = await run_in_threadpool(transcribe_file, Path(result["path"]))
        txt_path = write_transcript(result["id"], stt["text"])
        result["transcript"] = stt["text"]
        result["language"] = stt["language"]
        result["transcript_file"] = txt_path.name
    except TranscriptionError as exc:
        result["stt_error"] = str(exc)

    # Forward the transcript to the agent gateway when configured and there is
    # text to send. Failures are reported but never discard the audio/transcript.
    if AGENT_ENABLED and result["transcript"]:
        try:
            reply = await send_to_agent(result["transcript"])
            reply_path = write_agent_reply(result["id"], reply)
            result["agent_reply"] = reply
            result["agent_file"] = reply_path.name
        except AgentError as exc:
            result["agent_error"] = str(exc)

    return result


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
