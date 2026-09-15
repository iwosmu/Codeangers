import { GitBranch, UsersRound } from 'lucide-react'
import { Card } from '../../components/ui'
import { BriefDocument } from '../../components/BriefDocument'
import type { BriefSession } from '../../state/briefs'

const areas: Record<string, string> = { frontend: 'Frontend', backend: 'Backend', database: 'Database / data', ml: 'AI / ML', design: 'Design / UX', devops: 'DevOps', research: 'Research / domain', pitch: 'Pitch / communication' }
const symbols = { strong: '●●', some: '●', none: '–' }
export function AssignmentScreen({ session }: { session: BriefSession }) {
  const { team, project, inputs } = session
  const members = team.document?.structured.members ?? []
  const name = (id: string, cvName: string) => cvName !== 'not stated' ? cvName : inputs.members.find(m => m.id === id)?.label || id
  return <main id="main-content" className="screen screen-assignment"><div className="screen-heading"><div><p className="eyebrow">03 · Review & download</p><h2>One shared understanding.</h2><p>Check the source evidence, discuss the open questions, and take both documents into your next conversation.</p></div></div>
    <div className="stack">{members.length > 0 && <><Card title="Team coverage" right={<span className="pill"><UsersRound size={14} aria-hidden="true" /> {members.length} people</span>}><p className="subtle">●● strong evidence · ● some evidence · – not stated / unconfirmed. Select a supported cell to read its CV evidence.</p><div className="table-scroll"><table><thead><tr><th>Area</th>{members.map(m => <th key={m.id}>{name(m.id, m.cv_name.text)}</th>)}</tr></thead><tbody>{Object.entries(areas).map(([area, label]) => <tr key={area}><th>{label}</th>{members.map(m => { const coverage = m.coverage.find(c => c.area === area); const evidence = m.evidence.filter(e => coverage?.evidence_ids.includes(e.id)); return <td key={m.id}>{evidence.length ? <details><summary aria-label={`${name(m.id, m.cv_name.text)}: ${label}, ${coverage?.level} evidence`}>{symbols[coverage!.level]}</summary>{evidence.map(e => <blockquote key={e.id}>{e.quote}<footer>{e.location} · {team.document?.sources.find(s => s.id === e.source_id)?.label} [{m.id}:{e.id}]</footer></blockquote>)}</details> : '–'}</td> })}</tr>)}</tbody></table></div></Card>
    <div className="grid-three">{members.map(m => <Card key={m.id} title={name(m.id, m.cv_name.text)}><p className="muted">{m.roles.map(r => r.text).join(' · ') || 'Role not stated'}</p><div className="skill-tags">{m.stack.map((s, i) => <span className="skill-tag" key={i}>{s.text}</span>)}</div><details><summary>Strengths & CV evidence</summary>{m.strengths.map((s, i) => <div key={i}><p>{s.text}</p>{m.evidence.filter(e => s.evidence_ids.includes(e.id)).map(e => <blockquote key={e.id}>{e.quote}<footer>{e.location} [{m.id}:{e.id}]</footer></blockquote>)}</div>)}</details></Card>)}</div></>}
      <BriefDocument output={project} kind="project" /><BriefDocument output={team} kind="team" />
      <Card title={<><GitBranch size={16} aria-hidden="true" /> Task flow & assignments · coming later</>}><p className="muted">The next stage will use the project deliverables to create a task flow, then use the team evidence to suggest ownership. The two documents will form the starting point for that stage.</p></Card>
    </div></main>
}
