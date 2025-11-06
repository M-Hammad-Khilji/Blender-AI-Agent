"""Nebius client wrapper using an OpenAI-compatible chat completions endpoint.

The function `call_hermes(system_prompt, user_prompt, ...)` returns the assistant
text (string) produced by the model. This keeps the server generic so `app.py`
can pass a system prompt and the user's instruction separately.
"""

import os
import requests
from typing import Dict

NEBIUS_API_KEY = os.environ.get("NEBIUS_API_KEY")
DEV_FALLBACK = os.environ.get("DEV_FALLBACK", "0")
if not NEBIUS_API_KEY:
    if DEV_FALLBACK == "1":
        NEBIUS_API_KEY = None
    else:
        raise RuntimeError(
            "Set NEBIUS_API_KEY environment variable or set DEV_FALLBACK=1 for local testing"
        )

MODEL = os.environ.get("NEBIUS_MODEL", "NousResearch/Hermes-4-70B")
NEBIUS_BASE_URL = os.environ.get("NEBIUS_BASE_URL", "https://api.studio.nebius.ai/v1")


def _post_json(url: str, headers: dict, payload: dict, timeout: int = 120) -> Dict:
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if resp.status_code >= 400:
        print(f"[nebius_client] HTTP {resp.status_code} response:\n{resp.text}")
    resp.raise_for_status()
    return resp.json()


def call_hermes(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 2000,
    temperature: float = 0.0,
) -> str:
    """Call Nebius Hermes using the OpenAI-compatible chat completions API.

    Returns assistant text (str). Raises RuntimeError on failure and prints
    the remote body into logs for easier debugging.
    """
    # Local dev fallback (no API key) returns a small example script
    if not NEBIUS_API_KEY:
        example = (
            "import bpy\n"
            "bpy.ops.mesh.primitive_cube_add(size=2, location=(0,0,1))\n"
            "obj = bpy.context.object\n"
            "obj.scale = (2, 1, 0.1)\n"
        )
        return example

    headers = {
        "Authorization": f"Bearer {NEBIUS_API_KEY}",
        "Content-Type": "application/json",
    }

    url = NEBIUS_BASE_URL.rstrip("/") + "/chat/completions"

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    try:
        data = _post_json(url, headers, payload, timeout=120)
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError(f"no choices in Nebius response: {data}")
        first = choices[0]
        # Support both older 'text' and modern 'message.content' shapes
        content = None
        if "message" in first and isinstance(first["message"], dict):
            content = first["message"].get("content")
        if not content:
            content = first.get("text") or first.get("message", {}).get("content")
        if not content:
            raise RuntimeError(f"couldn't find assistant content in response: {data}")
        return content
    except requests.exceptions.RequestException as e:
        body = (
            getattr(e.response, "text", "<no response body>")
            if hasattr(e, "response")
            else "<no response>"
        )
        raise RuntimeError(
            f"Nebius API request failed: {e} - response body: {body}"
        ) from e
