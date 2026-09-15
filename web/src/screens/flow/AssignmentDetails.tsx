import { Button } from '../../components/ui'
import type { BriefSession } from '../../state/briefs'
import { currentAssignment } from './assignment'

/** Assignment controls live inside the graph's task inspector. */
export function AssignmentDetails({ session, choose }: { session: BriefSession; choose: (id: number) => void }) {
  const { assignment, generateAssignments, busy, github, team } = session
  const result = assignment.result
  const current = currentAssignment(result, github.owners)
  const name = (id: string) => { const n = team.document?.structured.members.find(m => m.id === id)?.cv_name.text; return n && n !== 'not stated' ? n : id }
  return <div className="assignment-details">
    <Button kind="secondary" disabled={busy || github.started} onClick={() => void generateAssignments()}>{assignment.busy ? 'Matching owners…' : result ? 'Recalculate all owners' : 'Suggest task owners'}</Button>
    {assignment.busy && <p role="status">Comparing CV evidence and checking task order…</p>}
    {assignment.error && <p className="notice" role="alert">{assignment.error}</p>}
    {result && <details className="assignment-explanation"><summary>Team task order & assumptions</summary><p>{current ? `${result.validation.makespan_hours}h with suggested owners.` : 'Owners edited. These original sequences and timing need recalculation.'} Suggestions assume continuous availability and exclude extra learning time. Recalculating replaces all owner choices.</p>
      <p>“Closest skillset” describes transferable experience, not proven expertise or learning speed. Confirm interest and availability together.</p>
      {result.assignment.people.map(p => <div className="assignment-person" key={p.member_id}><strong>{name(p.member_id)}</strong><span>{p.task_ids.length ? p.task_ids.map((id, i) => <span key={id}>{i > 0 && ' → '}<button onClick={() => choose(id)}>#{id}</button></span>) : 'No tasks suggested'}</span></div>)}
      {result.assignment.notes.map((n, i) => <p key={i}>{n.task_id ? `Task ${n.task_id} · ` : ''}{n.name}: {n.note}</p>)}
      {result.validation.warnings.map((w, i) => <p key={i}>{w}</p>)}<p>Generated in {(result.ms / 1000).toFixed(1)}s. CV references and schedule consistency checked; review the skill-fit reasoning.</p></details>}
  </div>
}
