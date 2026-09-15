from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.brief_schemas import AREAS, TeamBrief
from app.routers import task_assignment as route
from app.task_assigner import AssignerConfig, TaskAssigner
from app.task_assigner.fit import validate_fit
from test_task_assigner import StubClient, response


def team_data():
    def member(mid, name, skill):
        claim = {'text': skill, 'evidence_ids': ['e1']}
        return dict(id=mid, cv_name={'text': name, 'evidence_ids': ['e1']},
                    evidence=[dict(id='e1', source_id=f'cv:{mid}', source_part='text', location='CV project', quote=f'{name} built a project using {skill}.')],
                    roles=[], strengths=[claim], gaps=[{'area': 'Availability', 'relevance': 'not stated'}, {'area': 'Preferences', 'relevance': 'not stated'}],
                    stack=[claim], experience=claim, working_style=[],
                    coverage=[{'area': a, 'level': 'none', 'evidence_ids': []} for a in AREAS])
    return {'members': [member('m1', 'Alex', 'React'), member('m2', 'Sam', 'Python')], 'open_questions': ['Availability?', 'Preferences?', 'Other experience?']}


def tasks_data():
    return [dict(id=1, name='Build Vue screen', description='Build an interactive Vue screen. Requires Vue.', group='frontend', prerequisites=[], estimated_time_hours=2, people_needed=1),
            dict(id=2, name='Write Python parser', description='Write a Python CSV parser. Requires Python.', group='backend', prerequisites=[], estimated_time_hours=2, people_needed=1)]


def output_data():
    return {'tasks': [{'task_id': 1, 'task_name': 'Build Vue screen', 'assigned_to': ['Alex']}, {'task_id': 2, 'task_name': 'Write Python parser', 'assigned_to': ['Sam']}],
            'people': [{'member_id': 'm1', 'name': 'Alex', 'task_ids': [1]}, {'member_id': 'm2', 'name': 'Sam', 'task_ids': [2]}], 'notes': [],
            'fit': [dict(task_id=1, required_skills=['Vue'], team_missing_skills=['Vue'], matches=[dict(member_id='m1', match='adjacent', matched_skills=[], missing_skills=['Vue'], evidence_ids=['e1'], reason='React component work is transferable; Vue experience is not stated.', learning_step='Build a small Vue component with reactive state.')]),
                    dict(task_id=2, required_skills=['Python'], team_missing_skills=[], matches=[dict(member_id='m2', match='direct', matched_skills=['Python'], missing_skills=[], evidence_ids=['e1'], reason='Python is explicit in the CV project.', learning_step='')])]}


def run_with(payloads):
    client = StubClient([response(p) for p in payloads])
    result = TaskAssigner(client=client, config=AssignerConfig(max_fix_rounds=1)).assign('Team', tasks_data(), members=[{'id': 'm1', 'name': 'Alex'}, {'id': 'm2', 'name': 'Sam'}], evidence_profiles=TeamBrief.model_validate(team_data()).members)
    return result, client


def test_adjacent_skill_is_not_claimed_as_direct_and_has_evidence():
    result, client = run_with([output_data()])
    assert result.ok and result.assignment['fit'][0]['matches'][0]['missing_skills'] == ['Vue']
    assert 'fit' in client.calls[0]['config'].response_json_schema['required']
    assert client.calls[0]['config'].http_options.timeout == 60000
    assert client.calls[0]['config'].http_options.retry_options.attempts == 1
    assert 'not a claim' in str(client.calls[0]['config'].system_instruction)


@pytest.mark.parametrize('mutate', [
    lambda a: a['fit'][0]['matches'][0].update(match='direct'),
    lambda a: a['fit'][0]['matches'][0].update(evidence_ids=['other-member-evidence']),
    lambda a: a['fit'][0]['matches'][0].update(learning_step=''),
    lambda a: a['fit'][0]['matches'][0].update(member_id='m8'),
    lambda a: a['fit'][0]['matches'][0].update(matched_skills=['Vue']),
    lambda a: a['fit'][0].update(team_missing_skills=['Docker']),
    lambda a: a['fit'].pop(),
    lambda a: a.update(fit=None),
])
def test_invalid_fit_is_rejected(mutate):
    a = output_data(); mutate(a)
    assert validate_fit(a, TeamBrief.model_validate(team_data()).members, tasks_data())


def test_no_transferable_evidence_stays_unconfirmed():
    a = output_data()
    a['fit'][0]['matches'][0].update(match='unconfirmed', evidence_ids=[], reason='No relevant evidence to compare learning fit.', learning_step='Check interest and try a small supervised exercise.')
    assert not validate_fit(a, TeamBrief.model_validate(team_data()).members, tasks_data())
    a['fit'][0]['matches'][0]['matched_skills'] = ['Vue']
    assert validate_fit(a, TeamBrief.model_validate(team_data()).members, tasks_data())


def test_missing_references_trigger_repair_and_keep_model_turn():
    bad = output_data(); bad['fit'][0]['matches'][0]['evidence_ids'] = ['unknown']
    result, client = run_with([bad, output_data()])
    assert result.ok and result.rounds == 2
    assert client.calls[1]['contents'][1].role == 'model'
    assert 'evidence IDs' in client.calls[1]['contents'][2].parts[0].text


