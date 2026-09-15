"""Opt-in Gemini smoke test with synthetic inputs only. Run from any directory."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from brief_fixtures import request_data, uploads

parser = argparse.ArgumentParser()
parser.add_argument('--live', action='store_true', help='Makes two paid/quota-consuming Gemini calls with fictional CVs')
parser.add_argument('--export-fixtures', type=Path, help='Write synthetic CV files here for manual browser testing')
parser.add_argument('--output', type=Path, help='Save generated synthetic Markdown here for review')
args = parser.parse_args()
if args.export_fixtures:
    args.export_fixtures.mkdir(parents=True,exist_ok=True)
    for _,(name,data,_) in uploads(): (args.export_fixtures/name).write_bytes(data)
if not args.live: sys.exit(0)
from fastapi.testclient import TestClient
from app.main import app
start=time.perf_counter()
with TestClient(app) as client:
    response=client.post('/api/briefs', data={'input':json.dumps(request_data())}, files=uploads())
elapsed=time.perf_counter()-start
print('HTTP',response.status_code,'elapsed',round(elapsed,2),'seconds')
body=response.json()
if not body.get('ok'):
    print(body['error']['message']);sys.exit(1)
failed=False
for kind,document in body['data'].items():
    if document.get('error'):
        print(kind,document['error']);failed=True;continue
    markdown=document['markdown']
    print(kind,'generated',len(markdown),'characters',document.get('warnings'))
    if args.output:
        args.output.mkdir(parents=True,exist_ok=True)
        (args.output/f'{kind}.md').write_text(markdown)
    if kind=='project':
        questions=markdown.split('## Open questions\n')[1].split('## Source notes')[0]
        count=sum(line.startswith('- ') for line in questions.splitlines())
        print('Thin-input open questions:',count)
        if count<8: failed=True
if elapsed>=60: print('60-second target not met on this run');failed=True
sys.exit(1 if failed else 0)
