import { Users } from 'lucide-react'
import { Button, Card, Field } from '../../components/ui'
import { BriefDocument } from '../../components/BriefDocument'
import { SourceUploads, CV_ACCEPT } from '../../components/SourceUploads'
import type { BriefSession } from '../../state/briefs'
import type { MemberInput } from '../../api/briefTypes'

export function PlanScreen({ session }: { session: BriefSession }) {
  const { inputs, update, team, busy, generate } = session
  function resize(count: number) {
    const members = inputs.members.slice(0, count)
    while (members.length < count) members.push({ id: `m${members.length + 1}`, label: '', text: '' })
    update({ members })
  }
  function changeMember(index: number, patch: Partial<MemberInput>) { update({ members: inputs.members.map((m, i) => i === index ? { ...m, ...patch } : m) }) }
  function batch(files: File[]) {
    const members = inputs.members.map(m => ({ ...m }))
    for (const file of files) {
      const empty = members.find(m => !m.file && !m.text.trim())
      if (empty) empty.file = file
      else members.push({ id: `m${members.length + 1}`, label: '', text: '', file })
    }
    update({ members })
  }
  const occupied = inputs.members.filter(m => m.file || m.text.trim()).length
  const ready = occupied === inputs.members.length
  const profiles = team.document?.structured.members ?? []
  const areas: Record<string, string> = { frontend: 'Frontend', backend: 'Backend', database: 'Database / data', ml: 'AI / ML', design: 'Design / UX', devops: 'DevOps', research: 'Research', pitch: 'Pitch / communication' }
  const covered = new Set(profiles.flatMap(m => m.coverage.filter(c => c.level !== 'none').map(c => c.area)))
  return <main id="main-content" className="screen screen-team"><div className="screen-heading"><div><p className="eyebrow">02 · Team overview</p><h1>Understand the team before planning the work.</h1><p>Bring the CVs. Build a grounded picture of experience, strengths and the questions still worth asking.</p></div></div>
    <div className="team-layout"><section className="team-main"><Card className="team-input-card" title="Build the team" right={<span className="pill"><Users size={13} aria-hidden="true" /> {occupied}/{inputs.members.length} ready</span>}>
      <fieldset disabled={busy} className="input-group"><div className="team-controls"><label className="field team-size"><span className="field-label">Team size</span><select className="select" value={inputs.members.length} onChange={e => resize(Number(e.target.value))}>{[2,3,4,5,6,7,8].map(n => <option key={n} value={n}>{n} people</option>)}</select></label><p className="subtle">One CV per person. Add or remove teammates as your team takes shape.</p></div>
        {occupied < 8 && <SourceUploads files={[]} onChange={batch} max={8 - occupied} accept={CV_ACCEPT} title="Add CVs in a batch" help="PDF, DOCX, images or text files. Team size expands automatically, up to 8 people." disabled={busy} />}
        <div className="people-list">{inputs.members.map((member, i) => <article className="member-input" key={member.id}><div className="member-input-heading"><span className="profile-index">{String(i + 1).padStart(2, '0')}</span><span className="avatar avatar-large"><Users size={20} aria-hidden="true" /></span><div><strong>{member.label || `Member ${i + 1}`}</strong><small>{member.file?.name || (member.text.trim() ? 'Pasted CV text' : 'Add a CV to get started')}</small></div><span className="source-label">{member.file || member.text.trim() ? 'Source ready' : 'Awaiting CV'}</span></div>
          <div className="input-group"><Field label={`Member ${i + 1} name (optional)`} value={member.label} onChange={label => changeMember(i, { label })} />
            <SourceUploads files={member.file ? [member.file] : []} onChange={files => changeMember(i, { file: files[0] })} max={1} accept={CV_ACCEPT} title={`CV for member ${i + 1}`} help="Upload a file or paste CV text below." disabled={busy} />
            <Field label={`Member ${i + 1} CV text`} rows={3} value={member.text} onChange={text => changeMember(i, { text })} placeholder="Paste CV text…" />
            <div><Button kind="ghost" disabled={inputs.members.length <= 2} onClick={() => update({ members: inputs.members.filter((_, index) => index !== i).map((m, index) => ({ ...m, id: `m${index + 1}` })) })}>Remove member {i + 1}</Button></div>
          </div></article>)}</div>
      </fieldset><div className="form-action team-generate"><div><strong>{ready ? 'Your sources are ready.' : 'Add a source for every teammate.'}</strong><p>Each profile is grounded in that person's CV.</p></div><div className="document-actions"><Button disabled={!ready || busy} onClick={() => void generate('team')}>{team.busy ? 'Reading team CVs…' : 'Generate team.md'}</Button>
      <Button kind="secondary" disabled={!ready || busy || !(inputs.projectText.trim() || inputs.projectFiles.length)} onClick={() => { void generate('team'); void generate('project') }}>Generate both documents</Button></div></div>
    </Card></section><aside className="coverage-panel"><p className="eyebrow">Team signal</p><div className="coverage-count">{String(profiles.length).padStart(2, '0')}</div><h2>profiles analysed</h2><p>{profiles.length ? 'Coverage reflects explicit CV evidence. An empty area is unconfirmed, not a lack of ability.' : 'Generate the team brief to reveal your coverage. Uploaded files alone do not establish skills.'}</p><div className="coverage-list">{Object.entries(areas).map(([key,label]) => <div className={covered.has(key) ? 'covered' : ''} key={key}><span>{label}</span><small>{covered.has(key) ? 'Evidenced' : profiles.length ? 'Not stated' : 'Awaiting analysis'}</small></div>)}</div><div className="coverage-action"><Users size={18} aria-hidden="true" /><p><strong>{covered.size}/8 areas evidenced</strong>Review citations and discuss the gaps together.</p></div></aside></div>
    <section className="review-section" aria-label="Team document"><BriefDocument output={team} kind="team" /></section>
  </main>
}
