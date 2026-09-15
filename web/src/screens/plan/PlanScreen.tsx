import { Users } from 'lucide-react'
import { Button, Card, Field } from '../../components/ui'
import { BriefDocument } from '../../components/BriefDocument'
import { SourceUploads, CV_ACCEPT } from '../../components/SourceUploads'
import type { BriefSession } from '../../state/briefs'
import type { MemberInput } from '../../api/briefTypes'

export function PlanScreen({ session }: { session: BriefSession }) {
  const { inputs, update, team, project, busy, generate } = session
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
  return <main id="main-content" className="screen screen-flow"><div className="screen-heading"><div><p className="eyebrow">02 · Team overview</p><h2>Know who brings what.</h2><p>Add the CVs, then review the evidence behind each person's strengths, likely roles, and team coverage.</p></div></div>
    <div className="stack"><Card title="Build the team" right={<span className="pill"><Users size={13} aria-hidden="true" /> {occupied}/{inputs.members.length} ready</span>}>
      <fieldset disabled={busy} className="input-group"><label className="field team-size"><span className="field-label">Team size</span><select className="select" value={inputs.members.length} onChange={e => resize(Number(e.target.value))}>{[2,3,4,5,6,7,8].map(n => <option key={n} value={n}>{n} people</option>)}</select></label>
        {occupied < 8 && <SourceUploads files={[]} onChange={batch} max={8 - occupied} accept={CV_ACCEPT} title="Add CVs in a batch" help="PDF, DOCX, image, TXT or MD. One file per person; team size expands automatically." disabled={busy} />}
        <div className="grid-three">{inputs.members.map((member, i) => <article className="person-card" key={member.id}><div className="person-top"><div className="avatar">{i + 1}</div><strong>Member {i + 1}</strong></div>
          <div className="input-group"><Field label={`Member ${i + 1} name (optional)`} value={member.label} onChange={label => changeMember(i, { label })} />
            <SourceUploads files={member.file ? [member.file] : []} onChange={files => changeMember(i, { file: files[0] })} max={1} accept={CV_ACCEPT} title={`CV for member ${i + 1}`} help="Upload a CV or paste the text below." disabled={busy} />
            <Field label={`Member ${i + 1} CV text`} rows={3} value={member.text} onChange={text => changeMember(i, { text })} placeholder="Paste CV text…" />
            <Button kind="ghost" disabled={inputs.members.length <= 2} onClick={() => update({ members: inputs.members.filter((_, index) => index !== i).map((m, index) => ({ ...m, id: `m${index + 1}` })) })}>Remove member {i + 1}</Button>
          </div></article>)}</div>
      </fieldset><div className="document-actions"><Button disabled={!ready || team.busy} onClick={() => void generate('team')}>{team.busy ? 'Reading team CVs…' : 'Generate team.md'}</Button>
      <Button kind="secondary" disabled={!ready || busy || !(inputs.projectText.trim() || inputs.projectFiles.length)} onClick={() => { void generate('team'); void generate('project') }}>Generate both documents</Button><span className="subtle">{project.busy ? 'project.md is also generating.' : 'Every person needs a CV file or pasted text.'}</span></div>
    </Card><BriefDocument output={team} kind="team" /></div>
  </main>
}
