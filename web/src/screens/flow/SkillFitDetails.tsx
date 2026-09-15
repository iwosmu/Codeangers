import type { BriefSession } from '../../state/briefs'
import { fitLabels, sameOwners } from './assignment'

export function SkillFitDetails({ session, taskId }: { session: BriefSession; taskId: number }) {
  const fit = session.assignment.result?.assignment.fit.find(f => f.task_id === taskId)
  if (!fit) return null
  const current = sameOwners(fit.matches.map(m => m.member_id), session.github.owners[taskId])
  return <section className="flow-inspector-section skill-fit"><h4>Why these people?</h4>
    {!current && <p className="fit-warning">Owners changed. These are the original suggestions; the new owners have not been assessed for this task.</p>}
    {fit.team_missing_skills.length > 0 && <p className="fit-warning"><strong>No direct evidence in this team</strong>{fit.team_missing_skills.join(', ')}. Confirm actual experience before starting.</p>}
    {fit.matches.map(match => { const member = session.team.document?.structured.members.find(m => m.id === match.member_id); return <article key={match.member_id} className={`skill-fit-person fit-${match.match}`}><div><strong>{member?.cv_name.text === 'not stated' ? match.member_id : member?.cv_name.text}</strong><span className="fit-badge">{fitLabels[match.match]}</span></div><p>{match.reason}</p>{match.missing_skills.length > 0 && <p><strong>Not stated in CV:</strong> {match.missing_skills.join(', ')}</p>}{match.learning_step && <p><strong>First learning step:</strong> {match.learning_step}</p>}{match.evidence_ids.length > 0 && <details><summary>CV evidence behind this suggestion</summary>{match.evidence_ids.map(id => { const e = member?.evidence.find(e => e.id === id); return e && <blockquote key={id}>{e.quote}<footer>{session.team.document?.sources.find(s => s.id === e.source_id)?.label} · {e.location} [{match.member_id}:{id}]</footer></blockquote> })}</details>}</article> })}
  </section>
}
