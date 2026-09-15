# Team Work Splitter API

CVs and project material produce `team.md` and `project.md`, plus validated JSON for the future overview UI. The TaskPilot frontend uses these endpoints. Legacy project/CV/task/plan routes are no longer mounted.

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
- Project output covers idea, deliverables, constraints, and open questions. Task graph generation is available through the endpoint below. Named assignments belong to a later stage.

## Optional live smoke test

```sh
uv run python scripts/smoke_briefs.py --live
```

Consumes Gemini quota using fictional mixed-format CVs and a thin project description. Checks both documents, at least eight project questions, and the 60-second target. Ordinary pytest tests need no credentials or live model calls. Do not commit real CVs or generated personal profiles as fixtures.

## Task flow — POST /api/task-graph

After generating both briefs, send JSON:

```json
{"project_md":"# Project…", "team_md":"# Team…", "team_size":2}
```

`team_size` is the actual count from the generated team document (2–8), avoiding a separate counting call. Both documents must be non-empty and at most 1,000,000 characters each; request limit is 8 MB.

Returns the normal envelope with `data.graph` (`nodes` and `edges`), flat `data.tasks`, `team_size`, `rounds`, `ms`, and `validation`. Each node has integer `id`, `label`, `title` (plain-text task description), `group`, `estimated_time_hours`, and `people_needed`. Edges run `from` the prerequisite to the dependent task `to`.

The app runs the planner with MEDIUM thinking. The planner uses Gemini, validates the graph, and may request two corrections (three attempts total). Each SDK call has a 60-second timeout and no automatic retries. The synchronous package runs in a worker thread so the server remains responsive. Client connections close after planning. A browser cancellation stops waiting but a running worker may finish its bounded attempts. No graph or source documents are persisted.

Invalid requests return 400, exhausted invalid graphs 422, model failures 502, and rate limits 429, using the existing error envelope. The UI clears the dependent graph when an input brief changes or is regenerated.

Validation covers graph structure, cycles, references, positive estimates, headcount capacity, and a simulated utilisation threshold. Duration and utilisation are estimates; skill feasibility and stated deadlines are considered by the prompt but are not mechanically proven. `people_needed` is a headcount, not a named assignment.

Only `api/app/task_planner/` was imported from `taskparser` (source commit `5e702e3`), with integration fixes for bounded calls, malformed outputs, and hackathon-sized estimates. Its other adapters, files, and dependency suggestions were not imported. The app uses its own router and native React/SVG graph UI; optional PyVis rendering in the standalone package is not used or installed.
