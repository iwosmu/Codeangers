from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from google.genai import types

from app.main import app
from app.routers import task_flow
from app.task_planner import PlannerConfig, PlanningError, TaskPlanner
from app.task_planner.graph import levels
from app.task_planner.validation import validate_graph


def graph():
    return {"nodes": [
        {"id": 1, "label": "Build API", "title": "Implement the endpoint.", "group": "backend", "estimated_time_hours": 2, "people_needed": 1},
        {"id": 2, "label": "Build UI", "title": "Implement the interface.", "group": "frontend", "estimated_time_hours": 2, "people_needed": 1},
        {"id": 3, "label": "Integrate", "title": "Verify the user flow.", "group": "testing", "estimated_time_hours": 1, "people_needed": 2},
    ], "edges": [{"from": 1, "to": 3}, {"from": 2, "to": 3}]}


def planner_with(*outputs):
    planner = TaskPlanner(client=SimpleNamespace(), config=PlannerConfig(max_fix_rounds=1))
    turns = iter(outputs)
    calls = []
    def generate(contents, schema, **kwargs):
        calls.append(list(contents))
        return next(turns), types.Content(role="model", parts=[types.Part.from_text(text="{}")] )
    planner._generate = generate
    return planner, calls


def test_parallel_graph_and_metrics():
    result = validate_graph(graph(), 2)
    assert result.ok
    assert result.makespan_hours == 3
    assert result.total_person_hours == 6
    assert result.idle_fraction == 0
    assert levels(graph()) == {1: 0, 2: 0, 3: 1}


@pytest.mark.parametrize("change", [
    lambda g: g["edges"].append({"from": 3, "to": 1}),
    lambda g: g["edges"].append({"from": 99, "to": 1}),
    lambda g: g["nodes"][1].update(id=1),
    lambda g: g["nodes"][0].update(people_needed=3),
    lambda g: g["nodes"][0].update(people_needed="one"),
    lambda g: g["nodes"][0].update(estimated_time_hours=True),
    lambda g: g["nodes"][0].update(label=[]),
    lambda g: g["nodes"][0].update(title=None),
])
def test_invalid_graph_rejected_without_crashing(change):
    data = graph(); change(data)
    assert not validate_graph(data, 2).ok


def test_planner_repairs_and_preserves_model_turn():
    invalid = graph(); invalid["edges"].append({"from": 3, "to": 1})
    planner, calls = planner_with(invalid, graph())
    result = planner.plan("Project", "Team", 2)
    assert result.ok and result.rounds == 2
    assert len(calls) == 2
    assert "confirmed team size is 2" in calls[0][0].parts[0].text
    assert calls[1][1].role == "model"
    assert "cycle" in calls[1][2].parts[0].text


def test_exhausted_malformed_output_is_a_failed_result():
    planner, _ = planner_with({"nodes": [{"id": 1}], "edges": []}, {"nodes": [{"id": 1}], "edges": []})
    result = planner.plan("Project", "Team", 2)
    assert not result.ok and result.tasks == []


def test_route_passes_both_briefs_and_returns_validated_graph(monkeypatch):
    def run(body):
        assert body.project_md == "Project brief"
        assert body.team_md == "Team brief"
        assert body.team_size == 2
        planner, _ = planner_with(graph())
        return planner.plan(body.project_md, body.team_md, body.team_size)
    monkeypatch.setattr(task_flow, "generate_flow", run)
    with TestClient(app) as client:
        response = client.post('/api/task-graph', json={"project_md": "Project brief", "team_md": "Team brief", "team_size": 2})
    assert response.status_code == 200
    body = response.json()
    assert body['ok'] and body['data']['validation']['ok']
    assert body['data']['tasks'][2]['prerequisites'] == [1, 2]
    assert response.headers['cache-control'] == 'no-store'


