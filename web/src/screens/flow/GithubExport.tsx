import { GitBranch, ArrowUpRight } from 'lucide-react'
import { Button } from '../../components/ui'
import type { BriefSession } from '../../state/briefs'
import './github.css'

export function GithubExport({ session }: { session: BriefSession }) {
  const { github: gh, team, project, flow, inputs } = session
  const members = team.document?.structured.members ?? []
  if (!flow.result || !project.document) return null
  const nodes = flow.result.graph.nodes
  const name = (id: string) => { const m = members.find(m => m.id === id); return m?.cv_name.text !== 'not stated' ? m?.cv_name.text : inputs.members.find(m => m.id === id)?.label || id }
  const login = (id: string) => gh.profiles[id] ?? (members.find(m => m.id === id)?.github?.text === 'not stated' ? '' : members.find(m => m.id === id)?.github?.text ?? '')
  const remaining = nodes.filter(n => (gh.owners[n.id]?.length ?? 0) !== n.people_needed).length
  const frozen = gh.busy || gh.started
  const ready = !remaining && members.every(m => login(m.id)) && gh.repository && gh.token
  function review() {
    void gh.review({ repository: gh.repository.trim(), title: inputs.setup.name || 'Project task plan', summary: project.document!.structured.one_liner.text,
      members: members.map(m => ({ id: m.id, login: login(m.id).trim() })),
      tasks: nodes.map(n => ({ id: n.id, title: n.label, description: n.title, hours: n.estimated_time_hours, people: n.people_needed, owners: gh.owners[n.id] ?? [], prerequisites: flow.result!.graph.edges.filter(e => e.to === n.id).map(e => e.from) })) })
  }
  return <section className="github-export" aria-labelledby="github-heading">
    <header><div><p className="eyebrow">05 / Put the plan to work</p><h3 id="github-heading"><GitBranch size={21} /> Ship the plan to GitHub.</h3><p>One parent issue, assigned task sub-issues, and links between prerequisites.</p></div><span className="github-count">{nodes.length - remaining}/{nodes.length} tasks assigned</span></header>
    <div className="github-setup"><div><h4>Connect your team</h4><p>Confirm each account. Profiles found in CVs are prefilled; missing profiles need a username.</p>{members.map(m => <label className="github-profile" key={m.id}><span>{name(m.id)}<small>{m.github && m.github.text !== 'not stated' ? `CV: ${m.github.text} · ${m.github.evidence_ids.join(', ')}` : 'GitHub not stated in CV'}</small></span><div><span>@</span><input aria-label={`GitHub username for ${name(m.id)}`} disabled={frozen} value={login(m.id)} placeholder="username" autoCapitalize="none" spellCheck={false} onChange={e => { gh.setProfiles({ ...gh.profiles, [m.id]: e.target.value }); gh.invalidate() }} /></div></label>)}</div>
      <div className="github-destination"><h4>Choose the destination</h4><label>Repository<input disabled={frozen} placeholder="owner/repository" value={gh.repository} autoCapitalize="none" onChange={e => { gh.setRepository(e.target.value); gh.invalidate() }} /></label><label>GitHub access token<input type="password" autoComplete="off" disabled={gh.busy || gh.result?.complete} placeholder="Fine-grained token" value={gh.token} onChange={e => { gh.setToken(e.target.value); gh.invalidate() }} /></label><p>Give the token <strong>Issues: read and write</strong> access to this repository. Team members must be assignable there. The token stays in memory for this session.</p><a href="https://github.com/settings/personal-access-tokens/new" target="_blank" rel="noreferrer">Create a GitHub token <ArrowUpRight size={13} /></a></div></div>
    {remaining > 0 && <p className="github-guidance">Select a task in the flowchart and choose its owners. {remaining} task{remaining === 1 ? '' : 's'} still need the required number of people.</p>}
    {!gh.started && <Button disabled={!ready || gh.busy} onClick={review}>{gh.busy ? 'Checking GitHub…' : 'Check access & preview issues'}</Button>}
    {gh.error && <p role="alert" className="github-error">{gh.error}</p>}
    {gh.preview && <div className="github-preview"><h4>Review {gh.preview.issues.length} issues</h4><p>Creating in <strong>{gh.preview.account.repository}</strong> · {gh.preview.account.private ? 'Private' : 'Public'} repository · Signed in as <strong>@{gh.preview.account.login}</strong></p><p>Only the content below and GitHub assignments are exported. Placeholder issue links will become real links.</p>{gh.preview.issues.map(issue => <details key={issue.key}><summary><strong>{issue.title}</strong><span>{issue.assignees.map(a => '@' + a).join(', ') || 'Parent issue'}</span></summary><pre>{issue.body}</pre></details>)}
      {!gh.result?.complete && <Button disabled={gh.busy} onClick={() => void gh.publish()}>{gh.busy ? 'Exporting… keep this session open' : gh.started ? 'Resume export' : `Create ${gh.preview.issues.length} issues on GitHub`}</Button>}
    </div>}
    {gh.result && <div className="github-result" role="status"><h4>{gh.result.complete ? 'Your plan is on GitHub.' : 'Export needs attention.'}</h4>{gh.result.error && <p>{gh.result.error} Resume uses the same plan and checks for existing issues.</p>}<ul>{gh.result.issues.map(issue => <li key={issue.key}><a href={issue.url} target="_blank" rel="noreferrer">{issue.key === 'parent' ? 'Project issue' : `Task ${issue.key}`} · #{issue.number} <ArrowUpRight size={13} /></a></li>)}</ul></div>}
  </section>
}
