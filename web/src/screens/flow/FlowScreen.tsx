import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { GitBranch, ArrowRight, ArrowDown, ArrowUpRight, Minus, Plus, Maximize2, Minimize2, Scan, Search, Clock3, Users, Check, X, RotateCw } from 'lucide-react'
import { Button } from '../../components/ui'
import type { BriefSession } from '../../state/briefs'
import { layoutGraph, NODE_WIDTH, NODE_HEIGHT, COLUMN_GAP, PADDING } from './layout'
import './flow.css'
import { GithubExport } from './GithubExport'
import { AssignmentDetails } from './AssignmentDetails'
import { SkillFitDetails } from './SkillFitDetails'
import { taskFitLabel, currentAssignment } from './assignment'

const categoryColours: Record<string, string> = { frontend: '#333333', backend: '#555555', database: '#555555', design: '#666666', testing: '#444444', devops: '#606060', setup: '#606060', docs: '#707070' }
const colour = (group: string) => categoryColours[group.toLowerCase()] ?? '#737373'
const clampZoom = (value: number) => Math.min(1.6, Math.max(.3, value))

export function FlowScreen({ session }: { session: BriefSession }) {
  const { flow, team, project, generateFlow, busy, github } = session
  const [selected, setSelected] = useState<number | null>(null)
  const [zoom, setZoom] = useState(.9)
  const [view, setView] = useState<'diagram' | 'list'>('diagram')
  const [direction, setDirection] = useState<'horizontal' | 'vertical'>('vertical')
  const [query, setQuery] = useState('')
  const [expanded, setExpanded] = useState(false)
  const [focused, setFocused] = useState(false)
  const [panning, setPanning] = useState(false)
  const viewport = useRef<HTMLDivElement>(null)
  const workbench = useRef<HTMLDivElement>(null)
  const expandButton = useRef<HTMLButtonElement>(null)
  const drag = useRef<{ x: number; y: number; left: number; top: number } | null>(null)
  const members = team.document?.structured.members ?? []
  const memberName = (id: string) => { const m = members.find(m => m.id === id); return m?.cv_name.text !== 'not stated' ? m?.cv_name.text : session.inputs.members.find(m => m.id === id)?.label || id }
  const graph = flow.result?.graph
  const layout = useMemo(() => {
    if (!graph) return null
    try { return layoutGraph(graph.nodes, graph.edges, direction) } catch { return null }
  }, [graph, direction])
  const byId = useMemo(() => new Map(layout?.nodes.map(n => [n.id, n]) ?? []), [layout])
  const current = graph?.nodes.find(n => n.id === selected) ?? graph?.nodes[0]
  const ownersCurrent = currentAssignment(session.assignment.result, github.owners)
  const ready = Boolean(team.document && project.document)
  const prerequisites = graph?.edges.filter(e => e.to === current?.id).map(e => e.from) ?? []
  const unlocks = graph?.edges.filter(e => e.from === current?.id).map(e => e.to) ?? []
  const related = new Set([current?.id, ...prerequisites, ...unlocks])
  const matches = graph?.nodes.filter(n => `${n.id} ${n.label} ${n.title} ${n.group}`.toLowerCase().includes(query.toLowerCase())) ?? []
  const matching = new Set(matches.map(n => n.id))
  const groups = [...new Set(graph?.nodes.map(n => n.group) ?? [])]

  const fitLabel = (id: number) => taskFitLabel(session.assignment.result?.assignment.fit.find(f => f.task_id === id), github.owners[id] ?? [])
  function fit() {
    if (!layout || !viewport.current) return
    setZoom(Math.min(1, clampZoom(Math.min((viewport.current.clientWidth - 24) / layout.width, (viewport.current.clientHeight - 24) / layout.height))))
    viewport.current.scrollTo({ left: 0, top: 0 })
  }
  useEffect(() => { setZoom(.9); setQuery(''); setFocused(false) }, [graph])
  useEffect(() => {
    if (!expanded) return
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    workbench.current?.focus()
    const key = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { setExpanded(false); expandButton.current?.focus() }
      if (event.key === 'Tab' && workbench.current) {
        const elements = Array.from(workbench.current.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), [tabindex="0"]')).filter(el => el.getClientRects().length)
        const first = elements[0], last = elements[elements.length - 1]
        if (event.shiftKey && (document.activeElement === first || document.activeElement === workbench.current)) { event.preventDefault(); last?.focus() }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
      }
    }
    document.addEventListener('keydown', key)
    return () => { document.body.style.overflow = previous; document.removeEventListener('keydown', key) }
  }, [expanded])
  function changeZoom(next: number) {
    const el = viewport.current
    const value = clampZoom(next)
    const centerX = el ? (el.scrollLeft + el.clientWidth / 2) / zoom : 0
    const centerY = el ? (el.scrollTop + el.clientHeight / 2) / zoom : 0
    setZoom(value)
    requestAnimationFrame(() => { if (el) el.scrollTo({ left: centerX * value - el.clientWidth / 2, top: centerY * value - el.clientHeight / 2 }) })
  }
  function choose(id: number, reveal = false) {
    setSelected(id)
    if (reveal && viewport.current) {
      const node = byId.get(id)
      if (node) viewport.current.scrollTo({ left: node.x * zoom - viewport.current.clientWidth / 2 + NODE_WIDTH * zoom / 2, top: node.y * zoom - viewport.current.clientHeight / 2 + NODE_HEIGHT * zoom / 2, behavior: 'smooth' })
    }
  }
  const nodeLinks = (ids: number[], empty: string) => ids.length ? ids.map(id => <button className="flow-relation" key={id} onClick={() => choose(id, true)}><span className="mono">{String(id).padStart(2, '0')}</span><span>{graph!.nodes.find(n => n.id === id)?.label}</span><ArrowUpRight size={14} aria-hidden="true" /></button>) : <p className="flow-muted">{empty}</p>

  return <main id="main-content" className="screen screen-flowchart">
    <header className="flow-heading"><div><p className="eyebrow">04 / Plan the work</p><h2>A clear path to building.</h2><p>Explore the work, follow its dependencies, and see what can begin together.</p></div><Button disabled={!ready || busy || github.started} onClick={() => void generateFlow()}><RotateCw size={15} aria-hidden="true" />{flow.busy ? 'Planning…' : flow.result ? 'Regenerate flow' : 'Generate task flow'}</Button></header>
    {!ready && <div className="flow-message"><GitBranch size={20} aria-hidden="true" /><div><strong>Start with the two briefs.</strong><p>Generate project.md and team.md, then return to build the task flow.</p></div></div>}
    {flow.busy && <div role="status" className="flow-message"><span className="flow-spinner" /><div><strong>Building and checking your plan…</strong><p>Your briefs stay available in the other steps. Planning can take a few minutes.</p></div></div>}
    {flow.error && <div role="alert" className="flow-message flow-error"><div><strong>The plan couldn't be completed.</strong><p>{flow.error}</p></div></div>}
    {flow.result && <>
      <div className="flow-summary"><div><span className="flow-live-dot" /> {graph!.nodes.length} tasks <span className="flow-summary-divider">/</span> {graph!.edges.length} dependencies</div><div><Clock3 size={14} aria-hidden="true" /><strong>{ownersCurrent ? session.assignment.result!.validation.makespan_hours : flow.result.validation.makespan_hours}h</strong> {ownersCurrent ? 'with suggested owners' : 'headcount estimate'}</div><div><Users size={14} aria-hidden="true" /><strong>{flow.result.validation.total_person_hours}h</strong> total person-hours</div><span className="flow-summary-team">For {flow.result.team_size} people</span></div>
      <div ref={workbench} className={`flow-workbench ${expanded ? 'expanded' : ''}`} tabIndex={-1} role={expanded ? 'dialog' : undefined} aria-modal={expanded || undefined} aria-label="Task flow workspace">
        <div className="flow-workspace-toolbar"><div className="flow-tabs" aria-label="Graph view"><button aria-pressed={view === 'diagram'} onClick={() => setView('diagram')}>Flowchart</button><button aria-pressed={view === 'list'} onClick={() => setView('list')}>Task list</button></div><label className="flow-search"><Search size={15} aria-hidden="true" /><input aria-label="Find a task" placeholder="Find a task…" value={query} onChange={e => setQuery(e.target.value)} />{query && <button aria-label="Clear search" onClick={() => setQuery('')}><X size={14} /></button>}</label><button ref={expandButton} className="flow-icon-button" aria-label={expanded ? 'Exit focus mode' : 'Enter focus mode'} onClick={() => setExpanded(!expanded)}>{expanded ? <Minimize2 size={17} /> : <Maximize2 size={17} />}</button></div>
        <div className="flow-workspace-body"><div className="flow-map-column">
          <div className="flow-map-caption"><span>{query ? `${matches.length} matching task${matches.length === 1 ? '' : 's'}` : <><GitBranch size={13} aria-hidden="true" /> Prerequisite <ArrowRight size={13} aria-hidden="true" /> next task</>}</span>{view === 'diagram' && <label><input type="checkbox" checked={focused} onChange={e => setFocused(e.target.checked)} /> Focus connections</label>}</div>
          {view === 'diagram' && layout ? <div ref={viewport} className={`flow-viewport ${panning ? 'panning' : ''}`} tabIndex={0} aria-label="Task graph. Drag the background or scroll to pan."
            onPointerDown={e => { if (e.button !== 0 || e.pointerType !== 'mouse' || (e.target as HTMLElement).closest('button')) return; drag.current = { x: e.clientX, y: e.clientY, left: e.currentTarget.scrollLeft, top: e.currentTarget.scrollTop }; e.currentTarget.setPointerCapture(e.pointerId); setPanning(true) }}
            onPointerMove={e => { if (drag.current) { e.currentTarget.scrollLeft = drag.current.left - (e.clientX - drag.current.x); e.currentTarget.scrollTop = drag.current.top - (e.clientY - drag.current.y) } }}
            onPointerUp={() => { drag.current = null; setPanning(false) }} onPointerCancel={() => { drag.current = null; setPanning(false) }}>
            <div className="flow-stage"><div style={{ width: layout.width * zoom, height: layout.height * zoom, flexShrink: 0 }}><div className="flow-canvas" style={{ width: layout.width, height: layout.height, transform: `scale(${zoom})` }}>
              {Array.from({ length: layout.columns }, (_, column) => <div className="flow-layer" key={column} style={direction === 'horizontal' ? { left: PADDING + column * (NODE_WIDTH + COLUMN_GAP), width: NODE_WIDTH } : { left: PADDING, top: 32 + column * (NODE_HEIGHT + COLUMN_GAP), width: layout.width - PADDING * 2 }}><span>{column === 0 ? 'Start here' : `Layer ${String(column + 1).padStart(2, '0')}`}</span><small>{column === 0 ? 'No prerequisites' : 'After earlier work'}</small></div>)}
              <svg width={layout.width} height={layout.height} aria-hidden="true"><defs><marker id="flow-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="context-stroke" /></marker></defs>{graph!.edges.map((edge, i) => {
                const from = byId.get(edge.from)!, to = byId.get(edge.to)!
                const active = edge.from === current?.id || edge.to === current?.id
                const vertical = direction === 'vertical'
                const x1 = from.x + (vertical ? NODE_WIDTH / 2 : NODE_WIDTH), y1 = from.y + (vertical ? NODE_HEIGHT : NODE_HEIGHT / 2), x2 = to.x + (vertical ? NODE_WIDTH / 2 : -5), y2 = to.y + (vertical ? -5 : NODE_HEIGHT / 2)
                const path = vertical ? `M ${x1} ${y1} C ${x1} ${y1 + 38}, ${x2} ${y2 - 38}, ${x2} ${y2}` : `M ${x1} ${y1} C ${x1 + 38} ${y1}, ${x2 - 38} ${y2}, ${x2} ${y2}`
                return <path key={i} d={path} fill="none" stroke={active ? '#111111' : '#c9c9c4'} strokeWidth={active ? 2.5 : 1.5} opacity={focused && !active ? .18 : 1} markerEnd="url(#flow-arrow)" />
              })}</svg>
              {layout.nodes.map(node => <button key={node.id} className={`flow-node ${node.id === current?.id ? 'selected' : ''} ${fitLabel(node.id) && fitLabel(node.id) !== 'Direct match' ? 'needs-learning' : ''} ${(focused && !related.has(node.id)) || (query && !matching.has(node.id)) ? 'dimmed' : ''}`} style={{ left: node.x, top: node.y, width: NODE_WIDTH, height: NODE_HEIGHT, '--category': colour(node.group) } as CSSProperties} onClick={() => choose(node.id)} aria-pressed={node.id === current?.id} aria-label={`Task ${node.id}: ${node.label}${fitLabel(node.id) ? ` · ${fitLabel(node.id)}` : ''}`}><span className="flow-node-top"><span className="flow-category"><i />{node.group}</span><span className="flow-node-status"><span className="fit-node-label" title={fitLabel(node.id)}>{fitLabel(node.id) === 'Direct match' ? 'Direct' : fitLabel(node.id) === 'Learning needed' ? 'Learn' : fitLabel(node.id) ? 'Review' : ''}</span><span className="mono">{String(node.id).padStart(2, '0')}</span></span></span><strong>{node.label}</strong><span className="flow-node-bottom"><span><Clock3 size={12} aria-hidden="true" />{node.estimated_time_hours}h</span><span><Users size={12} aria-hidden="true" />{github.owners[node.id]?.length ?? 0}/{node.people_needed}</span><span className="flow-owner-names">{(github.owners[node.id] ?? []).map(memberName).join(", ") || "Unassigned"}</span>{node.id === current?.id && <ArrowUpRight size={14} aria-hidden="true" />}</span></button>)}
            </div></div></div>
          </div> : <div className="flow-list">{matches.length ? matches.map(node => <button key={node.id} className={`flow-list-item ${node.id === current?.id ? 'selected' : ''}`} onClick={() => choose(node.id)}><span className="mono">{String(node.id).padStart(2, '0')}</span><span><strong>{node.label}</strong><small>{node.group} · {node.estimated_time_hours}h · {node.people_needed} {node.people_needed === 1 ? 'person' : 'people'}{fitLabel(node.id) && ` · ${fitLabel(node.id)}`} · {(github.owners[node.id] ?? []).map(memberName).join(', ') || 'Unassigned'}</small></span><ArrowUpRight size={15} aria-hidden="true" /></button>) : <p className="flow-no-matches">No tasks match “{query}”. Try another name or area.</p>}</div>}
          <div className="flow-map-footer"><div className="flow-legend">{groups.map(group => <span key={group}><i style={{ background: colour(group) }} />{group}</span>)}</div>{view === 'diagram' && <div className="flow-zoom"><button className="flow-icon-button" aria-label="Flow down" aria-pressed={direction === 'vertical'} onClick={() => { setDirection('vertical'); setZoom(.9); viewport.current?.scrollTo(0, 0) }}><ArrowDown size={15} /></button><button className="flow-icon-button" aria-label="Flow right" aria-pressed={direction === 'horizontal'} onClick={() => { setDirection('horizontal'); setZoom(.9); viewport.current?.scrollTo(0, 0) }}><ArrowRight size={15} /></button><span className="flow-control-divider" /><button className="flow-icon-button" aria-label="Zoom out" disabled={zoom <= .3} onClick={() => changeZoom(zoom - .1)}><Minus size={15} /></button><button className="flow-zoom-value" aria-label="Reset to 100% zoom" onClick={() => changeZoom(1)}>{Math.round(zoom * 100)}%</button><button className="flow-icon-button" aria-label="Zoom in" disabled={zoom >= 1.6} onClick={() => changeZoom(zoom + .1)}><Plus size={15} /></button><button className="flow-icon-button" aria-label="Fit graph to view" title="Fit to view" onClick={fit}><Scan size={16} /></button></div>}</div>
        </div>
        {current && <aside className="flow-inspector" aria-label="Selected task details">
          <div className="flow-inspector-eyebrow"><span>Task {String(current.id).padStart(2, '0')}</span><span style={{ color: colour(current.group) }}>{current.group}</span></div>
          <h3>{current.label}</h3>
          <div className="flow-task-facts"><span><Clock3 size={15} aria-hidden="true" /> {current.estimated_time_hours} hours</span><span><Users size={15} aria-hidden="true" /> {current.people_needed} {current.people_needed === 1 ? 'person' : 'people'}</span></div>
          <p className="flow-description">{current.title}</p>
          <div className="flow-inspector-section"><h4>Task owners <span>{github.owners[current.id]?.length ?? 0}/{current.people_needed}</span></h4>
            <p className="flow-muted">{session.assignment.busy ? 'Finding the closest evidenced fit…' : 'Suggested from CV evidence. Adjust owners here and confirm with the team.'}</p>
            <div className="flow-owner-options">{members.map(member => {
              const chosen = github.owners[current.id] ?? []
              const checked = chosen.includes(member.id)
              const coverage = member.coverage.find(c => c.area === current.group.toLowerCase())
              return <label key={member.id}><input type="checkbox" checked={checked} disabled={busy || github.started || (!checked && chosen.length >= current.people_needed)} onChange={() => { github.setOwners({ ...github.owners, [current.id]: checked ? chosen.filter(id => id !== member.id) : [...chosen, member.id] }); github.invalidate() }} /><span>{memberName(member.id)}<small>{coverage && coverage.level !== 'none' ? `${coverage.level === 'strong' ? 'Strong' : 'Some'} area evidence · ${coverage.evidence_ids.join(', ')}` : 'Area evidence not stated'}</small></span></label>
            })}</div>
            <AssignmentDetails session={session} choose={id => choose(id, true)} />
          </div>
          <SkillFitDetails session={session} taskId={current.id} />
          <div className="flow-inspector-section"><h4>Needs first <span>{prerequisites.length}</span></h4>{nodeLinks(prerequisites, 'No prerequisites. Ready to start when people are available.')}</div>
          <div className="flow-inspector-section"><h4>Unlocks next <span>{unlocks.length}</span></h4>{nodeLinks(unlocks, 'No dependent tasks. This is an endpoint in the plan.')}</div>
        </aside>}
        </div>
      </div>
      <GithubExport session={session} />
      <details className="flow-checks"><summary><span><Check size={15} aria-hidden="true" /> Dependency & capacity checks passed</span><span>{flow.result.validation.warnings.length ? `${flow.result.validation.warnings.length} notes to review` : 'Review assumptions'}</span></summary><div><p>Dependencies are acyclic and reference existing tasks. Headcounts fit the supplied team size. Columns show dependency depth, not a schedule.</p><p>Duration and utilisation are estimates. The simulation checks headcount, not named availability or skill conflicts. Review the scope and deadline with your team.</p><p>Generated in {(flow.result.ms / 1000).toFixed(1)}s over {flow.result.rounds} attempt{flow.result.rounds === 1 ? '' : 's'}. Simulated idle capacity: {Math.round(flow.result.validation.idle_fraction * 100)}%.</p>{flow.result.validation.warnings.length > 0 && <ul>{flow.result.validation.warnings.map((warning, i) => <li key={i}>{warning}</li>)}</ul>}</div></details>
    </>}
    {!flow.result && !flow.busy && <div className="flow-empty"><div className="flow-empty-symbol"><GitBranch size={32} aria-hidden="true" /></div><h3>Your plan starts here.</h3><p>Generate a task flow to turn your team's shared understanding into a connected plan of work.</p><div className="flow-empty-steps"><span>Briefs</span><ArrowRight size={16} /><span>Tasks</span><ArrowRight size={16} /><span>Dependencies</span></div></div>}
  </main>
}
