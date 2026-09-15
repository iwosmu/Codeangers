"""CLI: python -m app.task_planner project.md team.md -o tasks.json"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .planner import PlannerConfig, PlanningError, TaskPlanner


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m app.task_planner",
        description="Generate a validated task list for a project and team.",
    )
    p.add_argument("project_md", type=Path, help="markdown file describing the project")
    p.add_argument("team_md", type=Path, help="markdown file describing the team")
    p.add_argument("-o", "--output", type=Path, help="write the JSON here (default: stdout)")
    p.add_argument("--format", choices=("graph", "tasks"), default="graph",
                   help="graph = PyVis-shaped {nodes, edges} (default); tasks = flat list")
    p.add_argument("--html", type=Path, help="also render the graph to this HTML file with pyvis")
    p.add_argument("--team-size", type=int, help="skip the team-size extraction call")
    p.add_argument("--model", default=PlannerConfig.model)
    p.add_argument("--thinking-level", default=PlannerConfig.thinking_level,
                   help="Gemini 3 thinking level (low/medium/high); 'none' to unset")
    p.add_argument("--thinking-budget", type=int, help="Gemini 2.5 thinking budget (-1 = dynamic)")
    p.add_argument("--max-fix-rounds", type=int, default=PlannerConfig.max_fix_rounds)
    p.add_argument("--max-idle-fraction", type=float, default=PlannerConfig.max_idle_fraction)
    p.add_argument("--allow-invalid", action="store_true",
                   help="write the list even if validation still fails after all rounds")
    args = p.parse_args(argv)

    cfg = PlannerConfig(
        model=args.model,
        thinking_level=None if args.thinking_level in (None, "none") else args.thinking_level,
        thinking_budget=args.thinking_budget,
        max_fix_rounds=args.max_fix_rounds,
        max_idle_fraction=args.max_idle_fraction,
    )
    # Explicit UTF-8: Windows would otherwise decode with the locale code page.
    project_md = args.project_md.read_text(encoding="utf-8")
    team_md = args.team_md.read_text(encoding="utf-8")

    try:
        result = TaskPlanner(config=cfg).plan(project_md, team_md, team_size=args.team_size)
    except PlanningError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    v = result.validation
    print(f"team size {result.team_size}, {len(result.tasks)} tasks, "
          f"{result.rounds} round(s): {v.summary()}", file=sys.stderr)
    for w in v.warnings:
        print(f"  warning: {w}", file=sys.stderr)
    for e in v.errors:
        print(f"  ERROR: {e}", file=sys.stderr)

    if not result.ok and not args.allow_invalid:
        print("plan rejected; use --allow-invalid to write it anyway", file=sys.stderr)
        return 1

    data = result.graph if args.format == "graph" else result.tasks
    payload = json.dumps(data, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
        print(f"wrote {args.output}", file=sys.stderr)
    else:
        print(payload)

    if args.html:
        try:
            from .graph import to_pyvis
            to_pyvis(result.graph).write_html(str(args.html))
            print(f"wrote {args.html}", file=sys.stderr)
        except ImportError:
            print("pyvis is not installed (pip install pyvis); skipping --html", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
