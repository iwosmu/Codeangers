import { Info } from 'lucide-react'
import { Button, Card, Field } from '../../components/ui'
import { BriefDocument } from '../../components/BriefDocument'
import { SourceUploads, PROJECT_ACCEPT } from '../../components/SourceUploads'
import type { BriefSession } from '../../state/briefs'

export function SetupScreen({ session }: { session: BriefSession }) {
  const { inputs, update, busy, project, generate } = session
  const ready = Boolean(inputs.projectText.trim() || inputs.projectFiles.length)
  return <main id="main-content" className="screen screen-setup">
    <div className="screen-heading"><div><p className="eyebrow">01 · Project brief</p><h2>Start with the idea. Bring what you have.</h2><p>A PRD, a whiteboard photo, a voice note, or a few sentences. Turn them into one shared project brief.</p></div></div>
    <div className="grid-two"><div className="stack"><Card title="Project material" right={<span className="subtle">Text or files</span>}>
      <fieldset disabled={busy} className="input-group"><SourceUploads files={inputs.projectFiles} onChange={projectFiles => update({ projectFiles })} accept={PROJECT_ACCEPT} max={8} title="Drop project files" help="MD, PDF, DOCX, slides, images or audio · up to 8 files. You can also paste a note image here." disabled={busy} />
        <Field label="What are you building?" rows={6} value={inputs.projectText} placeholder="Add context, or leave this empty if your files explain the idea…" onChange={projectText => update({ projectText })} />
      </fieldset><div className="document-actions"><Button disabled={!ready || project.busy} onClick={() => void generate('project')}>{project.busy ? 'Analysing project…' : 'Generate project.md'}</Button><span className="subtle">{inputs.projectFiles.length} attachments · {inputs.projectText.length} characters</span></div>
    </Card><BriefDocument output={project} kind="project" /></div>
    <div className="stack"><Card title="Product setup"><fieldset disabled={busy} className="input-group">
      <Field label="Team / project name" value={inputs.setup.name} onChange={name => update({ setup: { ...inputs.setup, name } })} />
      <Field label="Context" rows={3} placeholder="48h hackathon, theme, deadline…" value={inputs.setup.context} onChange={context => update({ setup: { ...inputs.setup, context } })} />
      <Field label="Known constraints" rows={3} placeholder="Required stack, budget, essential project needs…" value={inputs.setup.constraints} onChange={constraints => update({ setup: { ...inputs.setup, constraints } })} />
    </fieldset><p className="subtle">Shared with both analyses. Include essential project needs here so the team overview can identify relevant evidence gaps.</p></Card>
    <Card title="A shared starting point"><ol className="section-list"><li><strong>01 · Understand the project</strong><p className="subtle">Vision, deliverables, success criteria, and questions to resolve.</p></li><li><strong>02 · Understand the team</strong><p className="subtle">CV-backed strengths and coverage for 2–8 people.</p></li><li><strong>03 · Review and download</strong><p className="subtle">Two Markdown documents to share with your team.</p></li></ol></Card>
    <div className="notice"><Info size={17} aria-hidden="true" /><span>Thin input produces more open questions. Add sources to make the brief more specific.</span></div></div></div>
  </main>
}
