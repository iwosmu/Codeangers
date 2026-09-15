# Codeangers — team planner

Add project material and CVs for 2–8 people. Generate two evidence-backed Markdown briefs, a dependency graph, and suggested task owners. When a skill has no direct CV evidence, review a suggested contributor with related experience and a first learning step.

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

Open http://localhost:5173. The current brief, graph and assignment endpoints use Gemini; they do not substitute mock responses. Set `GEMINI_API_KEY` (or `GEMINI_KEY`) in the repository's `.env.local`. Inputs and outputs stay in the browser/request session, with no application persistence.

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
| `GET` | `/api/health` | — | Connection/model status |
| `POST` | `/api/briefs/project` | multipart project text/files and setup | Structured brief + `project.md` |
| `POST` | `/api/briefs/team` | multipart CVs and setup | CV evidence + `team.md` |
| `POST` | `/api/task-graph` | `{ project_md, team_md, team_size }` | Validated graph and flat tasks |
| `POST` | `/api/task-assignments` | `{ team: TeamBrief, tasks }` | Owners by member ID, ordered task lists, skill fit, schedule validation |
| `POST` | `/api/github/preview` | Reviewed repository, profiles, tasks; token header | Issue preview |
| `POST` | `/api/github/export` | Same reviewed snapshot; token header | Parent issue and assigned sub-issues |

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

## Assignment integration

`api/app/task_assigner/` is integrated from `task-assigner` commit `6c86e81`; no other frontend or backend from that branch is imported. Its schedule simulator checks task coverage, headcounts, agreeing task/member views, dependency order and deadlocks. Application requests allow unavoidable idle capacity and report it rather than forcing unsupported skill matches.

The graph appears first, then owner suggestions run automatically. Assignment can be retried independently. Suggested owners feed the existing editable owner controls and reviewed GitHub export; nothing is published automatically.

Graph generation handles deliverables and technical prerequisites. Shared specialists are scheduled by the subsequent owner-assignment call, so skill overlap does not create artificial dependency edges. Application graph generation reports idle capacity as a warning instead of rejecting a valid graph at an arbitrary utilization threshold; cycles, missing dependencies and excessive per-task headcounts remain errors.

- **Direct match:** evidence for all required skills.
- **Closest skillset · learning needed:** relevant CV evidence, explicit missing skills and a concrete first learning step.
- **Fit unconfirmed:** insufficient relevant evidence to rank learning fit; a proposed owner needs team confirmation.

Task cards mark learning/review cases. The sidebar shows the reason, missing skills and original CV quotations. Assignment controls, task order, team-wide skill gaps and match explanations live in the selected-task sidebar; there is no separate assignment stage. Manual owner changes invalidate the displayed fit/schedule status; original suggestions remain available for comparison. Recalculating replaces owner suggestions. Duration assumes continuous availability and excludes learning time.

Prompts: `api/app/task_assigner/prompts.py` (assignment and scheduling), `api/app/prompts/assignment_fit.md` (evidence and learning-gap policy). The model compares semantic skill fit; code verifies member/task IDs, evidence references and consistent fit labels. Returned explanations use literal CV excerpts instead of unchecked model narratives that could incorrectly connect a separately listed tool to a project. The fit classification remains a suggestion to review with the team.

No dependencies added. Model calls use the configured Gemini model, a 60-second timeout per attempt, and at most one repair in the application. Tests: `cd api && uv run pytest`; `npm --prefix web test`; `npm --prefix web run build`.

## Consolidated frontend design

The interface applies the visual system from `new_desing` (`a75ac77`) to the working frontend on `main`: connected progress navigation, monochrome surfaces, project guidance, team coverage, and profile review. Project context/constraints, multimodal attachments, 2–8 member inputs, pasted CVs, Markdown views/downloads, evidence disclosures, and the reviewed GitHub export are retained. Graph node dimensions, layout, dependency routing, zoom/pan, orientation, focus mode and ownership controls remain from `main`; graph changes are visual only. The design branch's demo fallbacks and legacy API calls are not used.

## Demo recording

See [demo/README.md](demo/README.md) for the real-project, real-CV Playwright recording workflow. Validated responses stay in process memory; only the requested video and stills are saved in the ignored output directory. The app itself has no demo-result cache.
