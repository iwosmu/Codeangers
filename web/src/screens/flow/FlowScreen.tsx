import { useMemo, useState } from 'react'
import { GitBranch, ArrowRight, Minus, Plus } from 'lucide-react'
import { Button, Card } from '../../components/ui'
import type { BriefSession } from '../../state/briefs'
import { layoutGraph, NODE_WIDTH, NODE_HEIGHT } from './layout'
import './flow.css'

export function FlowScreen({ session }: { session: BriefSession }) {
  const { flow, team, project, generateFlow, busy } = session
  const [selected, setSelected] = useState<number | null>(null)
  const [zoom, setZoom] = useState(1)
  const [view, setView] = useState<'diagram' | 'list'>('diagram')
  const graph = flow.result?.graph
  const layout = useMemo(() => {
    if (!graph) return null
    try { return layoutGraph(graph.nodes, graph.edges) } catch { return null }
  }, [graph])
  const current = graph?.nodes.find(n => n.id === selected) ?? graph?.nodes[0]
  const ready = Boolean(team.document && project.document)
  const prerequisites = graph?.edges.filter(e => e.to === current?.id).map(e => e.from) ?? []
  const unlocks = graph?.edges.filter(e => e.from === current?.id).map(e => e.to) ?? []
  return <main id="main-content" className="screen screen-flowchart"><div className="screen-heading"><div><p className="eyebrow">04 · Task flow</p><h2>See how the work connects.</h2><p>Turn the two briefs into concrete tasks and prerequisites. Follow the arrows to see what unlocks what.</p></div></div>
    <div className="stack"><Card title="Build the task flow" right={<GitBranch size={18} aria-hidden="true" />}><div className="flow-toolbar"><div><strong>{ready ? 'Both source briefs are ready' : 'Generate both briefs first'}</strong><p className="subtle">{ready ? `${team.document!.structured.members.length} team members · uses the current project.md and team.md` : 'Complete the project and team steps, then return here.'}</p></div><Button disabled={!ready || busy} onClick={() => void generateFlow()}>{flow.busy ? 'Planning and checking…' : flow.result ? 'Regenerate task flow' : 'Generate task flow'}</Button></div>
      {flow.busy && <p role="status" className="notice">Gemini is planning tasks and checking dependencies and capacity. It may make up to three attempts; allow up to a few minutes. You can browse the other steps while it runs.</p>}
      {flow.error && <p role="alert" className="notice">{flow.error}</p>}
    </Card>
    {flow.result && <><div className="flow-stats"><Card title="Tasks"><strong>{graph!.nodes.length}</strong></Card><Card title="Dependencies"><strong>{graph!.edges.length}</strong></Card><Card title="Simulated duration"><strong>{flow.result.validation.makespan_hours}h</strong></Card><Card title="Estimated effort"><strong>{flow.result.validation.total_person_hours} person-hours</strong></Card></div>
      <Card title="Dependency map" right={<span className="pill">{(flow.result.ms / 1000).toFixed(1)}s · {flow.result.rounds} attempt{flow.result.rounds === 1 ? '' : 's'}</span>}>
        <div className="flow-toolbar"><div className="document-actions"><button className={`button button-${view === 'diagram' ? 'primary' : 'secondary'}`} aria-pressed={view === 'diagram'} onClick={() => setView('diagram')}>Flowchart</button><button className={`button button-${view === 'list' ? 'primary' : 'secondary'}`} aria-pressed={view === 'list'} onClick={() => setView('list')}>Task list</button></div>{view === 'diagram' && <div className="flow-zoom"><button className="button button-ghost" aria-label="Zoom out" disabled={zoom <= .5} onClick={() => setZoom(z => Math.max(.5, z - .1))}><Minus size={16} /></button><span>{Math.round(zoom * 100)}%</span><button className="button button-ghost" aria-label="Zoom in" disabled={zoom >= 1.5} onClick={() => setZoom(z => Math.min(1.5, z + .1))}><Plus size={16} /></button><Button kind="ghost" onClick={() => setZoom(1)}>Reset zoom</Button></div>}</div>
        <p className="subtle">Arrows run from prerequisite to dependent task. Tasks in the same column have the same dependency depth; they may still compete for people or skills.</p>
        {view === 'diagram' && layout ? <div className="flow-viewport" tabIndex={0} aria-label="Scrollable task dependency diagram"><div style={{ width: layout.width * zoom, height: layout.height * zoom }}><div className="flow-canvas" style={{ width: layout.width, height: layout.height, transform: `scale(${zoom})` }}>
          <svg width={layout.width} height={layout.height} aria-hidden="true"><defs><marker id="flow-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" /></marker></defs>{graph!.edges.map((edge, i) => {
            const from = layout.nodes.find(n => n.id === edge.from)!, to = layout.nodes.find(n => n.id === edge.to)!
            const x1 = from.x + NODE_WIDTH, y1 = from.y + NODE_HEIGHT / 2, x2 = to.x - 5, y2 = to.y + NODE_HEIGHT / 2
            return <path key={i} d={`M ${x1} ${y1} C ${x1 + 45} ${y1}, ${x2 - 45} ${y2}, ${x2} ${y2}`} fill="none" stroke={edge.from === current?.id || edge.to === current?.id ? '#111' : '#b6b6b1'} strokeWidth={edge.from === current?.id || edge.to === current?.id ? 2.5 : 1.5} markerEnd="url(#flow-arrow)" />
          })}</svg>
          {layout.nodes.map(node => <button key={node.id} className={`flow-node ${node.id === current?.id ? 'selected' : ''}`} style={{ left: node.x, top: node.y, width: NODE_WIDTH, height: NODE_HEIGHT }} onClick={() => setSelected(node.id)} aria-pressed={node.id === current?.id} aria-label={`Task ${node.id}: ${node.label}`}><span className="flow-node-top"><span className="mono">#{node.id}</span><span>{node.group}</span></span><strong>{node.label}</strong><span className="flow-node-bottom">{node.estimated_time_hours}h · {node.people_needed} {node.people_needed === 1 ? 'person' : 'people'} needed</span></button>)}
        </div></div></div> : <div className="table-scroll"><table><thead><tr><th>Task</th><th>Area</th><th>Estimate</th><th>People needed</th><th>Prerequisites</th></tr></thead><tbody>{graph!.nodes.map(node => <tr key={node.id}><td><button className="flow-text-button" onClick={() => setSelected(node.id)}>#{node.id} {node.label}</button></td><td>{node.group}</td><td>{node.estimated_time_hours}h</td><td>{node.people_needed}</td><td>{graph!.edges.filter(e => e.to === node.id).map(e => `#${e.from}`).join(', ') || 'None'}</td></tr>)}</tbody></table></div>}
      </Card>
      {current && <Card title={`#${current.id} · ${current.label}`} right={<span className="pill">{current.group}</span>}><p className="flow-description">{current.title}</p><div className="flow-details"><div><h4>Prerequisites</h4>{prerequisites.length ? prerequisites.map(id => <button className="flow-text-button" key={id} onClick={() => setSelected(id)}>#{id} {graph!.nodes.find(n => n.id === id)?.label}</button>) : <p className="subtle">No task prerequisites. Eligible to start when people are available.</p>}</div><div><h4>Unlocks</h4>{unlocks.length ? unlocks.map(id => <button className="flow-text-button" key={id} onClick={() => setSelected(id)}><ArrowRight size={14} /> #{id} {graph!.nodes.find(n => n.id === id)?.label}</button>) : <p className="subtle">No dependent tasks.</p>}</div><div><h4>Effort & ownership</h4><p>{current.estimated_time_hours} hours with {current.people_needed} {current.people_needed === 1 ? 'person' : 'people'}.</p><p className="subtle">People are not assigned yet. These are proposed estimates.</p></div></div></Card>}
      <Card title="Validation & assumptions"><p>Dependencies are acyclic and reference existing tasks. Headcounts fit the supplied team size.</p><p className="subtle">The duration and utilisation simulation checks headcount, not named availability or skill conflicts. Review estimates, scope, and the deadline with your team.</p><p className="subtle">Simulated idle capacity: {Math.round(flow.result.validation.idle_fraction * 100)}%.</p>{flow.result.validation.warnings.length > 0 && <ul>{flow.result.validation.warnings.map((warning, i) => <li key={i}>{warning}</li>)}</ul>}</Card>
    </>}
    {!flow.result && !flow.busy && <div className="empty"><div><GitBranch size={28} aria-hidden="true" /><strong style={{ display: 'block' }}>Your task flow will appear here</strong><span className="subtle">Generate the graph to explore tasks, dependencies, and effort.</span></div></div>}
    </div></main>
}
