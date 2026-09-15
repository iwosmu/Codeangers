import { CheckCircle2, Layers3, PackageCheck } from 'lucide-react'
import { Button, Card, Field } from '../../components/ui'
import { BriefDocument } from '../../components/BriefDocument'
import { SourceUploads, PROJECT_ACCEPT } from '../../components/SourceUploads'
import type { BriefSession } from '../../state/briefs'

export function SetupScreen({ session }: { session: BriefSession }) {
  const { inputs, update, busy, project, generate } = session
  const ready = Boolean(inputs.projectText.trim() || inputs.projectFiles.length)
  return <main id="main-content" className="screen screen-setup">
    <div className="screen-heading"><div><p className="eyebrow">01 · Project brief</p><h1>Give the project a clear starting point.</h1><p>Bring your idea, notes and constraints. Build a shared brief before the work is assigned.</p></div></div>
    <div className="brief-layout"><Card className="brief-card" title="Describe the project" right={<span className="required-label">Text or files</span>}>
      <fieldset disabled={busy} className="input-group">
        <Field label="Team / project name" value={inputs.setup.name} placeholder="Give your project a name" onChange={name => update({ setup: { ...inputs.setup, name } })} />
        <Field label="What are you building?" rows={7} value={inputs.projectText} placeholder="Who is it for? What should it do? Add the idea here, or upload your project material below…" onChange={projectText => update({ projectText })} />
        <div className="setup-fields"><Field label="Context" rows={3} placeholder="Hackathon theme, duration, deadline…" value={inputs.setup.context} onChange={context => update({ setup: { ...inputs.setup, context } })} /><Field label="Known constraints" rows={3} placeholder="Required stack, budget, essential needs…" value={inputs.setup.constraints} onChange={constraints => update({ setup: { ...inputs.setup, constraints } })} /></div>
        <p className="subtle field-hint">Name, context and constraints are shared with both analyses so team coverage reflects your project.</p>
        <SourceUploads files={inputs.projectFiles} onChange={projectFiles => update({ projectFiles })} accept={PROJECT_ACCEPT} max={8} title="Add project material" help="MD, PDF, DOCX, slides, images or audio. Drop files, choose files, or paste a note image. Up to 8 files." disabled={busy} />
      </fieldset>
      <div className="brief-meta"><span>{inputs.projectText.length} characters</span><span>{inputs.projectFiles.length}/8 attachments</span></div>
      <div className="form-action"><div><strong>A useful brief starts with what you know.</strong><p>Missing details become open questions.</p></div><Button disabled={!ready || busy} onClick={() => void generate('project')}>{project.busy ? 'Analysing brief…' : 'Generate project.md'}</Button></div>
    </Card><aside className="brief-aside"><span className="aside-index">01</span><h2>One idea.<br />A shared direction.</h2><ul className="feature-list"><li><Layers3 size={18} aria-hidden="true" /><span><strong>Problem & vision</strong>Who you are helping and why it matters.</span></li><li><PackageCheck size={18} aria-hidden="true" /><span><strong>Deliverables & boundaries</strong>What the project should produce, and its constraints.</span></li><li><CheckCircle2 size={18} aria-hidden="true" /><span><strong>Success & open questions</strong>What good looks like, with uncertainty made explicit.</span></li></ul><p className="aside-note">A paragraph, a PRD or a whiteboard photo. Start with whatever you have.</p></aside></div>
    <section className="review-section" aria-label="Project document"><BriefDocument output={project} kind="project" /></section>
  </main>
}
