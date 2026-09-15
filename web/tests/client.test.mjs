import { readFile } from 'node:fs/promises'
import test from 'node:test'
import assert from 'node:assert/strict'
import ts from 'typescript'

// Exercise the actual browser transport without a browser or a Gemini request.
const source = await readFile(new URL('../src/api/client.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } })
const { api, ApiFailure } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)
const inputs = {
  setup: { name: 'Synthetic test', context: '', constraints: '' },
  members: [{ id: 'm1', label: 'Alex', text: 'Python' }, { id: 'm2', label: '', text: '', file: new File(['CV'], 'cv.pdf', { type: 'application/pdf' }) }],
  projectText: '', projectFiles: [new File(['# PRD'], 'project.md'), new File(['image'], 'note.png')],
}
const document = { filename: 'project.md', markdown: '# Project', schema_version: '1.0', structured: {}, sources: [], warnings: [], ms: 10 }
const envelope = data => Response.json({ ok: true, data, warnings: [], meta: {} })

await test('project-only request sends attachments without CVs or members', async t => {
  t.mock.method(globalThis, 'fetch', async (url, init) => {
    assert.equal(url, '/api/briefs/project')
    assert.deepEqual([...init.body.keys()], ['input', 'project', 'project'])
    assert.deepEqual(JSON.parse(init.body.get('input')), { setup: inputs.setup, project_text: '' })
    assert.deepEqual(init.body.getAll('project').map(f => f.name), ['project.md', 'note.png'])
    assert.equal(init.headers, undefined) // Browser must supply the multipart boundary.
    return envelope(document)
  })
  assert.equal((await api.project(inputs)).markdown, '# Project')
})

await test('team request supports 2, 3, 5, and 8 members and stable CV ownership', async t => {
  let expected
  t.mock.method(globalThis, 'fetch', async (url, init) => {
    assert.equal(url, '/api/briefs/team')
    const body = JSON.parse(init.body.get('input'))
    assert.equal(body.members.length, expected)
    assert.equal(body.members[1].id, 'm2')
    assert.equal(body.members[1].file, undefined)
    assert.equal(init.body.get('cv:m2').name, 'cv.pdf')
    assert.equal(init.body.has('project'), false)
    assert.equal(body.project_text, undefined)
    return envelope({ ...document, filename: 'team.md' })
  })
  for (expected of [2, 3, 5, 8]) {
    const members = [...inputs.members, ...Array.from({ length: expected - 2 }, (_, i) => ({ id: `m${i + 3}`, label: '', text: 'SQL' }))]
    await api.team({ ...inputs, members })
  }
})

await test('HTTP validation error preserves actionable backend message', async t => {
  t.mock.method(globalThis, 'fetch', async () => Response.json({ ok: false, error: { code: 'bad_input', message: 'Add a CV for m2.', retryable: false } }, { status: 400 }))
  await assert.rejects(api.team(inputs), error => error instanceof ApiFailure && error.message === 'Add a CV for m2.' && !error.retryable)
})

await test('HTTP 200 document failure is surfaced, never replaced with demo content', async t => {
  t.mock.method(globalThis, 'fetch', async () => envelope({ error: { code: 'model_timeout', message: 'Retry with smaller files.', retryable: true }, warnings: ['Cleanup note'] }))
  await assert.rejects(api.project(inputs), error => error.code === 'model_timeout' && error.message.includes('Cleanup note'))
})

await test('network failure and non-JSON server failure do not produce documents', async t => {
  const fetchMock = t.mock.method(globalThis, 'fetch', async () => { throw new Error('offline') })
  await assert.rejects(api.project(inputs), error => error.code === 'network')
  fetchMock.mock.mockImplementation(async () => new Response('Proxy unavailable', { status: 502 }))
  await assert.rejects(api.project(inputs), error => error.code === 'unavailable')
})

await test('caller abort signal reaches fetch', async t => {
  const controller = new AbortController()
  t.mock.method(globalThis, 'fetch', async (_, init) => { assert.equal(init.signal, controller.signal); return envelope(document) })
  await api.project(inputs, controller.signal)
})

await test('task planner receives the actual Markdown pair, team size, and abort signal', async t => {
  const controller = new AbortController()
  t.mock.method(globalThis, 'fetch', async (url, init) => {
    assert.equal(url, '/api/task-graph')
    assert.deepEqual(JSON.parse(init.body), { project_md: '# Project', team_md: '# Team', team_size: 5 })
    assert.equal(init.headers['content-type'], 'application/json')
    assert.equal(init.signal, controller.signal)
    return envelope({ graph: { nodes: [], edges: [] }, validation: { ok: true } })
  })
  assert.equal((await api.taskGraph('# Project', '# Team', 5, controller.signal)).validation.ok, true)
})

await test('GitHub preview and export send the same reviewed data with a separate credential header', async t => {
  const input = { repository: 'example/demo', export_id: 'same-id', tasks: [{ id: 1, owners: ['m2'] }] }
  const paths = []
  t.mock.method(globalThis, 'fetch', async (url, init) => {
    paths.push(url)
    assert.equal(init.headers['x-github-token'], 'session-token')
    assert.deepEqual(JSON.parse(init.body), input)
    assert.equal(init.body.includes('session-token'), false)
    return envelope({ complete: false, issues: [{ key: 'parent', number: 12 }], error: 'Retry' })
  })
  await api.githubPreview(input, 'session-token')
  assert.equal((await api.githubExport(input, 'session-token')).complete, false)
  assert.deepEqual(paths, ['/api/github/preview', '/api/github/export'])
})
