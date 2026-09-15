import { ArrowLeft, Check, LockKeyhole, Route } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import { Button } from '../components/ui'
import { AssignmentScreen } from '../screens/assignment/AssignmentScreen'
import { PlanScreen } from '../screens/plan/PlanScreen'
import { SetupScreen } from '../screens/setup/SetupScreen'
import { TeamScreen } from '../screens/team/TeamScreen'
import { useAppState } from '../state/store'

const steps = ['Project Brief', 'Team Overview', 'Team & Task Flow', 'Assignments']

export function App() {
  const { state, patch, reassign, locks } = useAppState()
  const [step, setStep] = useState(1)
  const [mock, setMock] = useState<boolean | null>(null)
  useEffect(() => { api.health().then(result => setMock(result.mockMode)).catch(() => setMock(true)) }, [])
  const unlockedThrough = useMemo(() => !state.project ? 1 : !state.people.length ? 2 : !state.graph || !state.plan ? 3 : 4, [state.project, state.people.length, state.graph, state.plan])
  const goTo = (target: number) => { if (target <= unlockedThrough) setStep(target) }
  return <div className="app-shell taskpilot-shell">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <header className="app-header"><button className="brand-button" onClick={() => setStep(1)} aria-label="TaskPilot home — return to Project Brief"><span className="brand-mark" aria-hidden="true"><Route size={22} /></span><span className="brand-copy"><strong>TaskPilot</strong><small>Plan clearly. Assign deliberately.</small></span></button>{mock && <span className="status">Demo workspace</span>}</header>
    <nav className="wizard-progress" aria-label={`Product progress, step ${step} of 4`}><div className="progress-summary"><p className="eyebrow">Workflow</p><strong>Step {step} of 4</strong></div><ol>{steps.map((label, index) => { const number = index + 1; const locked = number > unlockedThrough; return <li key={label} className={number === step ? 'current' : number < step ? 'complete' : locked ? 'locked' : ''}><button onClick={() => goTo(number)} aria-disabled={locked} tabIndex={locked ? -1 : 0} aria-current={number === step ? 'step' : undefined} aria-label={`${label}${locked ? ', locked' : ''}`}><span>{number < step ? <Check size={14} aria-hidden="true" /> : locked ? <LockKeyhole size={13} aria-hidden="true" /> : number}</span><small>{label}</small></button></li> })}</ol><span className="progress-count" aria-hidden="true">{Math.round((step / steps.length) * 100)}%</span></nav>
    {step === 1 && <SetupScreen state={state} patch={patch} onProjectReady={() => setStep(2)} />}
    {step === 2 && <TeamScreen state={state} patch={patch} isDemo={Boolean(mock)} onContinue={() => setStep(3)} />}
    {step === 3 && <PlanScreen state={state} patch={patch} locks={locks} onPlanReady={() => setStep(4)} />}
    {step === 4 && <AssignmentScreen state={state} reassign={reassign} />}
    {step > 1 && <footer className="wizard-actions"><Button kind="secondary" onClick={() => setStep(current => current - 1)}><ArrowLeft size={17} /> Back to {steps[step - 2]}</Button><span className="wizard-hint">Progress is saved in this session.</span></footer>}
  </div>
}
