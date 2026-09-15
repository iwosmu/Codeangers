"""Two independent calls, one request, no disk or server-side session storage."""
import asyncio
import json
import time

from fastapi import APIRouter, Request
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser
from pydantic import ValidationError

from ..brief_schemas import BriefInput, ProjectBriefInput, ProjectBrief, TeamBrief
from ..config import settings
from ..envelope import ApiError, ok
from ..services.brief_files import MAX_REQUEST_BYTES, Source, prepare_source
from ..services.brief_markdown import render_project, render_team
from ..services.brief_validation import validate_project, validate_team
from ..services.gemini import generate_brief

router = APIRouter()


class MemoryMultipartParser(MultiPartParser):
    # Starlette normally spools files >1 MB to disk. A bounded request fits entirely
    # below this threshold, so its SpooledTemporaryFile stays an in-memory BytesIO.
    spool_max_size = MAX_REQUEST_BYTES + 1
    max_file_size = MAX_REQUEST_BYTES + 1  # older Starlette spelling


async def read_inputs(request: Request, kind="both"):
    async def bounded_stream():
        total = 0
        async for chunk in request.stream():
            total += len(chunk)
            if total > MAX_REQUEST_BYTES:
                raise MultiPartException("The combined upload exceeds 120 MB.")
            yield chunk
    parser = MemoryMultipartParser(request.headers, bounded_stream(), max_files=16, max_fields=1, max_part_size=3_000_000)
    form = None
    try:
        form = await parser.parse()
        metadata = form.get("input")
        if not isinstance(metadata, str):
            raise ApiError("bad_input", "Missing product setup and member information.")
        body = (ProjectBriefInput if kind == "project" else BriefInput).model_validate_json(metadata)
        members = getattr(body, "members", [])
        member_ids = {m.id for m in members}
        if len(member_ids) != len(members):
            raise ApiError("bad_input", "Each team member needs a unique ID.")
        if len(form.getlist("input")) != 1:
            raise ApiError("bad_input", "Send exactly one input field.")
        team_sources = [Source(f"cv-{m.id}-text", "Pasted CV", m.id, m.text) for m in members if m.text.strip()]
        project_sources = [Source("setup", "Product setup", text=body.setup.model_dump_json())]
        if body.project_text.strip():
            project_sources.append(Source("project-text", "Project description", text=body.project_text))
        seen_cv = set()
        project_count = 0
        for field, upload in form.multi_items():
            if field == "input":
                continue
            if not isinstance(upload, UploadFile):
                raise ApiError("bad_input", "Unexpected upload field.")
            if kind != "project" and field.startswith("cv:") and field[3:] in member_ids:
                mid = field[3:]
                if mid in seen_cv:
                    raise ApiError("bad_input", "Use one CV file per member; additional text can be pasted.")
                seen_cv.add(mid)
                team_sources.append(prepare_source(f"cv-{mid}-file", upload.filename or "", await upload.read(), owner=mid))
            elif kind != "team" and field == "project":
                project_count += 1
                if project_count > 8:
                    raise ApiError("bad_input", "Use at most eight project attachments.")
                project_sources.append(prepare_source(f"project-file-{project_count}", upload.filename or "", await upload.read()))
            else:
                raise ApiError("bad_input", "A file was not linked to a team member or project.")
        for member in members:
            if not any(s.owner == member.id for s in team_sources):
                raise ApiError("bad_input", f"Add a CV file or pasted CV for {member.label or member.id}.")
        if kind != "team" and not body.project_text.strip() and not project_count:
            raise ApiError("bad_input", "Add a project description or at least one project attachment.")
        team_sources.sort(key=lambda s: [m.id for m in members].index(s.owner))
        return body, team_sources, project_sources
    except (ValidationError, json.JSONDecodeError, MultiPartException) as exc:
        raise ApiError("bad_input", "Check your inputs: 2–8 members, readable uploads, at most 60,000 characters per textbox and 120 MB combined.") from exc
    finally:
        if form is not None:
            await form.close()
        # Also close buffers on malformed/disconnected requests before parse() returns.
        for buffer in parser._files_to_close_on_error:
            buffer.close()


