# task_planner

Turns a project description and a team description (two markdown files) into a
validated, dependency-ordered task graph using the Gemini API. The output is
shaped for vis.js / PyVis: `{"nodes": [...], "edges": [...]}`.

```
task_planner/
  prompts.py      system instruction, user prompt template, fix-round prompt
  schema.py       GRAPH_SCHEMA passed as response_json_schema; Node/Edge/Graph/Task types
  graph.py        graph <-> flat task list conversion, levels(), to_pyvis()
  validation.py   validate_graph()/validate(): logical checks + schedule simulation
  planner.py      TaskPlanner: generate -> validate -> send errors back -> repeat
  __main__.py     CLI
requirements.txt
```

## Install

```
pip install -r requirements.txt
pip install pyvis                 # optional, only for rendering
set GEMINI_API_KEY=...            # Windows;  export GEMINI_API_KEY=... elsewhere
```

## Use

CLI:

```
python -m task_planner project.md team.md -o plan.json
python -m task_planner project.md team.md -o plan.json --html plan.html   # + PyVis render
python -m task_planner project.md team.md --format tasks                  # flat list instead
```

From code:

```python
from task_planner import TaskPlanner, PlannerConfig, to_pyvis

planner = TaskPlanner(config=PlannerConfig(model="gemini-3.8-flash", max_fix_rounds=2))
result = planner.plan(project_md, team_md)      # team_size inferred with a small call
print(result.validation.summary())
if result.ok:
    graph = result.graph                        # {"nodes": [...], "edges": [...]}
    tasks = result.tasks                        # same data, flat, with prerequisite ids
    to_pyvis(graph).write_html("plan.html")
```

## Output format

```json
{
  "nodes": [
    {
      "id": 1,
      "label": "Set up repository",
      "title": "Create the repo, branch rules and a README skeleton. ...",
      "group": "setup",
      "estimated_time_hours": 4,
      "people_needed": 1
    }
  ],
  "edges": [
    {"from": 1, "to": 4}
  ]
}
```

- `id`, `label`, `title`, `group` are vis.js node fields: `label` is the task
  name, `title` is the description (rendered as the hover tooltip), `group` is
  a one-word work category the model picks (backend, frontend, testing, ...)
  and vis.js colours nodes by it automatically.
- `estimated_time_hours` and `people_needed` are extra node properties; vis.js
  carries them on the node object and ignores them when drawing.
- An edge runs **from the prerequisite to the task that needs it**. Build the
  network with `Network(directed=True)` to get arrows.
- Feeding it to PyVis by hand:

  ```python
  net = Network(directed=True)
  for n in graph["nodes"]:
      net.add_node(n["id"], **{k: v for k, v in n.items() if k != "id"})
  for e in graph["edges"]:
      net.add_edge(e["from"], e["to"])
  ```

  `to_pyvis()` does the same plus a left-to-right hierarchical layout (vis.js
  `level` = dependency depth) and appends hours/people to the tooltip.
- `--format tasks` / `result.tasks` gives the flat view
  `{id, name, description, group, prerequisites: [ids], estimated_time_hours, people_needed}`.
  `graph_to_tasks` / `tasks_to_graph` convert between the two.

## How it works

1. `prompts.build_user_prompt` fills the two documents into the planning prompt
   (constraints on team size, per-skill limits, acyclic direct-only edges,
   people-aware estimates, full-team utilisation).
2. `generate_content` runs with `response_json_schema=GRAPH_SCHEMA`, so the
   shape is guaranteed by the API.
3. `validation.validate_graph` checks what a schema cannot: unique node ids,
   edges that resolve, no self-loops or cycles, `people_needed <= team_size`,
   enough root tasks to occupy everyone at the start, and a simulated schedule
   whose idle fraction stays under `max_idle_fraction` (default 25%).
   Duplicate edges, duplicate labels, redundant transitive edges and over-long
   tasks come back as warnings.
4. On errors the model's own turn plus the error list are appended and the
   model is asked for a corrected complete graph, up to `max_fix_rounds` times.

## Knobs (`PlannerConfig`)

| field               | default            | note |
|---------------------|--------------------|------|
| `model`             | `gemini-3.8-flash` | any Gemini 3.x / 2.5 model |
| `thinking_level`    | `"high"`           | Gemini 3.x only; set `None` for 2.5 |
| `thinking_budget`   | `None`             | Gemini 2.5; `-1` = dynamic |
| `max_output_tokens` | `32768`            | includes thinking tokens |
| `temperature`       | `None`             | leave default on Gemini 3 |
| `max_fix_rounds`    | `2`                | correction rounds after the first attempt |
| `max_task_hours`    | `40`               | longer tasks produce a warning |
| `max_idle_fraction` | `0.25`             | idle capacity above this is an error |

## Limits

- The schedule simulation counts heads only; it cannot tell that two parallel
  tasks both need the single React developer. That constraint is enforced by
  the prompt, not by code. If you have structured skill data, extend
  `simulate_schedule` to take it.
- Duplicate ids are a hard error; the prompt asks for 1..N in list order and
  the validator warns if that is not the case.
- Colours are not part of the output on purpose - `group` gives them for free
  in vis.js. Add a `"color"` key to nodes yourself if you want fixed colours.
