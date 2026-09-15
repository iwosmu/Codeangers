"""Prompt text for the task planner.

The output *shape* is enforced by the JSON schema in ``schema.py``; per Google's
guidance the schema is deliberately not repeated here. These prompts carry only
the planning rules.
"""

from __future__ import annotations

SYSTEM_INSTRUCTION = (
    "You are a senior software project planner. You break IT projects into a "
    "dependency-ordered task list tailored to one specific team, and you are "
    "strict about respecting that team's size and skills. Think the plan through "
    "fully - dependency graph, schedule, skill conflicts - before producing the "
    "final list."
)

USER_PROMPT_TEMPLATE = """\
Below are two documents. The first describes the project to be delivered; the second describes the team that will build it.

<project>
{{PROJECT_MD}}
</project>

<team>
{{TEAM_MD}}
</team>

# Goal

Produce the complete set of tasks that, once all are finished, fully delivers the project - from initial setup through implementation, integration, testing, and whatever final steps the project calls for (deployment, documentation, handover). Nothing needed for completion may be left out, and nothing outside the project's scope may be added.

# Hard constraints - verify every one before answering

## Team capacity and skills
1. Let N be the number of team members. No task may need more than N people.
2. A task must be completable by some subset of the actual team members given the skills described in the team document. Do not create tasks that require skills nobody on the team has. If the project genuinely needs such a skill, add an explicit research/learning task for the most suitable team member as a prerequisite, and say so in the description.
3. Skill-count limits apply both within a task and across parallel tasks. If only one person knows React, then no React task may need more than one person, and no two React-heavy tasks may be runnable at the same time. Apply this to every skill.
4. Account for stated strengths, weaknesses and interests: route tasks toward people who are good at (or want to learn) them, and do not build the plan around a person's known weakness.

## Dependencies
5. Every task is a node with a unique integer id; number them 1, 2, 3, ... in the order the tasks are listed. A dependency is an edge from the prerequisite task's id to the id of the task that needs it - ids only, never names. No task may depend on itself, directly or transitively - the graph must be acyclic.
6. Add an edge only for direct prerequisites, never for ones already implied transitively.
7. Add an edge only when a task truly needs the other task's output. Do not add artificial ordering - unnecessary edges destroy parallelism.

## Estimates
8. The time estimate is wall-clock time for the stated number of people working on the task together. Adding people shortens a task, but not linearly - include coordination overhead. Calibrate to the experience levels described in the team document.
9. Keep tasks between roughly 4 and 40 hours. Split anything larger into smaller tasks with proper dependencies.

## Workflow - keep the whole team busy
10. Simulate the schedule step by step. At the start, the tasks with no incoming edges must together need at least N people (respecting the skill limits above). Every time a task finishes, the tasks that are in progress or newly unblocked must again be able to occupy all N team members, whenever the project's structure permits it. Prefer a wide dependency graph with parallel branches (e.g. tests, documentation, UI design, infrastructure running alongside core implementation) over long sequential chains. Idle team members are a defect in the plan - restructure to remove them.
11. Total effort (sum over tasks of hours x people) must be plausible for the project's scope, and the critical path must fit any deadline stated in the project document.

# Before producing the list

1. List the team members with their skills and experience level; state N.
2. List the major components/deliverables of the project.
3. Draft the task list, give each task a one-word group (backend, frontend, testing, ...), and draft the dependency edges.
4. Walk through the schedule wave by wave: which tasks are runnable, how many people they occupy, which skills they consume. Fix any wave where fewer than N people are busy or a skill is over-allocated.
5. Assign the ids last, sequentially in list order, and write every dependency as an edge from the prerequisite's id to the dependent task's id. Double-check that no id is used twice and that both ends of every edge exist.
6. Check constraints 1-11 one by one.

Then output the final graph of tasks (nodes) and dependencies (edges).
"""

TEAM_SIZE_PROMPT_TEMPLATE = """\
Below is a description of a team.

<team>
{{TEAM_MD}}
</team>

How many individual people are on this team? Count distinct team members, not roles, skills or tools.
"""


def build_user_prompt(project_md: str, team_md: str) -> str:
    """Fill the planning prompt with the two documents.

    Uses str.replace rather than str.format so braces inside the markdown
    files are left untouched.
    """
    return (
        USER_PROMPT_TEMPLATE
        .replace("{{PROJECT_MD}}", project_md.strip())
        .replace("{{TEAM_MD}}", team_md.strip())
    )


def build_team_size_prompt(team_md: str) -> str:
    return TEAM_SIZE_PROMPT_TEMPLATE.replace("{{TEAM_MD}}", team_md.strip())


def build_fix_prompt(errors: list[str], warnings: list[str]) -> str:
    """Follow-up message sent when the generated list fails validation."""
    lines = ["Your task graph violates the constraints. Problems that must be fixed:"]
    lines += [f"- {e}" for e in errors]
    if warnings:
        lines += ["", "Also improve these where the project's structure allows it:"]
        lines += [f"- {w}" for w in warnings]
    lines += [
        "",
        "Return the complete corrected graph - every node and edge, not only the "
        "changed ones - still satisfying every constraint from the original "
        "instructions.",
    ]
    return "\n".join(lines)
