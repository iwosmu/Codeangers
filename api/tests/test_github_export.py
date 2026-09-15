from copy import deepcopy
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.main import app
from app.brief_schemas import Claim, Evidence
from app.envelope import ApiError
from app.routers.github_export import ExportInput, GitHubFailure, export
from app.services.brief_validation import validate_team
from app.services.brief_markdown import render_team
from test_briefs import team_fixture, text_inputs


def payload():
    return dict(repository='example/demo', export_id=str(uuid4()), title='Demo plan', summary='A tiny inventory app.',
                members=[dict(id='m1', login='alex-example'), dict(id='m2', login='sam-example')],
                tasks=[dict(id=1, title='Build API', description='Provide inventory endpoints.', hours=2, people=1, owners=['m2'], prerequisites=[]),
                       dict(id=2, title='Build UI', description='Display inventory.', hours=2, people=1, owners=['m1'], prerequisites=[1])])


class FakeGitHub:
    def __init__(self):
        self.issues = []; self.children = []; self.calls = []; self.fail = None; self.lost_create = False; self.silent_assignee = False
    def call(self, method, path, body=None):
        self.calls.append((method, path, deepcopy(body)))
        if self.fail and self.fail(method, path):
            self.fail = None
            raise GitHubFailure('Synthetic outage')
        if path == '/user': return {'login': 'tester'}
        if path == '/repos/example/demo': return {'has_issues': True, 'archived': False, 'full_name': 'example/demo', 'private': True}
        if '/assignees/' in path: return None
        if '/sub_issues' in path:
            if method == 'POST': self.children.append(body['sub_issue_id']); return {}
            return [{'id': i} for i in self.children]
        if method == 'GET': return deepcopy(self.issues)
        if method == 'POST':
            number = len(self.issues) + 10
            issue = dict(id=number + 100, number=number, html_url=f'https://github.com/example/demo/issues/{number}', **body)
            issue['assignees'] = [{'login': login} for login in body['assignees']]
            self.issues.append(issue)
            if self.lost_create:
                self.lost_create = False
                raise GitHubFailure('Lost create response')
            return deepcopy(issue)
        if method == 'PATCH':
            issue = next(i for i in self.issues if str(i['number']) == path.split('/')[-1])
            issue['body'] = body['body']
            issue['assignees'] = [] if self.silent_assignee else [{'login': login} for login in body['assignees']]
            return deepcopy(issue)
        raise AssertionError((method, path))


def test_hierarchy_assignees_links_and_replay():
    client = FakeGitHub(); body = ExportInput(**payload())
    result = export(client, body)
    assert result['complete'] and len(result['issues']) == 3
    assert client.children == [111, 112]
    assert client.issues[1]['assignees'] == [{'login': 'sam-example'}]
    assert 'https://github.com/example/demo/issues/11' in client.issues[2]['body']
    assert 'T1 --> T2' in client.issues[0]['body']
    assert export(client, body)['complete']
    assert len(client.issues) == 3 and client.children == [111, 112]


@pytest.mark.parametrize('phase', ['create', 'attach', 'patch'])
def test_partial_failure_can_resume_without_duplicate_issues(phase):
    client = FakeGitHub(); body = ExportInput(**payload())
    if phase == 'create': client.lost_create = True
    if phase == 'attach': client.fail = lambda method, path: method == 'POST' and '/sub_issues' in path
    if phase == 'patch': client.fail = lambda method, path: method == 'PATCH'
    assert not export(client, body)['complete']
    assert export(client, body)['complete']
    assert len(client.issues) == 3 and len(client.children) == 2


def test_reject_changed_snapshot_and_silent_assignee_omission():
    client = FakeGitHub(); body = ExportInput(**payload()); client.silent_assignee = True
    assert 'assignee' in export(client, body)['error']
    body.title = 'Changed plan'
    assert 'different content' in export(client, body)['error']
    assert len(client.issues) == 3


