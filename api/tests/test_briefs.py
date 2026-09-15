import asyncio
from copy import deepcopy
from io import BytesIO
import json
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from app.brief_schemas import AREAS, BriefInput, ProjectBrief, TeamBrief
from app.envelope import ApiError
from app.main import app
from app.routers import briefs
from app.services.brief_files import Source, prepare_source
from app.services.brief_markdown import render_team
from app.services.brief_validation import coverage_has_direct_signal, validate_team, validate_project
from brief_fixtures import CVS, docx, png, request_data, uploads


def team_fixture():
    def claim(text): return {'text':text, 'evidence_ids':['e1']}
    return TeamBrief.model_validate({'members': [
        {'id':f'm{i}', 'cv_name':claim('Alex'), 'evidence':[{'id':'e1','source_id':f'cv-m{i}-text','source_part':'text','location':'CV text','quote':'Alex. Built a React dashboard.'}],
         'roles':[claim('Frontend contributor; built a React dashboard.')], 'strengths':[claim('React project')],
         'gaps':[{'area':'Deployment','relevance':'Confirm whether hosting is needed.'}, {'area':'User research','relevance':'Clarify who can validate the idea.'}],
         'stack':[claim('React')], 'experience':claim('One dashboard project'), 'working_style':[],
         'coverage':[{'area':a, 'level':'some' if a=='frontend' else 'none','evidence_ids':['e1'] if a=='frontend' else []} for a in AREAS]}
        for i in range(1,3)], 'open_questions':['When are you available?', 'What do you want to contribute?', 'Who wants to present?']})


def project_fixture():
    unknown={'text':'not stated','source_ids':[]}
    return ProjectBrief.model_validate({**{k:unknown for k in ['problem','target_user','vision','value_proposition','impact']},
        'one_liner':{'text':'Reduce food waste.','source_ids':['project-text']},
        **{k:[] for k in ['must_have','nice_to_have','constraints','success_criteria','contradictions']},
        'open_questions':['Who is it for?', 'What should it deliver?', 'How will impact be measured?'],
        'source_notes':[{'source_id':'setup','contribution':'No setup provided.'}, {'source_id':'project-text','contribution':'Food waste idea.'}]})


def text_inputs():
    request = BriefInput.model_validate({'setup':{},'members':[{'id':f'm{i}','text':'Alex. Built a React dashboard.'} for i in (1,2)],'project_text':'Reduce food waste.'})
    sources=[Source(f'cv-m{i}-text','Pasted CV',f'm{i}','Alex. Built a React dashboard.') for i in (1,2)]
    return request,sources


def test_office_text_and_native_media():
    source=prepare_source('cv-m1-file','cv.docx',docx(CVS[1]),owner='m1')
    assert 'FastAPI' in source.text and 'paragraph' in source.text
    for _, (name,data,_) in uploads()[::2]:
        native=prepare_source('cv-m1-file',name,data,owner='m1')
        assert not native.text and native.assets[0].data == data


@pytest.mark.parametrize('name,data', [('bad.docx',b'not a zip'),('bad.pdf',b'not a pdf'),('empty.txt',b''),('old.doc',b'legacy'),('bad.txt',b'\xff')])
def test_bad_files_are_actionable(name,data):
    with pytest.raises(ApiError) as error: prepare_source('s',name,data,owner='m1')
    assert error.value.code == 'bad_input'


def test_xml_entity_and_zip_expansion_rejected():
    data=BytesIO()
    with ZipFile(data,'w') as z: z.writestr('word/document.xml','<!DOCTYPE doc [<!ENTITY x "malicious">]><doc>&x;</doc>')
    with pytest.raises(ApiError): prepare_source('s','cv.docx',data.getvalue(),owner='m1')


@pytest.mark.parametrize('tamper', ['missing_citation','wrong_owner','fake_quote','missing_member','bad_coverage','fake_asset','invented_tool'])
def test_team_evidence_fails_closed(tamper):
    team=team_fixture(); req,sources=text_inputs(); m=team.members[0]
    if tamper=='missing_citation': m.stack[0].evidence_ids=[]
    if tamper=='wrong_owner': m.evidence[0].source_id='cv-m2-text'
    if tamper=='fake_quote': m.evidence[0].quote='Expert Kubernetes operator'
    if tamper=='missing_member': team.members.pop()
    if tamper=='bad_coverage': m.coverage[1].area='frontend'
    if tamper=='invented_tool': m.stack[0].text='Kubernetes'
    if tamper=='fake_asset': m.evidence[0].source_part='invented-image'
    with pytest.raises(ApiError): validate_team(team,req,sources)


