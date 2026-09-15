# Codeangers — team planner

Paste a project brief and five CVs, get sections, a task graph with dependencies,
and a plan that keeps everyone unblocked at the same time. Gemini does the
planning; the code only checks the result.

## Stack

- `api/` — FastAPI + Pydantic v2, Gemini via `google-genai`
- `web/` — Vite + React + TypeScript
- `fixtures/` — the mock data every part of the system develops against

## Run it

Two terminals.

```bash
# terminal 1 — API on :8000
cd api
copy ..\.env.example ..\.env    # then put your key in it
uv run uvicorn app.main:app --reload --port 8000
```

`uv run` creates `.venv`, installs from `uv.lock` and fetches Python 3.12 if you do
not have it — no venv to activate, no `pip install`, and everyone gets byte-identical
versions. Install uv once: `winget install --id astral-sh.uv` (or `pip install uv`).

| Instead of | Use |
|---|---|
| `pip install X` | `uv add X` — writes `pyproject.toml` and `uv.lock`, commit both |
| `pip install -r requirements.txt` | `uv sync` |
| `pytest` | `uv run pytest` |
| activating the venv | nothing — prefix the command with `uv run` |

`uv.lock` is committed on purpose. Never edit it by hand; never install into the
API's venv with pip, or your machine stops matching everyone else's.

```bash
# terminal 2 — web on :5173, proxies /api to :8000
cd web
npm install
npm run dev
```

Open http://localhost:5173 . With `MOCK_ONLY=true` (the default) every endpoint
answers from `fixtures/`, so the whole app works before a single prompt exists.

## Mock mode

| How | Effect |
|---|---|
| `MOCK_ONLY=true` in `.env` | every endpoint answers from `fixtures/` |
| header `x-mock: 1` on one request | that request answers from `fixtures/` |
| `meta.mocked` in the response | tells the frontend which one it got |

Frontend work never blocks on backend work. That is the point.

## Who owns what

| | Lane | Paths |
|---|---|---|
| **A** | frontend — shell | `web/src/app/**`, `web/src/screens/setup/**`, `web/src/api/**`, `web/src/components/ui/**` |
| **B** | frontend — plan | `web/src/screens/plan/**`, `web/src/components/timeline/**` |
| **C** | project setup + planning | `api/app/services/ai_project.py`, `api/app/services/ai_plan.py` |
| **D** | CV + task graph + validation | `api/app/services/ai_cv.py`, `api/app/services/ai_tasks.py`, `api/app/services/validate.py`, `web/src/lib/validate.ts` |
| **E** | API backend | `api/app/main.py`, `api/app/routers/**`, `api/app/envelope.py`, `api/app/config.py`, deploy |
| — | **shared** | `api/app/schemas.py`, `web/src/types.ts`, `fixtures/*.json` — announce before changing |

`api/app/schemas.py` and `web/src/types.ts` are the same contract in two languages.
They must be edited together, in one commit, and announced out loud.

## API

| Method | Path | Body | Returns |
|---|---|---|---|
| `GET` | `/api/health` | — | `{ model, mockMode, commit }` |
| `POST` | `/api/project` | `{ brief, horizonHours, teamSize }` | `ProjectModel` |
| `POST` | `/api/cv` | multipart: `file` (pdf) or `text`, plus `name` | `PersonProfile` |
| `POST` | `/api/tasks` | `{ project }` | `TaskGraph` |
| `POST` | `/api/plan` | `{ project, people, graph, locks }` | `Plan` |

Every response is an envelope:

```json
{ "ok": true,  "data": {}, "warnings": [], "meta": { "ms": 12, "mocked": true, "cacheHit": false } }
{ "ok": false, "error": { "code": "rate_limited", "message": "...", "retryable": true } }
```

## Deploy (Render)

`render.yaml` defines both services. In Render: **New → Blueprint**, point it at this
repo, and set `GEMINI_API_KEY` when it asks. Two URLs come out:

| Service | What it is | URL |
|---|---|---|
| `codeangers-web` | static site, always on, free | what you demo and share |
| `codeangers-api` | FastAPI, free plan | only the static site talks to it |

The static site rewrites `/api/*` to the API service, so the browser only ever sees
one origin — no CORS, and no API URL baked into the bundle.

**The free plan sleeps after 15 minutes idle and cold-starts in roughly a minute.**
That is a dead minute in front of judges. Before the pitch, open the site once and
wait for it to answer, then leave the tab open. Do not find this out on stage.

`MOCK_ONLY` starts as `true`, so the deployed app works from fixtures before any
prompt exists. Flip it to `false` in the Render dashboard once `parse_project` and
friends are real — no redeploy needed, just restart the service.

## Rules

1. A drag in the UI never calls the model. Local edit + `validate.ts`, instant.
   Only the **Re-plan** button calls `POST /api/plan`.
2. `temperature=0` and cache every model response keyed on an input hash. The plan
   you rehearsed must be the plan that appears on stage.
3. One repair round when the validator finds errors, then give up and let the user
   fix it by hand. Never loop.
4. The Gemini key lives in `api/.env` only. Never in `web/`, never in a response, never in git.

## Consolidated frontend design

The interface applies the visual system from `new_desing` (`a75ac77`) to the working frontend on `main`: connected progress navigation, monochrome surfaces, project guidance, team coverage, and profile review. Project context/constraints, multimodal attachments, 2–8 member inputs, pasted CVs, Markdown views/downloads, evidence disclosures, and the reviewed GitHub export are retained. Graph node dimensions, layout, dependency routing, zoom/pan, orientation, focus mode and ownership controls remain from `main`; graph changes are visual only. The design branch's demo fallbacks and legacy API calls are not used.
