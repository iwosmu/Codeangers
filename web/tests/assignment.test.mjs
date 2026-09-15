import { readFile } from 'node:fs/promises'
import test from 'node:test'
import assert from 'node:assert/strict'
import ts from 'typescript'
const source = await readFile(new URL('../src/screens/flow/assignment.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } })
const { taskFitLabel, currentAssignment } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)
const fit = { task_id: 1, team_missing_skills: ['Vue'], matches: [{ member_id: 'm1', match: 'adjacent' }] }
test('missing skill is visible as learning needed, never a direct match', () => {
  assert.equal(taskFitLabel(fit, ['m1']), 'Learning needed')
  assert.equal(taskFitLabel({ ...fit, team_missing_skills: [], matches: [{ member_id: 'm1', match: 'unconfirmed' }] }, ['m1']), 'Fit unconfirmed')
})
test('manual replacement removes the old fit claim and invalidates the schedule', () => {
  assert.equal(taskFitLabel(fit, ['m2']), 'Owner changed · review fit')
  assert.equal(taskFitLabel(fit, []), 'Owner changed · review fit')
  assert.equal(currentAssignment({ owners: { 1: ['m1', 'm2'] } }, { 1: ['m2', 'm1'] }), true)
  assert.equal(currentAssignment({ owners: { 1: ['m1'] } }, { 1: ['m2'] }), false)
  assert.equal(currentAssignment(undefined, {}), false)
})
