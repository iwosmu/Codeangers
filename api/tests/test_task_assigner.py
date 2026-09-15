"""task_assigner: team parsing, task loading, validation with the execution-rule
simulation, the assign loop with a stubbed Gemini client, and the CLI. No network."""

import json
from types import SimpleNamespace

import pytest
from google.genai import types

from app.task_assigner import (
    ASSIGNMENT_SCHEMA,
    AssignerConfig,
    AssignmentError,
    AssignResult,
    TaskAssigner,
    check_tasks,
    load_tasks,
    parse_members,
    validate_assignment,
)
from app.task_assigner.validation import Deadlock, simulate_schedule

MEMBERS = [{"id": "m1", "name": "Ala"}, {"id": "m2", "name": "Bartek"}, {"id": "m3", "name": "Celina"}]

TEAM_MD = """\
# Fictional team — team understanding

Evidence-based suggestions for discussion.

## Ala

Member ID: m1

CV name: Ala [m1:e1]

### Likely roles

- Backend contributor [m1:e1]

### Stack & tools

- Python [m1:e1]

## Bartek

Member ID: m2

CV name: not stated

### Stack & tools

- React [m2:e1]

## Celina

Member ID: m3

CV name: Celina [m3:e1]

## Team overview

### Coverage map

| Area | Ala | Bartek | Celina |
| --- | --- | --- | --- |
| Backend | ●● [m1:e1] | – | ● [m3:e1] |

### Questions for the team

- When are you available?
"""


def task(id_, name, hours, people, prereqs=(), group="backend"):
    return {"id": id_, "name": name, "description": f"{name}: what is done and which skills it needs.",
            "group": group, "prerequisites": list(prereqs), "estimated_time_hours": hours,
            "people_needed": people}


def tasks():
    """Ten tasks for three people; every wave can occupy all three."""
    return [task(1, "Set up repository", 4, 1, group="setup"), task(2, "Design screens", 4, 1, group="design"),
            task(3, "Provision infrastructure", 4, 1, group="devops"), task(4, "Build API", 8, 1, [1]),
            task(5, "Build frontend", 8, 1, [2], group="frontend"), task(6, "Model database", 8, 1, [3], group="database"),
            task(7, "Integrate API and frontend", 4, 2, [4, 5]), task(8, "Write integration tests", 4, 1, [6], group="testing"),
            task(9, "Write documentation", 4, 1, [8], group="docs"), task(10, "Deploy to production", 4, 2, [7], group="devops")]


def graph():
    """The same tasks in the planner's {nodes, edges} shape."""
    nodes = [{"id": t["id"], "label": t["name"], "title": t["description"], "group": t["group"],
              "estimated_time_hours": t["estimated_time_hours"], "people_needed": t["people_needed"]} for t in tasks()]
    edges = [{"from": p, "to": t["id"]} for t in tasks() for p in t["prerequisites"]]
    return {"nodes": nodes, "edges": edges}


LISTS = {"m1": [1, 4, 7, 10], "m2": [2, 5, 7, 10], "m3": [3, 6, 8, 9]}


def assignment(lists=None, notes=None):
    """Both views built from per-member lists, so they agree by construction."""
    lists = lists or LISTS
    names = {m["id"]: m["name"] for m in MEMBERS}
    owners = {t["id"]: [names[m] for m, ids in lists.items() if t["id"] in ids] for t in tasks()}
    return {"tasks": [{"task_id": t["id"], "task_name": t["name"], "assigned_to": owners[t["id"]]} for t in tasks()],
            "people": [{"member_id": m["id"], "name": m["name"], "task_ids": list(lists.get(m["id"], []))} for m in MEMBERS],
            "notes": notes or []}


# --- inputs -------------------------------------------------------------------

def test_parse_members_from_rendered_team_md():
    assert parse_members(TEAM_MD) == MEMBERS


def test_parse_members_unescapes_markdown_and_ignores_other_sections():
    doc = "# T\n\n## Ola \\_dev\\_\n\nMember ID: m1\n\n### Strengths\n\n- x\n\n## Team overview\n\n### Coverage map\n"
    assert parse_members(doc) == [{"id": "m1", "name": "Ola _dev_"}]
    assert parse_members("# nothing here\n") == []
    with pytest.raises(ValueError, match="same Member ID"):
        parse_members("## A\n\nMember ID: m1\n\n## B\n\nMember ID: m1\n")


def test_load_tasks_accepts_every_planner_shape():
    flat = tasks()
    assert load_tasks(flat) == flat
    assert load_tasks({"tasks": flat}) == flat
    assert load_tasks({"data": {"tasks": flat}}) == flat
    assert load_tasks(graph()) == flat
    assert load_tasks({"ok": True, "data": {"graph": graph(), "tasks": flat}}) == flat
    with pytest.raises(ValueError):
        load_tasks({"foo": 1})


