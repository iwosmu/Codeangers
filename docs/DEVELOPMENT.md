# Development reference

TaskPilot is a completed hackathon prototype. Start with the [project overview](../README.md); the [submission archive](submission/README.md) preserves the original source and presentation materials.

## Repository map

| Path | Purpose |
| --- | --- |
| `web/src/screens/setup/` | Project setup and multimodal material input |
| `web/src/screens/plan/` | CV input and adjustable team roster |
| `web/src/screens/assignment/` | Team coverage and brief review (historical folder name) |
| `web/src/screens/flow/` | Graph, task inspector, owner suggestions, GitHub export |
| `web/src/state/` | Browser-session briefs, graph, assignments, and export state |
| `api/app/prompts/` | Shared rules, team/project prompts, skill-fit policy |
| `api/app/brief_schemas.py` | Structured brief and evidence schemas |
| `api/app/routers/` | Active FastAPI routes |
| `api/app/task_planner/` | Dependency planning and validation |
| `api/app/task_assigner/` | Owner assignment and schedule simulation |
| `fixtures/` | Original development fixtures; active generation endpoints call Gemini |
| `demo/` | Project PRD and optional Playwright recording helpers |
| `docs/submission/` | Pitch PDF, provenance, checksums, public issue snapshot |

## Local development

Use Python 3.12+, uv, Node.js, and npm. Copy `.env.example` to `.env.local` at the repository root and set `GEMINI_API_KEY`. The backend also accepts `GEMINI_KEY` and `GOOGLE_API_KEY`. Do not put credentials in the frontend or commit environment files.

```sh
# From the repository root; then leave this terminal running.
cd api
uv sync --locked
uv run uvicorn app.main:app --reload --port 8000
```

```sh
# In another terminal, from the repository root.
cd web
npm ci
npm run dev
```

Vite serves `http://localhost:5173` and proxies `/api` to port 8000. On Windows PowerShell use `Copy-Item .env.example .env.local` for the initial environment-file copy.

Use `uv add` for deliberate backend dependency changes; keep `uv.lock` committed. Use `npm ci` to install the committed frontend lockfile. The hackathon default is `gemini-3.8-flash`; set `GEMINI_MODEL` to a model available to your account if revisiting the project later.

## Checks

```sh
cd api
uv run pytest -q
```

```sh
npm --prefix web test
npm --prefix web run build
```

Ordinary tests use controlled inputs and do not require live Gemini calls. `api/scripts/smoke_briefs.py --live` is an explicit, quota-consuming smoke test; see the [API guide](../api/README.md). Recording helpers require an existing Playwright installation and FFmpeg; neither is an application dependency.

## Active API

| Method | Route | Result |
| --- | --- | --- |
| GET | `/api/health` | Configuration readiness and backend commit |
| POST | `/api/briefs/project` | Structured project brief and `project.md` |
| POST | `/api/briefs/team` | Structured team profiles, CV evidence, and `team.md` |
| POST | `/api/briefs` | Both briefs with independent results/errors |
| POST | `/api/download/{team,project}.md` | Markdown attachment without server persistence |
| POST | `/api/task-graph` | Validated nodes, edges, flat tasks, and estimates |
| POST | `/api/task-assignments` | Owners, skill-fit explanations, task order, and schedule checks |
| POST | `/api/github/preview` | Repository/account validation and issue preview |
| POST | `/api/github/export` | Parent issue, assigned sub-issues, and prerequisite links |

Responses use an `ok`/`data` or `ok`/`error` envelope. Some generation errors also appear inside `data`; HTTP 200 alone is not proof of successful generation. See [API details](../api/README.md) and the active router implementations.

## Pipeline decisions

The team and project brief calls share setup and product rules but run independently. The model returns structured JSON; code validates it and renders Markdown. Person claims refer to an evidence ledger. Text can be checked locally, while PDF/image transcription still depends on the model.

Task planning runs after the briefs. The planner validates dependencies, cycles, estimates, and headcounts. Shared specialists do not create artificial prerequisite edges: the later assignment stage handles their task order.

Owner suggestions appear in the existing graph view. Fit labels distinguish direct evidence, transferable experience with learning needed, and insufficient evidence. Explanations use quoted CV evidence. Manual owner changes invalidate the displayed fit and schedule; recalculation replaces the suggestions. Schedule duration assumes continuous availability and excludes learning time.

Application graph and assignment calls use LOW thinking with bounded attempts. Graph generation allows up to two corrections; assignment allows one repair. Idle capacity is reported rather than forcing an unsupported skill match. These checks validate structure and consistency, not the truth of every model interpretation.

GitHub publication requires a reviewed snapshot, distinct verified usernames, and an in-memory token with issue-writing access. Export markers support reconciliation after partial failures. The exported content contains the plan and assignments, not raw CVs.

## Integration history

- `task_planner` came from `taskparser` commit `5e702e3`, with integration fixes. The rest of that branch was not imported.
- `task_assigner` came from `task-assigner` commit `6c86e81`, then gained application-specific skill-gap handling and evidence checks.
- The visual design from `new_desing` commit `a75ac77` was applied to main's working frontend while retaining its graph layout and controls.
- The frozen application source for the recorded submission is `66c0daf`. The submission archive adds exact materials and final recording helpers; main's overview was written afterward.

## Hosting

[`render.yaml`](../render.yaml) defines a static frontend and FastAPI backend, both targeting `main`. The frontend rewrites `/api/*` to the backend; the API key is configured server-side in Render. Free hosting can sleep, and this archive does not promise continuing service availability. The backend health endpoint exposes its deployed commit for verification.

No application database is configured. Uploaded CVs and generated results are request/browser-session data; refreshing the page clears the working session. Gemini processes supplied materials externally. Raw CVs and private generated outputs must not be added as repository fixtures.
