import json
from pathlib import Path

from app.schemas import PersonProfile, Plan, ProjectModel, TaskGraph
from app.services.validate import metrics, validate_plan

FIX = Path(__file__).resolve().parents[2] / "fixtures"


def load():
    project = ProjectModel.model_validate(json.loads((FIX / "project.mock.json").read_text(encoding="utf-8")))
    people = [PersonProfile.model_validate(p)
              for p in json.loads((FIX / "people.mock.json").read_text(encoding="utf-8"))["people"]]
    graph = TaskGraph.model_validate(json.loads((FIX / "graph.mock.json").read_text(encoding="utf-8")))
    return project, people, graph


def test_good_plan_has_no_errors():
    project, people, graph = load()
    plan = Plan.model_validate(json.loads((FIX / "plan.mock.json").read_text(encoding="utf-8")))
    issues = validate_plan(project, people, graph, plan)
    assert [i for i in issues if i.severity == "error"] == []


def test_broken_plan_is_caught():
    project, people, graph = load()
    plan = Plan.model_validate(json.loads((FIX / "plan.broken.json").read_text(encoding="utf-8")))
    codes = {i.code for i in validate_plan(project, people, graph, plan) if i.severity == "error"}
    assert "overlap" in codes
    assert "dep_violation" in codes


def test_metrics_are_computed():
    project, people, graph = load()
    plan = Plan.model_validate(json.loads((FIX / "plan.mock.json").read_text(encoding="utf-8")))
    m = metrics(project, people, graph, plan)
    assert 0.0 <= m.parallelism_score <= 1.0
    assert len(m.critical_path) > 1