@pytest.mark.parametrize('change', ['cycle', 'missing_owner', 'duplicate_login', 'fake_owner', 'bad_repo', 'duplicate_task'])
def test_invalid_export_inputs(change):
    data = payload()
    if change == 'cycle': data['tasks'][0]['prerequisites'] = [2]
    if change == 'missing_owner': data['tasks'][0]['owners'] = []
    if change == 'duplicate_login': data['members'][1]['login'] = 'ALEX-EXAMPLE'
    if change == 'fake_owner': data['tasks'][0]['owners'] = ['m8']
    if change == 'bad_repo': data['repository'] = '../secrets'
    if change == 'duplicate_task': data['tasks'][1]['id'] = 1
    with pytest.raises(ValidationError): ExportInput(**data)


def test_preflight_failure_writes_nothing():
    client = FakeGitHub(); client.fail = lambda method, path: '/assignees/' in path
    result = export(client, ExportInput(**payload()))
    assert not result['complete'] and not client.issues


def test_api_requires_token_and_preview_never_writes(monkeypatch):
    from app.routers import github_export
    fake = FakeGitHub(); monkeypatch.setattr(github_export, 'GitHub', lambda token: fake)
    client = TestClient(app)
    assert client.post('/api/github/export', json=payload()).status_code == 400
    response = client.post('/api/github/preview', json=payload(), headers={'x-github-token': 'test-only'})
    assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
    assert len(response.json()['data']['issues']) == 3
    assert all(method == 'GET' for method, _, _ in fake.calls)
    assert 'test-only' not in response.text


@pytest.mark.parametrize('url,username,valid', [
    ('https://github.com/alex-example', 'alex-example', True),
    ('github.com/Alex-Example/', 'alex-example', True),
    ('https://github.com/company/repo', 'company', False),
    ('https://github.com/alex-example', 'invented', False),
    ('https://notgithub.com/alex-example', 'alex-example', False),
])
def test_github_profile_requires_exact_cv_evidence(url, username, valid):
    team = team_fixture(); request, sources = text_inputs()
    sources[0].text += '\n' + url
    team.members[0].evidence.append(Evidence(id='gh', source_id=sources[0].id, source_part='text', location='Profile', quote=url))
    team.members[0].github = Claim(text=username, evidence_ids=['gh'])
    if valid:
        validate_team(team, request, sources)
        assert f'GitHub: {username} [m1:gh]' in render_team(team, request, sources)
    else:
        with pytest.raises(ApiError): validate_team(team, request, sources)


def test_unknown_github_remains_not_stated():
    team = team_fixture(); request, sources = text_inputs()
    assert team.members[0].github.text == 'not stated'
    assert 'GitHub: not stated' in render_team(validate_team(team, request, sources), request, sources)


def test_reconciliation_paginates_before_creating():
    client = FakeGitHub(); body = ExportInput(**payload())
    assert export(client, body)['complete']
    original = client.call
    def paginated(method, path, data=None):
        if method == 'GET' and '?state=all' in path and path.endswith('&page=1'):
            return [{'body': 'unrelated issue'} for _ in range(100)]
        return original(method, path, data)
    client.call = paginated
    assert export(client, body)['complete']
    assert len(client.issues) == 3


def test_scan_limit_never_creates_and_export_api_reports_partial_progress(monkeypatch):
    from app.routers import github_export
    fake = FakeGitHub(); original = fake.call
    def huge(method, path, data=None):
        if method == 'GET' and '?state=all' in path:
            return [{'body': 'unrelated issue'} for _ in range(100)]
        return original(method, path, data)
    fake.call = huge
    assert 'too large' in export(fake, ExportInput(**payload()))['error']
    assert not fake.issues
    fake = FakeGitHub(); fake.fail = lambda method, path: method == 'POST' and '/sub_issues' in path
    monkeypatch.setattr(github_export, 'GitHub', lambda token: fake)
    response = TestClient(app).post('/api/github/export', json=payload(), headers={'x-github-token': 'test-only'})
    assert response.status_code == 200
    result = response.json()['data']
    assert not result['complete'] and len(result['issues']) == 3 and result['error']