@pytest.mark.parametrize('patch', [{"team_size": 9}, {"team_size": True}, {"project_md": "  "}, {"team_md": ""}, {"extra": "ignored?"}])
def test_route_invalid_inputs_never_call_model(monkeypatch, patch):
    monkeypatch.setattr(task_flow, "generate_flow", lambda body: pytest.fail("Must not call Gemini"))
    with TestClient(app) as client:
        response = client.post('/api/task-graph', json={"project_md": "Project", "team_md": "Team", "team_size": 2, **patch})
    assert response.status_code == 400
    assert response.json()['error']['code'] == 'bad_input'


def test_route_rejects_failed_validation(monkeypatch):
    planner, _ = planner_with({"nodes": [], "edges": []}, {"nodes": [], "edges": []})
    monkeypatch.setattr(task_flow, "generate_flow", lambda body: planner.plan(body.project_md, body.team_md, body.team_size))
    with TestClient(app) as client:
        response = client.post('/api/task-graph', json={"project_md": "Project", "team_md": "Team", "team_size": 2})
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'plan_invalid'


def test_model_error_does_not_echo_documents(monkeypatch):
    def fail(body): raise PlanningError('private CV content')
    monkeypatch.setattr(task_flow, "generate_flow", fail)
    with TestClient(app) as client:
        response = client.post('/api/task-graph', json={"project_md": "Project", "team_md": "Team", "team_size": 2})
    assert response.status_code == 502
    assert 'private CV content' not in response.text


def test_model_calls_are_bounded_and_use_structured_output():
    import json
    captured = {}
    def generate_content(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(candidates=[SimpleNamespace(finish_reason=types.FinishReason.STOP, content=types.Content(role='model', parts=[types.Part.from_text(text='{}')]))], text=json.dumps(graph()))
    planner = TaskPlanner(client=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))
    result = planner.plan('Project', 'Team', 2)
    assert result.ok
    cfg = captured['config']
    assert cfg.http_options.timeout == 60000
    assert cfg.http_options.retry_options.attempts == 1
    assert cfg.response_mime_type == 'application/json'
    assert cfg.response_json_schema['required'] == ['nodes', 'edges']


def test_worker_closes_client_on_model_failure(monkeypatch):
    closed = []
    fake_client = SimpleNamespace(close=lambda: closed.append(True))
    monkeypatch.setattr(task_flow, '_client', lambda: fake_client)
    class FailingPlanner:
        def __init__(self, **kwargs): pass
        def plan(self, *args): raise PlanningError('failed')
    monkeypatch.setattr(task_flow, 'TaskPlanner', FailingPlanner)
    with pytest.raises(PlanningError):
        task_flow.generate_flow(task_flow.FlowInput(project_md='Project', team_md='Team', team_size=2))
    assert closed == [True]


@pytest.mark.parametrize('cycle', [False, True])
def test_application_reports_idle_capacity_but_still_rejects_cycles(monkeypatch, cycle):
    import json
    data = graph()
    data['nodes'][0]['people_needed'] = 2
    data['nodes'][1]['people_needed'] = 3
    data['nodes'][2].update(people_needed=1, estimated_time_hours=8)
    if cycle:
        data['edges'].append({'from': 3, 'to': 1})
    def generate_content(**kwargs):
        return SimpleNamespace(candidates=[SimpleNamespace(finish_reason=types.FinishReason.STOP, content=types.Content(role='model', parts=[types.Part.from_text(text=json.dumps(data))]))], text=json.dumps(data))
    monkeypatch.setattr(task_flow, '_client', lambda: SimpleNamespace(models=SimpleNamespace(generate_content=generate_content), close=lambda: None))
    result = task_flow.generate_flow(task_flow.FlowInput(project_md='Project', team_md='Team', team_size=5))
    assert result.ok is not cycle
    if not cycle:
        assert result.validation.idle_fraction > .25
        assert any('idle capacity' in warning for warning in result.validation.warnings)
