"""Prompt text for the task assigner.

The output *shape* is enforced by the JSON schema in ``schema.py``; per Google's
guidance the schema is deliberately not repeated here. These prompts carry only
the assignment rules and the execution model the result is checked against.
"""

from __future__ import annotations

import json

SYSTEM_INSTRUCTION = (
    "You are a senior delivery lead who staffs and schedules software projects. You take a "
    "fixed, dependency-ordered task list and one specific team, and you decide who does what "
    "and in which order so that the project finishes as early as possible with nobody waiting "
    "for work. You are strict about two things: a person only gets work they have evidence of "
    "being able to do, or the work they could learn fastest when nobody has that evidence, and "
    "the task list is not yours to change. Work the whole schedule out - who is free when, "
    "which tasks are unblocked, which skills each task consumes - before producing the final "
    "assignment. The schedule is your working tool; the assignment is the answer."
)

USER_PROMPT_TEMPLATE = """\
Below are two inputs. The first describes the team. The second is the complete task list for the project, produced for exactly this team: every task has an integer id, a name, a description that states what is done and which skills it needs, a group, the ids of its prerequisites, estimated_time_hours (wall-clock hours when exactly people_needed members work on it together) and people_needed.

<team>
{{TEAM_MD}}
</team>

<tasks>
{{TASKS_JSON}}
</tasks>

# Goal

Decide who does each task and in what order, so that the whole project finishes as early as possible and every member is working for as much of that time as the task graph allows. Output the same assignment in two views: for every task, the names of the members who do it; for every member, the ids of their tasks in the order they do them. A member works through their list one task at a time; the order is binding. Add a note for every task that had to go to someone without evidence for a skill it needs. Do not output a schedule: work it out to find the best assignment, then report only the assignment and the notes.

# How a plan is executed - the rules the assignment is checked against

- Hour 0 is the project start. Every member is available from hour 0 until the project ends, without breaks. Hours are abstract units of effort; only their proportions matter.
- A member starts the next task in their list as soon as three things are true: they have finished their previous task, every prerequisite of the task has finished, and every other member assigned to that task is also free. Until then they wait, idle. A member never skips ahead in their list.
- A task with people_needed greater than 1 is done by exactly that many members at the same time; it starts when the last of them is free and lasts estimated_time_hours for all of them.
- The project ends when the last task finishes. Idle time is every hour in which a member is not working, counted from hour 0 until the project ends.

# Hard constraints - verify every one before answering

## The task list is fixed
1. Every task is assigned to exactly people_needed distinct members and appears in each of their lists exactly once; no task is left out. Do not invent, split, merge, re-estimate tasks or change their prerequisites; use the ids exactly as given.
2. Name members exactly as the team document does: the Member ID (m1, m2, ...) and the name in that member's heading, spelled identically. Every member appears in the per-member view, even one with an empty list. The two views must describe the same assignment: a task's members are exactly the members whose lists contain that task.

## Only evidenced skills
3. A task goes to a member only if the team document gives evidence for the skills the task description names: their Stack & tools, Likely roles, Strengths, Experience level, and the Coverage map (●● strong, ● some). A dash in the coverage map, "not stated", or an entry under Gaps / unknowns is no evidence. Do not infer a skill from a job title, an adjacent technology, or another member's CV.
4. If no member has evidence for a skill a task needs, still assign the task, to the member who would learn that skill fastest: the closest evidenced background - the same coverage area, a related language, framework or tool, or work of the same kind. Add a note naming the task, the member, the missing skill and why this member is the closest fit. Never leave a task unassigned and never claim a skill the document does not support.
5. When a task needs several members, at least one of them must have strong or explicit evidence for the task's main skill; the others may contribute related skills.
6. Skills are consumed by tasks that run at the same time. If only one member has evidence for React, no two React tasks can run in parallel: put them one after the other on that member and fill the other members' time with other ready work. Apply this to every skill.

## Time
7. A member does one task at a time; tasks in a member's list never overlap.
8. A multi-member task is done by all its assigned members together for its whole duration. Arrange their lists so that they become free at the same moment; otherwise the ones who finish early sit idle.

# Optimisation - in this priority order
9. Project duration. The longest chain of prerequisites (summing estimated_time_hours along it) is the lower bound; get as close to it as the skills allow. Identify the critical path(s) first, staff every task on them with a fully qualified member who is free the moment its prerequisite finishes, and never let a critical task wait behind a less urgent task in someone's list or for a busy member.
10. Full utilisation. At every moment the number of members working must equal the team size whenever enough tasks are ready; a free member while a ready task they qualify for exists is a defect. Independent branches go to different members so they run in parallel; a chain of dependent tasks runs back to back, ideally with the same member, so no hand-off waits on someone who is busy. Order each list so that nobody waits for a prerequisite or a co-assignee while a ready task they could do exists, unless that wait is shorter than the alternative task and keeps a critical task on time. Example with two members: A (2 h), B (2 h, needs A) and an independent C (4 h). One member does A then B, the other does C, and the project takes 4 h. Putting A, B and C in one list takes 8 h; giving B to the member on C makes B wait until hour 4.
11. Skill fit. Among plans with the same duration and utilisation, prefer the one where each task goes to the member with the strongest evidence for its skills, where members follow their stated preferences and working-style signals, and where a member stays within one area or group of related tasks instead of switching context at every task.
12. Balance. Spread total working hours reasonably across members. A long idle stretch for one member while others carry chains of work is acceptable only when the skill constraints leave no alternative; then add a note saying so.

# Before producing the answer

1. List the members with their Member IDs, names, evidenced skills (stack, coverage levels, roles, strengths) and stated preferences; state N, the team size.
2. For each task, note the skills its description requires and which members qualify: strong, some, or fallback only (rule 4).
3. Compute each task's earliest possible start (all prerequisites finished) and the critical path(s); note the lower bound on the project duration.
4. Simulate the schedule event by event. Keep the set of ready tasks and the set of free members. At each event, start every ready task for which people_needed qualified members are free - critical-path tasks and longest remaining chains first - record its start hour, end hour and members, then advance to the next finishing time.
5. Read each member's list off the simulation in start-hour order, and each task's members from the same simulation. Check that every task appears in exactly people_needed lists and that no member's tasks overlap.
6. Hunt for idle gaps: a free member while a ready task they could do exists; a member waiting for a prerequisite while a ready task exists; a multi-member task whose members become free at different times; a skill bottleneck that another evidenced member could relieve. Re-assign or re-order to remove them and re-run the simulation until the project duration and the idle time stop improving.
7. Check constraints 1-8 one by one, make sure the two views agree, and write the notes for every rule-4 assignment.

Then output the assignment.
"""


def build_user_prompt(team_md: str, tasks: list[dict]) -> str:
    """Fill the assignment prompt with the team document and the flat task list.

    Uses str.replace rather than str.format so braces inside the markdown are
    left untouched. The task list is embedded as pretty-printed JSON.
    """
    tasks_json = json.dumps(tasks, ensure_ascii=False, indent=2)
    return (
        USER_PROMPT_TEMPLATE
        .replace("{{TEAM_MD}}", team_md.strip())
        .replace("{{TASKS_JSON}}", tasks_json)
    )


def build_fix_prompt(errors: list[str], warnings: list[str]) -> str:
    """Follow-up message sent when the assignment fails validation."""
    lines = ["Your assignment violates the rules. Problems that must be fixed:"]
    lines += [f"- {e}" for e in errors]
    if warnings:
        lines += ["", "Also improve these where the task graph allows it:"]
        lines += [f"- {w}" for w in warnings]
    lines += [
        "",
        "Return the complete corrected assignment - every task in the tasks view, every "
        "member in the people view, and the notes - still satisfying every rule from the "
        "original instructions.",
    ]
    return "\n".join(lines)
