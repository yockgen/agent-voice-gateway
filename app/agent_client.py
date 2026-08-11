"""Forward transcripts to an OpenAI-compatible agent gateway.

Sends the transcribed text as a chat completion and returns the assistant's
reply. Configuration (base URL, API key, model) comes from app.config and can
target any OpenAI-compatible endpoint.
"""

import httpx

from .config import (
    AGENT_API_KEY,
    AGENT_BASE_URL,
    AGENT_MODEL,
    AGENT_SYSTEM_PROMPT,
    AGENT_TIMEOUT,
)


class AgentError(RuntimeError):
    """Raised when the agent gateway call fails."""


def _build_messages(text: str) -> list[dict]:
    messages = []
    if AGENT_SYSTEM_PROMPT:
        messages.append({"role": "system", "content": AGENT_SYSTEM_PROMPT})
    messages.append({"role": "user", "content": text})
    return messages


async def send_to_agent(text: str) -> str:
    """Send `text` to the agent gateway and return the assistant reply.

    Raises AgentError on any transport, auth, or response-shape problem so the
    caller can degrade gracefully without losing the recording/transcript.
    """
    if not AGENT_API_KEY:
        raise AgentError("Agent gateway API key is not configured.")

    url = f"{AGENT_BASE_URL.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": AGENT_MODEL,
        "messages": _build_messages(text),
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {AGENT_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=AGENT_TIMEOUT) as client:
            resp = await client.post(url, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        raise AgentError(f"Could not reach agent gateway: {exc}") from exc

    if resp.status_code != 200:
        raise AgentError(
            f"Agent gateway returned HTTP {resp.status_code}: {resp.text[:300]}"
        )

    try:
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise AgentError(f"Unexpected agent gateway response shape: {exc}") from exc