def test_check_tasks_rejects_unusable_lists():
    check_tasks(tasks())
    broken = tasks(); broken[0]["prerequisites"] = [10]        # 1 -> 4 -> 7 -> 10 -> 1
    with pytest.raises(ValueError, match="cycle"):
        check_tasks(broken)
    broken = tasks(); broken[3]["prerequisites"] = [99]
    with pytest.raises(ValueError, match="unknown prerequisite"):
        check_tasks(broken)
    broken = tasks(); broken[1]["id"] = 1
    with pytest.raises(ValueError, match="unique"):
        check_tasks(broken)
    with pytest.raises(ValueError, match="empty"):
        check_tasks([])


# --- validation ---------------------------------------------------------------

def test_valid_assignment_passes():
    r = validate_assignment(assignment(), tasks(), MEMBERS)
    assert r.ok and r.warnings == []
    assert r.makespan_hours == 20 and r.critical_path_hours == 20
    assert r.total_person_hours == 60 and r.idle_person_hours == 0 and r.idle_fraction == 0.0
    assert r.schedule[7] == (12, 16) and r.schedule[10] == (16, 20) and r.schedule[9] == (16, 20)
    assert r.summary().startswith("OK")


def test_views_must_agree():
    a = assignment(); a["tasks"][0]["assigned_to"] = ["Bartek"]   # task 1 is in Ala's list
    r = validate_assignment(a, tasks(), MEMBERS)
    assert any("task 1" in e and "two views must agree" in e for e in r.errors)


def test_people_needed_is_enforced():
    lists = {"m1": [1, 4, 7, 10], "m2": [2, 5, 10], "m3": [3, 6, 8, 9]}   # task 7 needs two members
    r = validate_assignment(assignment(lists), tasks(), MEMBERS)
    assert any("task 7" in e and "needs 2 member(s) but appears in 1 list(s)" in e for e in r.errors)


def test_unknown_and_missing_ids_are_errors():
    a = assignment(); a["people"][0]["task_ids"].append(99)
    assert any("unknown task id 99" in e for e in validate_assignment(a, tasks(), MEMBERS).errors)

    a = assignment(); a["people"][0]["member_id"] = "m9"
    errors = validate_assignment(a, tasks(), MEMBERS).errors
    assert any("unknown member id 'm9'" in e for e in errors)
    assert any("member m1 (Ala) is missing" in e for e in errors)

    a = assignment(); a["people"][0]["task_ids"] = [1, 1, 4, 7, 10]
    assert any("lists task 1 more than once" in e for e in validate_assignment(a, tasks(), MEMBERS).errors)

    a = assignment(); del a["tasks"][2]
    assert any("task 3" in e and "missing from the tasks view" in e for e in validate_assignment(a, tasks(), MEMBERS).errors)


def test_name_mismatches_and_odd_notes_are_warnings_not_errors():
    a = assignment(notes=[{"task_id": 99, "name": "Nobody", "note": "x"}, {"task_id": 0, "name": "Ala", "note": "ok"}])
    a["people"][0]["name"] = "ala"
    a["tasks"][0]["task_name"] = "Setup"
    r = validate_assignment(a, tasks(), MEMBERS)
    assert r.ok
    assert len(r.warnings) == 4 and any("unknown task id 99" in w for w in r.warnings)


def test_deadlock_is_reported():
    lists = {"m1": [1, 4, 10, 7], "m2": [2, 5, 7, 10], "m3": [3, 6, 8, 9]}
    r = validate_assignment(assignment(lists), tasks(), MEMBERS)
    assert any("cannot be executed: at hour 20" in e
               and "m1 waits for task 10 (prerequisite(s) 7 not finished; co-assignee(s) m2 not at that task)" in e
               and "m2 waits for task 7 (co-assignee(s) m1 not at that task)" in e for e in r.errors)
    with pytest.raises(Deadlock):
        simulate_schedule(lists, tasks())


def test_idle_team_is_rejected():
    lists = {"m1": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], "m2": [7, 10], "m3": []}
    r = validate_assignment(assignment(lists), tasks(), MEMBERS)
    assert not r.ok
    assert any("idle 62% of the time over a 52 h project (limit 25%)" in e for e in r.errors)
    assert r.idle_person_hours == 96 and r.makespan_hours == 52


def test_idle_while_work_is_ready_is_a_warning():
    lists = {"m1": [1, 4, 7, 10], "m2": [2, 5, 7, 10, 9], "m3": [3, 6, 8]}
    r = validate_assignment(assignment(lists), tasks(), MEMBERS)
    assert r.ok and r.makespan_hours == 24 and r.idle_person_hours == 12
    assert any("Celina (m3) idle h 16-24 while task(s) 9 were ready" in w for w in r.warnings)
    assert any("critical path is 20 h" in w for w in r.warnings)


def test_shape_errors_do_not_crash():
    r = validate_assignment({"tasks": [], "people": [{"member_id": "m1"}], "notes": "no"}, tasks(), MEMBERS)
    assert not r.ok
    r = validate_assignment({"tasks": [{"task_id": "1"}], "people": [], "notes": []}, tasks(), MEMBERS)
    assert any("tasks entry #0" in e for e in r.errors)


# --- the assign loop with a stubbed client -------------------------------------

