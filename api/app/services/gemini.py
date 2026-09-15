import json
from typing import Any

from ..config import settings
from ..envelope import ApiError

# OWNER E owns this wrapper. C and D use it and never import google.genai directly,
# so the model name, retry policy and JSON handling live in exactly one place.


def _client():
    key = settings().gemini_api_key
    if not key:
        raise ApiError("internal", "GEMINI_API_KEY is empty. Put it in .env or run with MOCK_ONLY=true.")
    try:
        from google import genai
    except ImportError as e:
        raise ApiError("internal", "google-genai is not installed. Run: uv sync") from e
    return genai.Client(api_key=key)


def generate_json(prompt: str, schema: dict, *, reason: bool = False,
                  files: list[dict] | None = None) -> dict[str, Any]:
    # prompt   the whole instruction, including the level scale and the constraints
    # schema   a responseSchema dict, so the model cannot return prose
    # reason   True for /tasks and /plan, False for extraction
    # files    optional [{"bytes": b"...", "mime": "application/pdf"}]
    from google.genai import types

    model = settings().model_reason if reason else settings().model_extract
    client = _client()

    parts: list[Any] = [prompt]
    for f in files or []:
        parts.append(types.Part.from_bytes(data=f["bytes"], mime_type=f["mime"]))

    try:
        resp = client.models.generate_content(
            model=model,
            contents=parts,
            config={
                "temperature": 0,                 # the demo must be reproducible
                "response_mime_type": "application/json",
                "response_schema": schema,
            },
        )
    except Exception as e:
        msg = str(e).lower()
        if "quota" in msg or "429" in msg or "rate" in msg:
            raise ApiError("rate_limited", "Gemini quota is exhausted. Try again in a minute.", retryable=True) from e
        raise ApiError("model_failed", "The model call failed: " + str(e), retryable=True) from e

    text = (getattr(resp, "text", None) or "").strip()
    if not text:
        raise ApiError("model_invalid_json", "The model returned an empty response.", retryable=True)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ApiError("model_invalid_json", "The model returned something that is not JSON.", retryable=True) from e
