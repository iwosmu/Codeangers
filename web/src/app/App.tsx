import { ArrowLeft, ArrowRight, Check, ClipboardCheck, Copy, Navigation } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { Button } from '../components/ui'
import { AssignmentScreen } from '../screens/assignment/AssignmentScreen'
import { PlanScreen } from '../screens/plan/PlanScreen'
import { SetupScreen } from '../screens/setup/SetupScreen'
import { useAppState } from '../state/store'

const steps = ['Project brief', 'Team & task flow', 'Assignments']

export function App() {
  const { state, patch, reassign, locks, exportJson, importJson } = useAppState()
  const [step, setStep] = useState(1); const [mock, setMock] = useState<boolean | null>(null)
  useEffect(() => { api.health().then(result => setMock(result.mockMode)).catch(() => setMock(null)) }, [])
  const canContinue = step === 1 ? Boolean(state.project) : step === 2 ? Boolean(state.plan) : true
  const nextCopy = step === 1 ? 'Continue to task flow' : step === 2 ? 'Review assignments' : 'Plan is ready'
  return <div className="app-shell taskpilot-shell"><a className="skip-link" href="#main-content">Skip to content</a><header className="app-header"><div className="brand-mark"><Navigation size={21} aria-hidden="true" /></div><div className="brand-copy"><h1>TaskPilot</h1><p>From project scope to clear ownership.</p></div>{mock && <span className="status"><span aria-hidden="true">●</span> Demo workspace</span>}</header>
    <section className="wizard-progress" aria-label={`Step ${step} of 3`}><div><p className="eyebrow">Workflow</p><strong>Step {step} of 3</strong></div><ol>{steps.map((label, index) => { const number = index + 1; return <li key={label} className={number === step ? 'current' : number < step ? 'complete' : ''}><span>{number < step ? <Check size={14} aria-hidden="true" /> : number}</span><small>{label}</small></li> })}</ol><div className="wizard-tools"><Button kind="ghost" onClick={() => navigator.clipboard.writeText(exportJson())}><Copy size={15} aria-hidden="true" /> Copy</Button><Button kind="ghost" onClick={async () => importJson(await navigator.clipboard.readText())}><ClipboardCheck size={15} aria-hidden="true" /> Paste</Button></div></section>
    {step === 1 && <SetupScreen state={state} patch={patch} onProjectReady={() => setStep(2)} />}{step === 2 && <PlanScreen state={state} patch={patch} locks={locks} />}{step === 3 && <AssignmentScreen state={state} reassign={reassign} />}
    <footer className="wizard-actions"><div>{step > 1 && <Button kind="secondary" onClick={() => setStep(current => current - 1)}><ArrowLeft size={17} aria-hidden="true" /> Back</Button>}</div><div>{step < 3 ? <><span className="wizard-hint">{canContinue ? 'Your progress is saved in this session.' : step === 1 ? 'Enter your brief to start the next step.' : 'Generate the task plan to continue.'}</span><Button onClick={() => setStep(current => current + 1)} disabled={!canContinue}>{nextCopy} <ArrowRight size={17} aria-hidden="true" /></Button></> : <span className="wizard-finish"><Check size={17} aria-hidden="true" /> Human review complete</span>}</div></footer>
  </div>
}