def response(payload, finish_reason=types.FinishReason.STOP):
    text = json.dumps(payload)
    return SimpleNamespace(
        candidates=[SimpleNamespace(
            finish_reason=finish_reason,
            content=types.Content(role="model", parts=[types.Part.from_text(text=text)]))],
        text=text,
        prompt_feedback=None)


class StubClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.models = self

    def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        return self.responses.pop(0)


def test_assigner_sends_errors_back_and_accepts_the_fix():
    idle = assignment({"m1": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], "m2": [7, 10], "m3": []})
    client = StubClient([response(idle), response(assignment())])
    result = TaskAssigner(client=client, config=AssignerConfig(model="stub-model")).assign(TEAM_MD, graph())
    assert result.ok and result.rounds == 2 and result.members == MEMBERS and result.tasks == tasks()
    assert [h.ok for h in result.history] == [False, True]
    assert result.assignment["people"][0]["task_ids"] == [1, 4, 7, 10]

    first, second = client.calls
    assert first["model"] == "stub-model"
    assert first["config"].response_json_schema == ASSIGNMENT_SCHEMA
    assert "senior delivery lead" in str(first["config"].system_instruction)
    prompt = first["contents"][0].parts[0].text
    assert "<team>" in prompt and "Member ID: m1" in prompt
    assert '"people_needed": 2' in prompt and '"prerequisites": [\n      4,\n      5\n    ]' in prompt
    assert '"task_id"' not in prompt          # the output shape is enforced by the schema, not the prompt
    assert len(second["contents"]) == 3 and second["contents"][1].role == "model"
    fix = second["contents"][2].parts[0].text
    assert fix.startswith("Your assignment violates the rules")
    assert "idle 62%" in fix


def test_truncated_response_raises():
    client = StubClient([response(assignment(), finish_reason=types.FinishReason.MAX_TOKENS)])
    with pytest.raises(AssignmentError, match="max_output_tokens"):
        TaskAssigner(client=client).assign(TEAM_MD, tasks())


def test_unusable_output_raises():
    client = StubClient([response({"people": []})])
    with pytest.raises(AssignmentError, match='"tasks", "people" and "notes"'):
        TaskAssigner(client=client).assign(TEAM_MD, tasks())


def test_bad_inputs_fail_before_any_model_call():
    client = StubClient([])
    assigner = TaskAssigner(client=client)
    broken = tasks(); broken[0]["prerequisites"] = [10]
    with pytest.raises(ValueError, match="cycle"):
        assigner.assign(TEAM_MD, broken)
    with pytest.raises(ValueError, match="no team members"):
        assigner.assign("# no members here\n", tasks())
    assert client.calls == []


def test_explicit_members_override_parsing():
    client = StubClient([response(assignment())])
    result = TaskAssigner(client=client).assign("# hand-written team\n", tasks(), members=MEMBERS)
    assert result.ok and result.members == MEMBERS


# --- CLI ------------------------------------------------------------------------

def fake_assigner(monkeypatch, lists):
    from app.task_assigner import __main__ as cli
    validation = validate_assignment(assignment(lists), tasks(), MEMBERS)

    class FakeAssigner:
        def __init__(self, client=None, config=None):
            self.config = config

        def assign(self, team_md, tasks_in, members=None):
            assert "Member ID: m1" in team_md and load_tasks(tasks_in) == tasks()
            return AssignResult(assignment(lists), validation, MEMBERS, tasks(), 1, [validation])

    monkeypatch.setattr(cli, "TaskAssigner", FakeAssigner)
    return cli


def write_inputs(tmp_path):
    team = tmp_path / "team.md"
    team.write_text(TEAM_MD, encoding="utf-8")
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps(graph()), encoding="utf-8")
    return team, plan


def test_cli_writes_the_assignment(monkeypatch, tmp_path, capsys):
    cli = fake_assigner(monkeypatch, LISTS)
    team, plan = write_inputs(tmp_path)
    out = tmp_path / "assignment.json"
    assert cli.main([str(team), str(plan), "-o", str(out), "--show-schedule"]) == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["people"][0] == {"member_id": "m1", "name": "Ala", "task_ids": [1, 4, 7, 10]}
    assert written["tasks"][6] == {"task_id": 7, "task_name": "Integrate API and frontend", "assigned_to": ["Ala", "Bartek"]}
    err = capsys.readouterr().err
    assert "3 members, 10 tasks, 1 round(s): OK" in err
    assert "task 7 (Integrate API and frontend): Ala, Bartek" in err


def test_cli_rejects_an_invalid_assignment_unless_allowed(monkeypatch, tmp_path):
    cli = fake_assigner(monkeypatch, {"m1": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], "m2": [7, 10], "m3": []})
    team, plan = write_inputs(tmp_path)
    out = tmp_path / "assignment.json"
    assert cli.main([str(team), str(plan), "-o", str(out)]) == 1
    assert not out.exists()
    assert cli.main([str(team), str(plan), "-o", str(out), "--allow-invalid"]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["people"][2]["task_ids"] == []
