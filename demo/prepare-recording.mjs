// Real Gemini run followed by replay from process memory for a short recording.
// No CV contents or generated briefs are written to fixtures or source control.
import fs from 'node:fs/promises'
import path from 'node:path'
import readline from 'node:readline'
import { createRequire } from 'node:module'
const require = createRequire(import.meta.url)
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || 'playwright')
const cvDir = process.argv[2]
if (!cvDir) throw new Error('Usage: node demo/prepare-recording.mjs <CV directory>')
const origin = process.env.DEMO_ORIGIN || 'http://127.0.0.1:5173'
const apiOrigin = process.env.DEMO_API_ORIGIN || 'http://127.0.0.1:8000'
const files = (await fs.readdir(cvDir)).filter(n => /\.(pdf|docx|png|jpe?g|webp)$/i.test(n)).sort().map(n => path.join(cvDir,n))
if (files.length < 2 || files.length > 8) throw new Error('Demo needs 2–8 CVs')
const prdPath = path.resolve('demo/project-prd.md')
const setup = { name:'TaskPilot', context:`Hackathon MVP. Starting from an empty repository with ${files.length} teammates. Build a working demo today.`, constraints:'Gemini only. React/TypeScript + FastAPI/Python. CV evidence for every person claim. Session memory only. Chart first, people matching second on the same page.' }
const description = 'Help a newly formed hackathon team agree on what to build and who can help. Upload CVs and a project brief, get team.md and project.md, then a dependency graph with evidence-backed owner suggestions and a reviewed GitHub issue export.'
const teamForm = new FormData()
teamForm.append('input',JSON.stringify({setup,members:files.map((_,i)=>({id:`m${i+1}`,label:'',text:''}))}))
for (const [i,file] of files.entries()) teamForm.append(`cv:m${i+1}`,new Blob([await fs.readFile(file)]),path.basename(file))
const projectForm = new FormData()
projectForm.append('input',JSON.stringify({setup,project_text:description}))
projectForm.append('project',new Blob([await fs.readFile(prdPath)]),path.basename(prdPath))
const cache={}
const input=readline.createInterface({input:process.stdin,output:process.stdout,terminal:false})
const commands=input[Symbol.asyncIterator]()
async function request(endpoint,body,multipart=false) {
  for(let attempt=0;attempt<2;attempt++) {
    const start=Date.now()
    const response=await fetch(apiOrigin+'/api/'+endpoint,{method:'POST',headers:multipart?undefined:{'content-type':'application/json'},body:multipart?body:JSON.stringify(body),signal:AbortSignal.timeout(200000)})
    const data=await response.json()
    if(!response.ok || !data.ok || data.data?.error) {
      const error=data.error||data.data?.error
      if(attempt===0 && error?.retryable && ['model_failed','rate_limited'].includes(error.code)) {
        console.log(`${endpoint}: transient service failure; retrying once`)
        await new Promise(r=>setTimeout(r,2500)); continue
      }
      console.error(endpoint+': '+JSON.stringify(error))
      console.log('Successful stages remain in memory. Enter retry to retry this stage, or quit.')
      const next=await commands.next()
      if(next.done || next.value.trim()!=='retry') process.exit(1)
      attempt=-1; continue
    }
    cache['/api/'+endpoint]=data
    console.log(`${endpoint}: ${((Date.now()-start)/1000).toFixed(1)}s`)
    return data.data
  }
}
console.log(`Preparing real demo with ${files.length} CVs. Results remain in this process memory.`)
const [project,team]=await Promise.all([request('briefs/project',projectForm,true),request('briefs/team',teamForm,true)])
const flow=await request('task-graph',{project_md:project.markdown,team_md:team.markdown,team_size:team.structured.members.length})
const assignment=await request('task-assignments',{team:team.structured,tasks:flow.tasks})
console.log(JSON.stringify({members:team.structured.members.map(m=>({id:m.id,name:m.cv_name.text})),tasks:flow.tasks.length,learningTasks:assignment.assignment.fit.filter(f=>f.matches.some(m=>m.match!=='direct')).length,teamGaps:assignment.assignment.fit.filter(f=>f.team_missing_skills.length).map(f=>({id:f.task_id,skills:f.team_missing_skills})),rounds:assignment.rounds},null,2))
const browser=await chromium.launch({headless:true})
console.log('READY — enter record to capture, or quit. Cached results never touch disk.')
for await(const line of commands) {
  if(line.trim()==='quit') break
  if(line.trim()!=='record') continue
  try { const {record}=await import(`./record-flow.mjs?run=${Date.now()}`); await record({browser,cache,files,prdPath,setup,description,origin,team,flow,assignment}) }
  catch(error){console.error('Recording failed:',error.message)}
  console.log('READY — record again or quit.')
}
input.close()
process.stdin.pause()
await browser.close()
