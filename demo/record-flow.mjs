import fs from 'node:fs/promises'
import path from 'node:path'
import assert from 'node:assert/strict'

export async function record({browser,cache,files,prdPath,setup,description,origin,assignment,team,flow}) {
  console.log('Recording validated results:', JSON.stringify({members:team.structured.members.map(m=>({id:m.id,name:m.cv_name.text,tools:m.stack.length})),tasks:flow.tasks.map(t=>({id:t.id,name:t.name})),learningMatches:assignment.assignment.fit.filter(f=>f.matches.some(m=>m.match!=='direct'))},null,2))
  const out=path.resolve('output/playwright')
  await fs.mkdir(out,{recursive:true})
  const context=await browser.newContext({viewport:{width:3840,height:2160},deviceScaleFactor:1,recordVideo:{dir:out,size:{width:3840,height:2160}},acceptDownloads:true})
  const delays={'/api/briefs/project':2200,'/api/briefs/team':2600,'/api/task-graph':2300,'/api/task-assignments':5000}
  const errors=[]
  let complete=false
  await context.route('**/api/**',async route=>{
    const url=new URL(route.request().url())
    if(cache[url.pathname]) {
      let checking='request body'
      try {
        const request=route.request()
        if(url.pathname.startsWith('/api/briefs/')) {
          const form=await new Response(request.postDataBuffer(),{headers:{'content-type':request.headers()['content-type']}}).formData()
          const input=JSON.parse(form.get('input'))
          checking='product setup'; assert.deepEqual(input.setup,setup)
          if(url.pathname.endsWith('/team')) {
            checking='member roster'; assert.deepEqual(input.members,files.map((_,i)=>({id:`m${i+1}`,label:'',text:''})))
            // Chromium omits file bytes from intercepted multipart postData.
            // setInputFiles below loads the same source paths used by the live
            // preparation; verify their member mapping and names on the wire.
            for(const [i,file] of files.entries()) assert.equal(form.get(`cv:m${i+1}`).name,path.basename(file))
          } else {
            checking='project text'; assert.equal(input.project_text,description)
            checking='project file'; assert.equal(form.get('project').name,path.basename(prdPath))
          }
        } else if(url.pathname==='/api/task-graph') {
          assert.deepEqual(request.postDataJSON(),{project_md:cache['/api/briefs/project'].data.markdown,team_md:team.markdown,team_size:files.length})
        } else if(url.pathname==='/api/task-assignments') {
          assert.deepEqual(request.postDataJSON(),{team:team.structured,tasks:flow.tasks})
        }
      } catch {
        errors.push(`${url.pathname}: ${checking} differed from the validated demo input.`)
        await route.abort(); return
      }
      await new Promise(r=>setTimeout(r,delays[url.pathname]||0))
      await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(cache[url.pathname])})
    } else await route.continue()
  })
  const page=await context.newPage()
  const video=page.video()
  page.on('pageerror',e=>errors.push(e.message))
  await page.addInitScript(()=>{
    addEventListener('DOMContentLoaded',()=>{
      document.documentElement.style.zoom='2'
      const pointer=document.createElement('div')
      pointer.innerHTML='<svg width="18" height="25" viewBox="0 0 18 25"><path d="M2 1L2 20L6.8 15.8L10.3 23L13.4 21.4L9.8 14.5L16 14Z" fill="#111" stroke="white" stroke-width="1.5"/></svg>'
      Object.assign(pointer.style,{position:'fixed',left:'0',top:'0',zIndex:'2147483647',pointerEvents:'none',transform:'translate(-50px,-50px)'})
      document.body.appendChild(pointer)
      addEventListener('mousemove',e=>{pointer.style.transform=`translate(${e.clientX/2}px,${e.clientY/2}px)`})
    })
  })
  const born=Date.now()
  await page.goto(origin,{waitUntil:'networkidle'})
  await page.getByRole('heading',{name:'Give the project a clear starting point.'}).waitFor()
  const start=Date.now()
  const at=async s=>{await new Promise(r=>setTimeout(r,Math.max(0,start+s*1000-Date.now())))}
  const point=async locator=>{await locator.scrollIntoViewIfNeeded();const b=await locator.boundingBox();if(b)await page.mouse.move(b.x+b.width*.5,b.y+b.height*.5,{steps:24})}
  const click=async locator=>{await point(locator);await locator.click()}
  const top=async()=>{await page.evaluate(()=>window.scrollTo({top:0,behavior:'smooth'}));await page.waitForTimeout(600)}
  const fill=async(name,value)=>{const l=page.getByRole('textbox',{name,exact:true});await point(l);await l.fill(value)}
  const nav=async name=>{await click(page.getByRole('button',{name,exact:true}));await top()}
  try {
    await at(4); await fill('Team / project name',setup.name)
    await at(7); await fill('What are you building?',description)
    await at(11); await fill('Context',setup.context); await fill('Known constraints',setup.constraints)
    await at(15); await page.getByLabel('Add project material',{exact:true}).setInputFiles(prdPath)
    await at(19); await click(page.getByRole('button',{name:'Generate project.md',exact:true}))
    await at(23); await page.getByRole('button',{name:'Download project.md',exact:true}).waitFor(); await point(page.getByRole('heading',{name:'project.md',exact:true}));
    await at(29); await nav('2 Team overview')
    await at(33); await page.getByLabel('Add CVs in a batch',{exact:true}).setInputFiles(files); await top()
    await at(38); await point(page.getByRole('textbox',{name:'Member 2 name (optional)',exact:true}))
    await at(43); await click(page.getByRole('button',{name:'Generate team.md',exact:true})); await top()
    await at(49); await page.getByRole('button',{name:'Download team.md',exact:true}).waitFor()
    await at(51); await nav('Review & download')
    const supported=page.locator('table details summary').first()
    await at(57); if(await supported.count())await click(supported)
    await at(63); if(await supported.count())await click(supported)
    await at(66); await click(page.getByRole('button',{name:'Download project.md',exact:true}))
    await at(71); await click(page.getByRole('button',{name:'Download team.md',exact:true}))
    await at(76); await nav('4 Task flow')
    await at(79); await click(page.getByRole('button',{name:'Generate task flow',exact:true}))
    await page.getByRole('button',{name:'Enter focus mode',exact:true}).waitFor()
    await at(83); await click(page.getByRole('button',{name:'Enter focus mode',exact:true})); await click(page.getByRole('button',{name:'Fit graph to view',exact:true}))
    await page.getByRole('button',{name:'Recalculate all owners',exact:true}).waitFor({timeout:15000})
    const selected=assignment.assignment.fit.find(f=>f.team_missing_skills.length && f.matches.some(m=>m.match==='adjacent')) || assignment.assignment.fit.find(f=>f.matches.some(m=>m.match==='adjacent')) || assignment.assignment.fit[0]
    await at(89); await click(page.getByRole('button',{name:'Reset to 100% zoom',exact:true})); await click(page.getByRole('button',{name:new RegExp(`^Task ${selected.task_id}:`)}))
    await at(94); const evidence=page.getByText('CV evidence behind this suggestion',{exact:true}).first(); if(await evidence.count())await click(evidence)
    await page.screenshot({path:path.join(out,'taskpilot-demo-4k-still.png')})
    await at(103); await click(page.getByRole('button',{name:'Task list',exact:true}))
    await at(108); await click(page.getByRole('button',{name:'Flowchart',exact:true})); await click(page.getByRole('button',{name:'Fit graph to view',exact:true}))
    await at(113); await click(page.getByRole('button',{name:'Exit focus mode',exact:true})); await point(page.getByRole('heading',{name:'Ship the plan to GitHub.',exact:true}))
    await fill('Repository','iwosmu/Codeangers')
    await at(119); await click(page.getByRole('button',{name:'Enter focus mode',exact:true})); await click(page.getByRole('button',{name:'Fit graph to view',exact:true}))
    await at(123)
    if(errors.length)throw new Error(errors.join('; '))
    complete=true
  } finally {
    await context.close()
    const filename=await video.path()
    await fs.writeFile(path.join(out,'recording-metadata.json'),JSON.stringify({complete,sourceVideo:filename,width:3840,height:2160,contentStartSeconds:(start-born)/1000,contentSeconds:(Date.now()-start)/1000,errors},null,2))
    console.log('VIDEO',filename)
  }
}