async def run_brief(kind, body, sources):
    schema, validate, render = (TeamBrief, validate_team, render_team) if kind == "team" else (ProjectBrief, validate_project, render_project)
    start = time.perf_counter()
    warnings = []
    try:
        async with asyncio.timeout(55):
            document, warnings = await generate_brief(kind, schema, body.setup, sources, warnings=warnings)
            if kind == "team":
                validate(document, body, sources)
                warnings.extend(document._coverage_review_notes)
            else:
                validate(document, sources)
            return {"filename": kind + ".md", "markdown": render(document, body, sources),
                    "schema_version": "1.0", "structured": document.model_dump(),
                    "sources": [{"id": s.id, "label": s.label, "member_id": s.owner} for s in sources],
                    "warnings": warnings,
                    "ms": round((time.perf_counter() - start) * 1000)}
    except TimeoutError:
        return {"warnings": warnings, "error": {"code": "model_timeout", "message": "Gemini took too long. Try again with smaller files.", "retryable": True}}
    except ApiError as exc:
        return {"warnings": warnings, "error": {"code": exc.code, "message": exc.message, "retryable": exc.retryable}}
    except Exception:
        return {"warnings": warnings, "error": {"code": "internal", "message": "This document could not be generated. Please try again.", "retryable": True}}


@router.post("/briefs")
async def create_briefs(request: Request):
    started = time.perf_counter()
    if not request.headers.get("content-type", "").startswith("multipart/form-data"):
        raise ApiError("bad_input", "Send the upload form as multipart/form-data.")
    body, team_sources, project_sources = await read_inputs(request)

    # No member material is passed to Call B; no project output/material is passed to Call A.
    team, project = await asyncio.gather(
        run_brief("team", body, team_sources),
        run_brief("project", body, project_sources),
    )
    return ok({"team": team, "project": project}, ms=round((time.perf_counter() - started) * 1000), model=settings().gemini_model)


@router.post("/briefs/{kind}")
async def create_one_brief(kind: str, request: Request):
    if kind not in {"team", "project"}:
        raise ApiError("bad_input", "Choose team or project.")
    if not request.headers.get("content-type", "").startswith("multipart/form-data"):
        raise ApiError("bad_input", "Send the upload form as multipart/form-data.")
    started = time.perf_counter()
    body, team_sources, project_sources = await read_inputs(request, kind)
    document = await run_brief(kind, body, team_sources if kind == "team" else project_sources)
    return ok(document, ms=round((time.perf_counter() - started) * 1000), model=settings().gemini_model)


@router.post("/download/{filename}")
async def download_markdown(filename: str, request: Request):
    """Return a native attachment without saving it, including in browsers without blob downloads."""
    from urllib.parse import parse_qs
    from fastapi.responses import Response
    if filename not in {"team.md", "project.md"}:
        raise ApiError("bad_input", "Choose team.md or project.md.")
    if not request.headers.get("content-type", "").startswith("application/x-www-form-urlencoded"):
        raise ApiError("bad_input", "Submit a Markdown document using the download form.")
    chunks = bytearray()
    async for chunk in request.stream():
        if len(chunks) + len(chunk) > 2_000_000:
            raise ApiError("bad_input", "The Markdown document is too large to download.")
        chunks.extend(chunk)
    try:
        fields = parse_qs(chunks.decode("utf-8"), strict_parsing=True, max_num_fields=1, errors="strict")
        markdown = fields["markdown"][0]
    except (ValueError, KeyError, UnicodeDecodeError) as exc:
        raise ApiError("bad_input", "The Markdown document is missing or malformed.") from exc
    if not markdown.strip():
        raise ApiError("bad_input", "There is no document to download yet.")
    return Response(markdown, media_type="text/markdown", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