def test_team_renderer_derives_overview_and_escapes_input():
    req,sources=text_inputs(); req.setup.name='<script>alert(1)</script>'
    team=validate_team(team_fixture(),req,sources)
    markdown=render_team(team,req,sources)
    assert '| Frontend | ● [m1:e1] | ● [m2:e1] |' in markdown
    assert '### Overlaps' in markdown and '[m1:e1]' in markdown
    assert '<script>' not in markdown
    assert '### Working-style signals\n\nnot stated' in markdown


def test_project_requires_all_source_notes_and_valid_citations():
    sources=[Source('setup','Setup'),Source('project-text','Description')]
    project=project_fixture(); validate_project(project,sources)
    project.one_liner.source_ids=['imaginary']
    with pytest.raises(ApiError): validate_project(project,sources)
    project=project_fixture(); project.source_notes.pop()
    with pytest.raises(ApiError): validate_project(project,sources)


def test_role_preview_keeps_complete_evidence_available():
    req, sources = text_inputs()
    team = team_fixture()
    passage = 'Alex. Built a React dashboard. ' + 'Documented additional project detail. ' * 25
    team.members[0].evidence[0].quote = passage
    sources[0].text = passage
    markdown = render_team(validate_team(team, req, sources), req, sources)
    role_section = markdown.split('### Likely roles\n', 1)[1].split('### Strengths', 1)[0]
    assert '[m1:e1]' in role_section and '…' in role_section
    assert len(role_section) < 700
    assert passage.strip() in markdown.split('### CV evidence\n', 1)[1]


@pytest.mark.parametrize('area,quote,supported', [
    ('backend', 'Built a Python board-game engine and Minimax bots.', False),
    ('backend', 'Built REST endpoints using FastAPI.', True),
    ('devops', 'Managed Git branches and generated tests with Bash.', False),
    ('devops', 'Validated the adjudicator with a test suite in CI.', True),
    ('devops', 'Deployed an app with Docker.', True),
    ('pitch', 'Group outputs include an oral presentation and my first-author poster.', False),
    ('pitch', 'Set the research direction and secured compute resources.', False),
    ('pitch', 'Taught mathematics and presented solutions clearly.', True),
])
def test_coverage_requires_area_specific_evidence(area, quote, supported):
    assert coverage_has_direct_signal(area, [quote]) is supported


def test_unsupported_coverage_is_withheld_with_reviewable_sources():
    req, sources = text_inputs()
    team = team_fixture()
    cell = next(c for c in team.members[0].coverage if c.area == 'devops')
    cell.level = 'some'; cell.evidence_ids = ['e1']
    validate_team(team, req, sources)
    assert cell.level == 'none' and not cell.evidence_ids
    assert '[m1:e1]' in team._coverage_review_notes[0]
    assert 'Coverage checks to review' in render_team(team, req, sources)
    assert '_coverage_review_notes' not in team.model_dump()


def test_project_only_uses_markdown_and_image_without_cvs_or_text(monkeypatch):
    async def fake(kind, schema, setup, sources, **kwargs):
        assert kind == 'project'
        assert all(source.owner is None for source in sources)
        assert 'reservation' in sources[1].text
        assert sources[2].assets[0].mime == 'image/png'
        result = project_fixture().model_dump()
        result['one_liner'] = {'text': 'A reservation board.', 'source_ids': ['project-file-1']}
        result['source_notes'] = [{'source_id': s.id, 'contribution': 'Supplied project material.'} for s in sources]
        return ProjectBrief.model_validate(result), []
    monkeypatch.setattr(briefs, 'generate_brief', fake)
    with TestClient(app) as client:
        response = client.post('/api/briefs/project', data={'input': json.dumps({'setup': {}})}, files=[
            ('project', ('prd.md', b'# A reservation board\nMust support reservations.', 'text/markdown')),
            ('project', ('notes.png', png('PICKUP AT CAMPUS'), 'image/png')),
        ])
    assert response.status_code == 200
    assert response.json()['data']['filename'] == 'project.md'
    assert 'A reservation board.' in response.json()['data']['markdown']


