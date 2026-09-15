import { Info } from 'lucide-react'
import { useState } from 'react'
import { api, ApiFailure } from '../../api/client'
import { Button, Card, Field, Warnings } from '../../components/ui'
import type { AppState, Warning } from '../../types'

export function SetupScreen({ state, patch, onProjectReady }: { state: AppState; patch: (p: Partial<AppState>) => void; onProjectReady: () => void }) {
  const [busy, setBusy] = useState(false); const [error, setError] = useState<Warning[]>([])
  async function generateProject() { setBusy(true); setError([]); try { patch({ project: await api.project(state.brief) }); onProjectReady() } catch (e) { const f = e as ApiFailure; setError([{ code: f.code, severity: 'error', message: f.message }]) } finally { setBusy(false) } }
  function handleBriefKey(event: React.KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); if (!busy && state.brief.trim().length >= 20) void generateProject() } }
  return <main id="main-content" className="screen screen-setup">
    <div className="screen-heading"><div><p className="eyebrow">01 · Intake</p><h2>Start with the brief and the people.</h2><p>Turn a messy project description and CVs into a shared, editable planning input.</p></div></div>
    <div className="grid-two"><div className="stack">
      <Card title="Project brief" right={<span className="subtle">Required</span>}><Field label="What are you building?" rows={7} value={state.brief} placeholder="Describe the outcome, deadline, team constraints and success criteria…" onChange={brief => patch({ brief })} onKeyDown={handleBriefKey} /><div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}><span className="subtle">{state.brief.length} characters · Enter to analyse · Shift + Enter for a new line</span><Button onClick={generateProject} disabled={busy || state.brief.length < 20}>{busy ? 'Analysing brief…' : 'Analyse and continue'}</Button></div></Card>
      {state.project && <Card title="Project sections" right={<span className="pill">{state.project.sections.length} sections</span>}><p className="muted" style={{ marginTop: 0 }}>Review this before tasks are created. The whole plan depends on these boundaries.</p><ul className="section-list">{state.project.sections.map(section => <li key={section.id}><div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}><strong>{section.name}</strong><span className="subtle">{section.minPeople}–{section.maxPeople} people</span></div><p className="muted" style={{ margin: '4px 0 8px', fontSize: 13 }}>{section.description}</p><div className="skill-tags">{section.needs.map(need => <span className="skill-tag" key={need}>{need}</span>)}</div></li>)}</ul></Card>}
    </div><div className="stack"><Card title="What happens next"><p className="muted" style={{ marginTop: 0 }}>Once your brief is analysed, the next screen opens automatically.</p><ol className="section-list"><li><strong>01</strong><p className="subtle" style={{ margin: '4px 0 0' }}>Add the team CVs.</p></li><li><strong>02</strong><p className="subtle" style={{ margin: '4px 0 0' }}>Generate parallel tasks.</p></li><li><strong>03</strong><p className="subtle" style={{ margin: '4px 0 0' }}>Review the suggested ownership.</p></li></ol></Card><div className="notice"><Info size={17} aria-hidden="true" /><span><strong>Demo tip:</strong> mock mode supplies predictable results, so frontend work can continue without a Gemini key.</span></div></div></div><Warnings items={error} />
  </main>
}
