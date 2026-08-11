const recordBtn = document.getElementById("record");
const statusEl = document.getElementById("status");
const transcriptWrap = document.getElementById("transcript-wrap");
const transcriptEl = document.getElementById("transcript");
const agentWrap = document.getElementById("agent-wrap");
const agentEl = document.getElementById("agent");

let mediaRecorder = null;
let chunks = [];

const PREFERRED_MIME = [
  "audio/ogg; codecs=opus",
  "audio/webm; codecs=opus",
  "audio/webm",
];

function setStatus(message, kind = "") {
  statusEl.textContent = message;
  statusEl.className = kind;
}

function showTranscript(text) {
  transcriptEl.value = text;
  transcriptWrap.classList.add("visible");
}

function showAgent(text) {
  agentEl.value = text;
  agentWrap.classList.add("visible");
}

function hideTranscript() {
  transcriptEl.value = "";
  transcriptWrap.classList.remove("visible");
  agentEl.value = "";
  agentWrap.classList.remove("visible");
}

function pickMimeType() {
  if (typeof MediaRecorder === "undefined") return null;
  return PREFERRED_MIME.find((t) => MediaRecorder.isTypeSupported(t)) || null;
}

async function startRecording() {
  if (!navigator.mediaDevices?.getUserMedia) {
    setStatus("This browser does not support microphone capture.", "error");
    return;
  }

  const mimeType = pickMimeType();
  if (!mimeType) {
    setStatus("No supported audio recording format in this browser.", "error");
    return;
  }

  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (err) {
    setStatus(`Microphone access denied: ${err.name}`, "error");
    return;
  }

  chunks = [];
  mediaRecorder = new MediaRecorder(stream, { mimeType });

  mediaRecorder.ondataavailable = (e) => {
    if (e.data.size > 0) chunks.push(e.data);
  };

  mediaRecorder.onstop = async () => {
    stream.getTracks().forEach((t) => t.stop());
    const blob = new Blob(chunks, { type: mimeType });
    await uploadRecording(blob);
  };

  hideTranscript();
  mediaRecorder.start();
  recordBtn.textContent = "Stop & save";
  recordBtn.classList.add("recording");
  setStatus("Recording... speak now.");
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
  recordBtn.textContent = "Start recording";
  recordBtn.classList.remove("recording");
}

async function uploadRecording(blob) {
  setStatus("Uploading and transcribing... this can take a few seconds.");
  recordBtn.disabled = true;

  const form = new FormData();
  form.append("audio", blob, "recording");

  try {
    const res = await fetch("/api/recordings", { method: "POST", body: form });
    const payload = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(payload.detail || `HTTP ${res.status}`);
    }

    if (payload.stt_error) {
      setStatus(`Saved as ${payload.filename}, but transcription failed: ${payload.stt_error}`, "error");
    } else {
      const lang = payload.language ? ` [${payload.language}]` : "";
      setStatus(`Saved as ${payload.filename}${lang}`, "success");
      showTranscript(payload.transcript || "(no speech detected)");

      if (payload.agent_error) {
        showAgent(`(Agent error: ${payload.agent_error})`);
      } else if (payload.agent_reply) {
        showAgent(payload.agent_reply);
      }
    }
  } catch (err) {
    setStatus(`Upload failed: ${err.message}`, "error");
  } finally {
    recordBtn.disabled = false;
  }
}

recordBtn.addEventListener("click", () => {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    stopRecording();
  } else {
    startRecording();
  }
});
