"""Forward transcripts to the Hermes OpenAI-compatible gateway.

Sends the transcribed text as a chat completion and returns the assistant's
reply. Configuration (base URL, API key, model) comes from app.config.
"""

import httpx

from .config import (
    HERMES_API_KEY,
    HERMES_BASE_URL,
    HERMES_MODEL,
    HERMES_SYSTEM_PROMPT,
    HERMES_TIMEOUT,
)


class HermesError(RuntimeError):
    """Raised when the Hermes gateway call fails."""


def _build_messages(text: str) -> list[dict]:
    messages = []
    if HERMES_SYSTEM_PROMPT:
        messages.append({"role": "system", "content": HERMES_SYSTEM_PROMPT})
    messages.append({"role": "user", "content": text})
    return messages


async def send_to_hermes(text: str) -> str:
    """Send `text` to Hermes and return the assistant reply.

    Raises HermesError on any transport, auth, or response-shape problem so the
    caller can degrade gracefully without losing the recording/transcript.
    """
    if not HERMES_API_KEY:
        raise HermesError("Hermes API key is not configured.")

    url = f"{HERMES_BASE_URL.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": HERMES_MODEL,
        "messages": _build_messages(text),
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {HERMES_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=HERMES_TIMEOUT) as client:
            resp = await client.post(url, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        raise HermesError(f"Could not reach Hermes gateway: {exc}") from exc

    if resp.status_code != 200:
        raise HermesError(
            f"Hermes returned HTTP {resp.status_code}: {resp.text[:300]}"
        )

    try:
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise HermesError(f"Unexpected Hermes response shape: {exc}") from exc
