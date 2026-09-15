import { readFile } from 'node:fs/promises'
import test from 'node:test'
import assert from 'node:assert/strict'
import ts from 'typescript'
const source = await readFile(new URL('../src/screens/flow/layout.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } })
const { layoutGraph, NODE_WIDTH, NODE_HEIGHT } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)
const nodes = [3, 1, 2, 4].map(id => ({ id, label: `Task ${id}` }))
await test('fork and join layout follows edges regardless of input order', () => {
  const layout = layoutGraph(nodes, [{ from: 1, to: 3 }, { from: 2, to: 3 }, { from: 3, to: 4 }])
  const byId = Object.fromEntries(layout.nodes.map(n => [n.id, n]))
  assert.equal(byId[1].x, byId[2].x)
  assert.notEqual(byId[1].y, byId[2].y)
  assert.ok(byId[3].x > byId[2].x)
  assert.ok(byId[4].x > byId[3].x)
  assert.ok(layout.nodes.every(n => n.x + NODE_WIDTH <= layout.width && n.y + NODE_HEIGHT <= layout.height))
})
await test('multiple dependency depths do not overlap nodes', () => {
  const layout = layoutGraph(nodes, [{ from: 1, to: 2 }, { from: 2, to: 3 }, { from: 1, to: 3 }])
  assert.equal(layout.nodes.find(n => n.id === 3).column, 2)
  for (const a of layout.nodes) for (const b of layout.nodes) {
    if (a.id !== b.id) assert.ok(Math.abs(a.x - b.x) >= NODE_WIDTH || Math.abs(a.y - b.y) >= NODE_HEIGHT)
  }
})
await test('bad edges and cycles fail without hanging the UI', () => {
  assert.throws(() => layoutGraph(nodes, [{ from: 99, to: 1 }]), /missing/)
  assert.throws(() => layoutGraph(nodes, [{ from: 1, to: 2 }, { from: 2, to: 1 }]), /cycle/)
})
await test('downward layout preserves dependencies and keeps parallel tasks apart', () => {
  const layout = layoutGraph(nodes, [{ from: 1, to: 3 }, { from: 2, to: 3 }, { from: 3, to: 4 }], 'vertical')
  const byId = Object.fromEntries(layout.nodes.map(n => [n.id, n]))
  assert.equal(byId[1].y, byId[2].y)
  assert.notEqual(byId[1].x, byId[2].x)
  assert.ok(byId[3].y > byId[2].y)
  assert.ok(byId[4].y > byId[3].y)
  assert.ok(layout.nodes.every(n => n.x + NODE_WIDTH <= layout.width && n.y + NODE_HEIGHT <= layout.height))
})
await test('parallel branches follow their prerequisites instead of crossing by input order', () => {
  const layout = layoutGraph([1, 2, 3, 4].map(id => ({ id, label: `Task ${id}` })), [{ from: 1, to: 4 }, { from: 2, to: 3 }])
  const byId = Object.fromEntries(layout.nodes.map(n => [n.id, n]))
  assert.equal(byId[1].y, byId[4].y)
  assert.equal(byId[2].y, byId[3].y)
})
