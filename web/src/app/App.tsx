import { ArrowLeft, ArrowRight, Check, Navigation } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { Button } from '../components/ui'
import { AssignmentScreen } from '../screens/assignment/AssignmentScreen'
import { PlanScreen } from '../screens/plan/PlanScreen'
import { SetupScreen } from '../screens/setup/SetupScreen'
import { useBriefs } from '../state/briefs'
import '../components/ui/briefs.css'

const steps = ['Project brief', 'Team overview', 'Review & download']
export function App() {
  const session = useBriefs()
  const [step, setStep] = useState(1)
  const [connection, setConnection] = useState('Connecting to API…')
  useEffect(() => { api.health().then(result => setConnection(result.hasKey ? 'Gemini connected' : 'Add the Gemini key to .env.local')).catch(() => setConnection('API unavailable — check the backend')) }, [])
  const complete = [Boolean(session.project.document), Boolean(session.team.document), Boolean(session.project.document && session.team.document)]
  return <div className="app-shell taskpilot-shell"><a className="skip-link" href="#main-content">Skip to content</a><header className="app-header"><div className="brand-mark"><Navigation size={21} aria-hidden="true" /></div><div className="brand-copy"><h1>TaskPilot</h1><p>From rough inputs to a shared starting point.</p></div><span className="status">{connection}</span></header>
    <nav className="wizard-progress" aria-label="Workspace steps"><div><p className="eyebrow">Workflow</p><strong>Step {step} of 3</strong></div><ol>{steps.map((label, i) => <li key={label} className={i + 1 === step ? 'current' : complete[i] ? 'complete' : ''}><button className="step-link" aria-current={i + 1 === step ? 'step' : undefined} onClick={() => setStep(i + 1)}><span>{complete[i] ? <Check size={14} aria-hidden="true" /> : i + 1}</span><small>{label}</small></button></li>)}</ol><div className="wizard-tools"><Button kind="ghost" onClick={() => { session.reset(); setStep(1) }}>Clear session</Button></div></nav>
    {session.busy && <div className="generation-status" role="status">{session.project.busy ? 'project.md is generating. ' : ''}{session.team.busy ? 'team.md is generating. ' : ''}Each document appears as soon as it is ready.</div>}
    {step === 1 && <SetupScreen session={session} />}{step === 2 && <PlanScreen session={session} />}{step === 3 && <AssignmentScreen session={session} />}
    <footer className="wizard-actions"><div>{step > 1 && <Button kind="secondary" onClick={() => setStep(step - 1)}><ArrowLeft size={17} aria-hidden="true" /> Back</Button>}</div><div><span className="wizard-hint">Inputs and results stay in this browser session.</span>{step < 3 ? <Button onClick={() => setStep(step + 1)}>{step === 1 ? 'Continue to team' : 'Review documents'}<ArrowRight size={17} aria-hidden="true" /></Button> : complete[2] && <span className="wizard-finish"><Check size={17} aria-hidden="true" /> Both documents ready for review</span>}</div></footer>
  </div>
}