@pytest.mark.parametrize('count', [2, 3, 5, 8])
def test_team_only_supports_variable_member_counts_without_project(monkeypatch, count):
    calls = []
    async def fake(kind, schema, setup, sources, **kwargs):
        calls.append((kind, len(sources)))
        raise ApiError('model_failed', 'Synthetic stop after successful input parsing.')
    monkeypatch.setattr(briefs, 'generate_brief', fake)
    payload = {'setup': {}, 'members': [{'id': f'm{i}', 'text': 'Alex. Built a React dashboard.'} for i in range(1, count + 1)]}
    with TestClient(app) as client:
        response = client.post('/api/briefs/team', files={'input': (None, json.dumps(payload))})
    assert response.status_code == 200
    assert calls == [('team', count)]


def test_uploads_stay_in_memory_and_calls_are_separate(monkeypatch):
    active=set(); captured={}
    original=briefs.prepare_source
    def prepare(*args,**kwargs): return original(*args,**kwargs)
    monkeypatch.setattr(briefs,'prepare_source',prepare)
    async def fake(kind,schema,setup,sources,**kwargs):
        active.add(kind); captured[kind]=sources
        await asyncio.sleep(0.01)
        assert active=={'team','project'}
        raise ApiError('model_failed','Deliberate fake response')
    monkeypatch.setattr(briefs,'generate_brief',fake)
    # A >1MB text upload would normally roll to disk in Starlette; intercept the buffer state.
    seen=[]
    original_read=briefs.UploadFile.read
    async def read(self,*args):
        seen.append(getattr(self.file,'_rolled',None))
        return await original_read(self,*args)
    monkeypatch.setattr(briefs.UploadFile,'read',read)
    with TestClient(app) as client:
        files=uploads()
        name,data,mime=files[0][1]
        files[0]=(files[0][0],(name,data+b' '*2_000_000,mime))
        response=client.post('/api/briefs',data={'input':json.dumps(request_data())},files=files)
    assert response.status_code==200 and response.headers['cache-control']=='no-store'
    assert all(value is False for value in seen)
    assert all(s.owner for s in captured['team'])
    assert all(s.owner is None for s in captured['project'])
    assert {s.id for s in captured['project']}=={'setup','project-text'}


def test_partial_success_preserves_project(monkeypatch):
    async def fake(kind,*args,**kwargs):
        if kind=='team': raise ApiError('model_failed','Team failed')
        return project_fixture(),[]
    monkeypatch.setattr(briefs,'generate_brief',fake)
    request,_=text_inputs()
    with TestClient(app) as client:
        response=client.post('/api/briefs',data={'input':request.model_dump_json()})
        assert response.status_code==400 # must use multipart, not URL-encoded data
        response=client.post('/api/briefs',files={'input':(None,request.model_dump_json())})
    data=response.json()['data']
    assert data['team']['error']['message']=='Team failed'
    assert data['project']['filename']=='project.md'
    assert '## Open questions' in data['project']['markdown']


@pytest.mark.parametrize('count',[1,9])
def test_team_size_enforced_before_call(monkeypatch,count):
    req=request_data();req['members']=[{'id':f'm{i+1}','text':'CV'} for i in range(count)]
    with TestClient(app) as client:
        response=client.post('/api/briefs',files={'input':(None,json.dumps(req))})
    assert response.status_code==400


def test_markdown_download_roundtrips_exact_content_without_storage():
    markdown='# Example\n\nŹródło: CV → evidence\n\n| Skill | Member |\n| --- | --- |\n| React | ● |\n'
    with TestClient(app) as client:
        for filename in ['team.md','project.md']:
            response=client.post('/api/download/'+filename,data={'markdown':markdown})
            assert response.status_code==200 and response.text==markdown
            assert response.headers['content-disposition']==f'attachment; filename="{filename}"'
            assert response.headers['cache-control']=='no-store'
            assert response.headers['content-type'].startswith('text/markdown')
        assert client.post('/api/download/evil.html',data={'markdown':'hi'}).status_code==400
        assert client.post('/api/download/team.md',data={'markdown':''}).status_code==400
