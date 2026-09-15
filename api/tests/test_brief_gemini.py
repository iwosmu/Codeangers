import asyncio
from types import SimpleNamespace
import pytest
from google import genai
from google.genai import types
from app.brief_schemas import ProductSetup, ProjectBrief, gemini_schema
from app.envelope import ApiError
from app.services import brief_files
from app.services.brief_files import Source, Asset
from app.services.gemini import generate_brief
from test_briefs import project_fixture


@pytest.mark.parametrize('fail_generation,fail_delete', [(False,False),(True,False),(True,True)])
def test_large_upload_deleted_even_on_generation_failure(monkeypatch,fail_generation,fail_delete):
    events=[]
    monkeypatch.setattr(brief_files,'INLINE_LIMIT',3)
    class FakeClient:
        def __init__(self,**kwargs): self.aio=self;self.files=self;self.models=self
        async def __aenter__(self): return self
        async def __aexit__(self,*args): events.append('closed')
        async def upload(self,*,file,config):
            assert file.read()==b'large'
            events.append('upload')
            return types.File(name='files/test',uri='https://generativelanguage.googleapis.com/v1beta/files/test',state=types.FileState.PROCESSING)
        async def get(self,*,name):
            events.append('ready')
            return types.File(name=name,uri='https://generativelanguage.googleapis.com/v1beta/files/test',state=types.FileState.ACTIVE)
        async def delete(self,*,name):
            assert name=='files/test';events.append('delete')
            if fail_delete: raise RuntimeError('temporary deletion failure')
        async def generate_content(self,*,model,contents,config):
            events.append('generate')
            assert model=='gemini-3.8-flash' and config.temperature is None
            assert config.response_json_schema['type']=='object'
            assert any(part.inline_data and part.inline_data.data==b'abc' for part in contents)
            assert any(part.file_data for part in contents)
            if fail_generation: raise RuntimeError('synthetic failure')
            return SimpleNamespace(text=project_fixture().model_dump_json())
    monkeypatch.setattr(genai,'Client',FakeClient)
    # This test never uses a network key, including in a clean checkout.
    monkeypatch.setattr('app.services.gemini.settings', lambda: SimpleNamespace(gemini_api_key='synthetic',gemini_model='gemini-3.8-flash'))
    warnings=[]
    sources=[Source('p','media',assets=[Asset(b'abc','image/png'),Asset(b'large','image/png')])]
    async def execute(): return await generate_brief('project',ProjectBrief,ProductSetup(),sources,warnings=warnings)
    if fail_generation:
        with pytest.raises(ApiError): asyncio.run(execute())
    else:
        result,_=asyncio.run(execute());assert result.one_liner.text=='Reduce food waste.'
    assert events==['upload','ready','generate','delete']+(['delete'] if fail_delete else [])+['closed']
    assert bool(warnings)==fail_delete


def test_generation_schema_is_compact_but_local_schema_is_strict():
    schema=gemini_schema(ProjectBrief)
    assert '$defs' not in schema
    assert schema['properties']['problem']['properties']['text']['type']=='string'
    assert 'Maximum characters: 1000' in schema['properties']['problem']['properties']['text']['description']
    assert 'Minimum items: 3' in schema['properties']['open_questions']['description']
    assert 'maxLength' not in schema['properties']['problem']['properties']['text']
    assert 'source_notes' in schema['required']
    assert ProjectBrief.model_json_schema()['additionalProperties'] is False


def test_invalid_response_reports_field_without_private_value(monkeypatch):
    private_value = 'PRIVATE CV CONTENT ' * 100
    class FakeClient:
        def __init__(self, **kwargs): self.aio = self; self.models = self
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def generate_content(self, **kwargs):
            result = project_fixture()
            result.problem.text = private_value
            return SimpleNamespace(text=result.model_dump_json())
    monkeypatch.setattr(genai, 'Client', FakeClient)
    monkeypatch.setattr('app.services.gemini.settings', lambda: SimpleNamespace(gemini_api_key='synthetic', gemini_model='gemini-3.8-flash'))
    with pytest.raises(ApiError) as caught:
        asyncio.run(generate_brief('project', ProjectBrief, ProductSetup(), []))
    assert 'problem.text (string_too_long)' in caught.value.message
    assert 'PRIVATE CV CONTENT' not in caught.value.message
