import {execFileSync} from 'node:child_process'
import {randomUUID} from 'node:crypto'

// Use existing gh authentication in memory. Export only the task plan and
// verified GitHub accounts; no CV evidence or credentials enter issue bodies.
export async function prepareGithub({cache,team,flow,assignment,setup}) {
  if(cache.githubRecording){
    if(!cache['/api/github/export']?.data.complete){
      const {token,body}=cache.githubRecording
      const response=await fetch((process.env.DEMO_API_ORIGIN||'http://127.0.0.1:8000')+'/api/github/export',{method:'POST',headers:{'content-type':'application/json','x-github-token':token},body:JSON.stringify(body),signal:AbortSignal.timeout(240000)})
      const result=await response.json()
      cache['/api/github/export']=result
      if(!result.data?.complete)throw new Error(result.error?.message||result.data?.error||'GitHub export incomplete.')
    }
    return cache.githubRecording
  }
  const repository='iwosmu/Codeangers'
  const gh=(...args)=>execFileSync('gh',args,{encoding:'utf8',stdio:['ignore','pipe','pipe']}).trim()
  const token=gh('auth','token')
  const candidates=JSON.parse(gh('api',`repos/${repository}/assignees`))
  const profiles=candidates.map(c=>JSON.parse(gh('api',`users/${c.login}`)))
  const normalize=s=>(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'')
  const members=team.structured.members.map(m=>{
    const name=normalize(m.cv_name.text)
    const matches=profiles.filter(p=>normalize(p.name)===name || normalize(p.login).includes(name))
    if(matches.length!==1)throw new Error(`Could not uniquely verify GitHub account for ${m.id}.`)
    return {id:m.id,login:matches[0].login}
  })
  const body={repository,export_id:randomUUID(),title:setup.name,summary:cache['/api/briefs/project'].data.structured.one_liner.text,members,
    tasks:flow.graph.nodes.map(n=>({id:n.id,title:n.label,description:n.title,hours:n.estimated_time_hours,people:n.people_needed,owners:assignment.owners[n.id]||[],prerequisites:flow.graph.edges.filter(e=>e.to===n.id).map(e=>e.from)}))}
  const api=process.env.DEMO_API_ORIGIN||'http://127.0.0.1:8000'
  const request=async endpoint=>{
    const response=await fetch(api+endpoint,{method:'POST',headers:{'content-type':'application/json','x-github-token':token},body:JSON.stringify(body),signal:AbortSignal.timeout(240000)})
    const result=await response.json()
    if(!response.ok||!result.ok)throw new Error(result.error?.message||'GitHub export failed.')
    return result
  }
  cache.githubRecording={token,body,members}
  cache['/api/github/preview']=await request('/api/github/preview')
  console.log(`Verified ${members.length} GitHub accounts. Exporting ${body.tasks.length+1} real issues.`)
  const result=await request('/api/github/export')
  cache['/api/github/export']=result
  if(!result.data.complete)throw new Error(result.data.error||'GitHub export incomplete; resume before recording.')
  const parent=result.data.issues.find(i=>i.key==='parent')
  console.log('GitHub plan:',parent.url)
  return cache.githubRecording
}
