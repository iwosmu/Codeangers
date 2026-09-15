// OWNER A. Shell and routing between the two screens.
import { useEffect, useState } from 'react'

import { api } from '../api/client'
import { Button } from '../components/ui'
import { PlanScreen } from '../screens/plan/PlanScreen'
import { SetupScreen } from '../screens/setup/SetupScreen'
import { useAppState } from '../state/store'

export function App() {
  const { state, patch, reassign, locks, exportJson, importJson } = useAppState()
  const [tab, setTab] = useState<'setup' | 'plan'>('setup')
  const [mock, setMock] = useState<boolean | null>(null)

  useEffect(() => { api.health().then(h => setMock(h.mockMode)).catch(() => setMock(null)) }, [])

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', padding: '28px 20px 64px', display: 'grid', gap: 18 }}>
      <header style={{ display: 'flex', gap: 12, alignItems: 'baseline', flexWrap: 'wrap' }}>
        <h1 style={{ margin: 0, fontSize: 24 }}>Codeangers</h1>
        <span style={{ color: 'var(--ink-3)', fontSize: 14 }}>brief and CVs in, a plan out</span>
        {mock && (
          <span className="mono" style={{
            marginLeft: 'auto', fontSize: 11, padding: '3px 8px', borderRadius: 3,
            border: '1px solid var(--rule)', color: 'var(--ink-3)',
          }}>
            MOCK DATA
          </span>
        )}
      </header>

      <nav style={{ display: 'flex', gap: 8 }}>
        <Button kind={tab === 'setup' ? 'primary' : 'ghost'} onClick={() => setTab('setup')}>Setup</Button>
        <Button kind={tab === 'plan' ? 'primary' : 'ghost'} onClick={() => setTab('plan')}>Plan</Button>
        <span style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <Button kind="ghost" onClick={() => navigator.clipboard.writeText(exportJson())}>Copy session</Button>
          <Button kind="ghost" onClick={async () => importJson(await navigator.clipboard.readText())}>
            Paste session
          </Button>
        </span>
      </nav>

      {tab === 'setup'
        ? <SetupScreen state={state} patch={patch} />
        : <PlanScreen state={state} patch={patch} reassign={reassign} locks={locks} />}
    </div>
  )
}
