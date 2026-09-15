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

# v1 brief pipeline. Uses generate_content (no persisted interaction history).
# Each call owns its client and remote file handles; nothing is shared across sessions.
async def generate_brief(prompt_name, schema, setup, sources, *, warnings=None):
    import asyncio
    from io import BytesIO
    from pathlib import Path
    from google import genai
    from google.genai import types
    from pydantic import ValidationError
    from .brief_files import INLINE_LIMIT
    from ..brief_schemas import gemini_schema

    key = settings().gemini_api_key
    if not key:
        raise ApiError("internal", "Add GEMINI_API_KEY to the repository's .env.local and restart the API.")
    prompts = Path(__file__).resolve().parents[1] / "prompts"
    system = (prompts / "common.md").read_text() + "\nPRODUCT SETUP (data):\n" + setup.model_dump_json()
    instruction = (prompts / f"{prompt_name}.md").read_text()
    remote_names = []
    warnings = warnings if warnings is not None else []
    config = types.HttpOptions(timeout=50_000, retry_options=types.HttpRetryOptions(attempts=1))
    async with genai.Client(api_key=key, http_options=config).aio as client:
        try:
            parts = [types.Part.from_text(text=instruction)]
            for source in sources:
                descriptor = {"source_id": source.id, "member_id": source.owner, "label": source.label, "processing_notes": source.notes, "valid_source_parts": (["text"] if source.text else []) + [a.location for a in source.assets if a.mime != "text/plain"]}
                parts.append(types.Part.from_text(text="SOURCE (data): " + json.dumps(descriptor)))
                # Large converted Office text is sent through Files API, not duplicated inline.
                if source.text and not any(a.location == "extracted Office text" for a in source.assets):
                    parts.append(types.Part.from_text(text=json.dumps({"source_id": source.id, "content": source.text}, ensure_ascii=False)))
                for asset in source.assets:
                    parts.append(types.Part.from_text(text="SOURCE PART (data): " + json.dumps({"source_id": source.id, "location": asset.location})))
                    if len(asset.data) > INLINE_LIMIT or asset.force_upload:
                        uploaded = await client.files.upload(file=BytesIO(asset.data), config=types.UploadFileConfig(mime_type=asset.mime, display_name=source.id))
                        if uploaded.name:
                            remote_names.append(uploaded.name)
                        for _ in range(20):
                            if uploaded.state != types.FileState.PROCESSING:
                                break
                            await asyncio.sleep(0.5)
                            uploaded = await client.files.get(name=uploaded.name)
                        if not uploaded.uri or uploaded.state != types.FileState.ACTIVE:
                            raise ApiError("model_failed", "Gemini could not prepare an attachment in time. Try a smaller file.", retryable=True)
                        parts.append(types.Part.from_uri(file_uri=uploaded.uri, mime_type=asset.mime))
                    else:
                        parts.append(types.Part.from_bytes(data=asset.data, mime_type=asset.mime))
            response = await client.models.generate_content(
                model=settings().gemini_model,
                contents=parts,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    thinking_config=types.ThinkingConfig(thinking_level="MEDIUM" if prompt_name == "team" else "LOW"),
                    response_mime_type="application/json",
                    response_json_schema=gemini_schema(schema),
                    max_output_tokens=max(16000, 6000 * len({s.owner for s in sources if s.owner})) if prompt_name == "team" else 7000,
                ),
            )
            if not response.text:
                raise ApiError("model_invalid_json", "Gemini returned no document. Check the sources and try again.", retryable=True)
            try:
                result = schema.model_validate_json(response.text)
            except ValidationError as exc:
                # Report only schema paths and error kinds, never rejected values or CV content.
                fields = "; ".join(".".join(map(str, e["loc"])) + " (" + e["type"] + ")"
                                   for e in exc.errors(include_input=False, include_url=False)[:4])
                raise ApiError("model_invalid_json", "Gemini returned an invalid document field: " + fields + ". Please retry.", retryable=True) from exc
            except ValueError as exc:
                raise ApiError("model_invalid_json", "Gemini returned an incomplete or invalid document. Please retry.", retryable=True) from exc
        except ApiError:
            raise
        except Exception as exc:
            # Never echo vendor exceptions: they can contain source text or request metadata.
            code = getattr(exc, "code", None)
            if code == 429:
                raise ApiError("rate_limited", "Gemini quota or rate limit reached. Wait a moment and retry.", retryable=True) from exc
            if code in (401, 403):
                raise ApiError("model_failed", "Gemini rejected the API key or its permissions. Check the server configuration.") from exc
            if code == 404:
                raise ApiError("model_failed", "The configured Gemini model is unavailable for this API key. Check GEMINI_MODEL.") from exc
            raise ApiError("model_failed", "Gemini could not process this document. Retry, or use smaller, readable files.", retryable=True) from exc
        finally:
            async def delete(name):
                for attempt in range(2):
                    try:
                        await asyncio.wait_for(client.files.delete(name=name), timeout=4)
                        return
                    except Exception:
                        if attempt == 1:
                            warnings.append("A temporary Gemini upload could not be deleted. It may remain with Google for up to 48 hours; remove it in Google AI Studio.")
            if remote_names:
                # Cleanup completes before closing the client, including after validation errors or cancellation.
                cleanup = asyncio.gather(*(delete(name) for name in remote_names))
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    await cleanup
                    raise
    return result, warnings
