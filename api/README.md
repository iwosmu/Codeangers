# Team Work Splitter API

CVs and project material produce `team.md` and `project.md`, plus validated JSON for the future overview UI. This backend release does not include the new frontend. Legacy project/CV/task/plan routes are no longer mounted; integrate against the endpoints below.

## Run

Requires Python 3.12+ and uv. Copy the repository `.env.example` to `.env.local` and set `GEMINI_API_KEY` (aliases: `GEMINI_KEY`, `GOOGLE_API_KEY`). Keep credentials on the server. Set `CORS_ORIGINS` for your frontend. Default model: `gemini-3.8-flash`.

From `api/`:

```sh
uv sync --locked
uv run uvicorn app.main:app --reload --port 8000
uv run pytest -q
```

`GET /api/health` reports configuration readiness. Route docs: `/docs`. Multipart payloads are described below because uploads use a custom request parser.

## Independent generation

Use `FormData`; let the browser set the multipart boundary. Send both requests concurrently and display each result when it arrives.

### POST /api/briefs/team

One `input` field containing JSON:

```json
{
  "setup": {"name": "My team", "context": "48h hackathon", "constraints": ""},
  "members": [
    {"id": "m1", "label": "Member 1", "text": "Pasted CV text"},
    {"id": "m2", "label": "Member 2", "text": ""}
  ]
}
```

Add a file field `cv:m2` for the second member. Each member needs text, a file, or both; at most one file per member. Supply 2–8 members with unique IDs from `m1` through `m8`. No project attachment is required or accepted here. Shared setup supplies project context for team analysis.

### POST /api/briefs/project

One `input` field containing JSON:

```json
{
  "setup": {"name": "My project", "context": "48h hackathon", "constraints": ""},
  "project_text": "An app that helps students share surplus food."
}
```

Optionally add repeated `project` file fields. Text may be empty when an attachment is supplied. This endpoint does not take members or CVs.

### Responses

Envelope: `{ "ok": true, "data": ..., "warnings": [], "meta": ... }`.

A successful document in `data` contains:

- `filename`: `team.md` or `project.md`.
- `markdown`: complete document for preview/download.
- `schema_version`: `1.0`.
- `structured`: validated JSON; exact fields are in `app/brief_schemas.py`.
- `sources`: source IDs, labels, and optional member IDs.
- `warnings`: generation, validation, or cleanup notes.
- `ms`: document generation time.

Check both outer `ok` and `data.error`. Generation failures return `{ "warnings": [...], "error": { "code": "...", "message": "...", "retryable": true } }` inside `data`. Invalid requests use HTTP errors with `{ "ok": false, "error": ... }`. HTTP 200 alone does not mean a document was generated.

`POST /api/briefs` accepts combined team and project inputs and runs both calls concurrently. Its `data` contains `{ "team": ..., "project": ... }` with independent document errors. Separate endpoints allow immediate display of the faster result.

## Downloads

Create a browser download from `markdown`, or submit a native form to `POST /api/download/team.md` or `/api/download/project.md` with a URL-encoded `markdown` field. It returns a Markdown attachment without saving it. Encoded request limit: 2 MB.

## Inputs and processing

- CVs: PDF, DOCX, PNG/JPEG/WebP/HEIC/HEIF, TXT/MD, or pasted text.
- Project: the same plus PPTX and MP3/WAV/M4A/AAC/OGG/FLAC/AIFF. Export legacy DOC/PPT as PDF.
- Limits: 50 MB/file, 120 MB/request, 16 files total, 8 project attachments, 60,000 characters per pasted field.
- PDF/image/audio goes directly to Gemini. DOCX/PPTX text and raster images are extracted with the Python standard library. No OCR/ASR dependency.
- Assets over 20 MB use Gemini Files API with cleanup after the request; cleanup failures appear in warnings. Application inputs/results remain in memory. Gemini is an external processor.
- Edit `app/prompts/common.md`, `team.md`, and `project.md` to iterate on output. Structured output is validated and rendered as Markdown in code.
- Person claims reference CV evidence. Text quotations and ownership are checked locally; image/PDF transcription still depends on Gemini. Conservative coverage checks can mark unsupported scores unconfirmed. These checks do not guarantee perfect model interpretation.
- Project output covers idea, deliverables, constraints, and open questions. Tasks, schedules, and assignments belong to a later stage.

## Optional live smoke test

```sh
uv run python scripts/smoke_briefs.py --live
```

Consumes Gemini quota using fictional mixed-format CVs and a thin project description. Checks both documents, at least eight project questions, and the 60-second target. Ordinary pytest tests need no credentials or live model calls. Do not commit real CVs or generated personal profiles as fixtures.