def test_duplicate_names_use_ids_for_ownership():
    a = output_data(); members = [{'id': 'm1', 'name': 'Alex'}, {'id': 'm2', 'name': 'Alex'}]
    a['people'][1]['name'] = 'Alex'; a['tasks'][1]['assigned_to'] = ['Alex']
    team = team_data(); team['members'][1]['cv_name']['text'] = 'Alex'
    result = TaskAssigner(client=StubClient([response(a)])).assign('Team', tasks_data(), members=members, evidence_profiles=TeamBrief.model_validate(team).members)
    assert result.ok
    assert result.assignment['people'][1]['task_ids'] == [2]


def test_route_returns_member_ids_and_evidence_fit(monkeypatch):
    result, _ = run_with([output_data()])
    monkeypatch.setattr(route, 'generate_assignment', lambda body: result)
    with TestClient(app) as client:
        response_ = client.post('/api/task-assignments', json={'team': team_data(), 'tasks': tasks_data()})
    assert response_.status_code == 200
    assert response_.headers['cache-control'] == 'no-store'
    assert response_.json()['data']['owners'] == {'1': ['m1'], '2': ['m2']}
    assert response_.json()['data']['assignment']['fit'][0]['team_missing_skills'] == ['Vue']


@pytest.mark.parametrize('mutate', [
    lambda b: b['tasks'][0].update(people_needed=3),
    lambda b: b['tasks'][0].update(prerequisites=[2]) or b['tasks'][1].update(prerequisites=[1]),
    lambda b: b['team']['members'][1].update(id='m1'),
    lambda b: b['tasks'][0].update(id=True),
    lambda b: b['tasks'].clear(),
    lambda b: b['team']['members'].pop(),
])
def test_invalid_input_never_calls_gemini(monkeypatch, mutate):
    monkeypatch.setattr(route, 'generate_assignment', lambda body: pytest.fail('must not call model'))
    body = {'team': team_data(), 'tasks': tasks_data()}; mutate(body)
    with TestClient(app) as client:
        r = client.post('/api/task-assignments', json=body)
    assert r.status_code == 400


def test_route_model_failure_is_retryable_and_does_not_echo_cv(monkeypatch):
    def fail(body): raise RuntimeError('private CV text')
    monkeypatch.setattr(route, 'generate_assignment', fail)
    with TestClient(app) as client:
        r = client.post('/api/task-assignments', json={'team': team_data(), 'tasks': tasks_data()})
    assert r.status_code == 502 and 'private CV text' not in r.text
    assert r.json()['error']['retryable']


def test_worker_closes_client_and_relaxes_utilization_not_skill_checks(monkeypatch):
    closed = []
    monkeypatch.setattr(route, '_client', lambda: SimpleNamespace(close=lambda: closed.append(True)))
    class Fake:
        def __init__(self, client, config): assert config.max_idle_fraction == 1.0
        def assign(self, *args, **kwargs):
            assert len(kwargs['evidence_profiles']) == 2
            raise RuntimeError('fail')
    monkeypatch.setattr(route, 'TaskAssigner', Fake)
    with pytest.raises(RuntimeError): route.generate_assignment(route.AssignmentInput(team=team_data(), tasks=tasks_data()))
    assert closed == [True]


def test_team_gap_cannot_contradict_exact_evidenced_stack_entry():
    a = output_data(); a['fit'][1]['team_missing_skills'] = ['Python']
    a['fit'][1]['matches'][0].update(match='adjacent', matched_skills=[], missing_skills=['Python'], learning_step='Learn Python.')
    assert any('explicitly evidenced' in e for e in validate_fit(a, TeamBrief.model_validate(team_data()).members, tasks_data()))


def test_eight_members_and_unused_capacity_are_supported():
    team = team_data(); a = output_data()
    for i in range(3, 9):
        p = deepcopy(team['members'][0]); p['id'] = f'm{i}'; p['cv_name']['text'] = f'Person {i}'
        team['members'].append(p)
        a['people'].append({'member_id': f'm{i}', 'name': f'Person {i}', 'task_ids': []})
    profiles = TeamBrief.model_validate(team).members
    result = TaskAssigner(client=StubClient([response(a)]), config=AssignerConfig(max_idle_fraction=1)).assign('Team', tasks_data(), members=[{'id': p.id, 'name': p.cv_name.text} for p in profiles], evidence_profiles=profiles)
    assert result.ok and len(result.members) == 8
    assert result.validation.idle_fraction == .75 and result.validation.warnings


def test_route_rejects_invalid_result_instead_of_applying_owners(monkeypatch):
    a = output_data(); a['fit'] = []
    result, _ = run_with([a, a])
    assert not result.ok
    monkeypatch.setattr(route, 'generate_assignment', lambda body: result)
    with TestClient(app) as client:
        r = client.post('/api/task-assignments', json={'team': team_data(), 'tasks': tasks_data()})
    assert r.status_code == 422 and r.json()['error']['retryable']
    assert 'owners' not in r.json()
