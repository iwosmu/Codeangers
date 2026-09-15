// OWNER B. Stages 3-4: the task graph, the plan, the timeline, the warnings.
//
// The rule that makes a 30-second model call usable: a drag is a local edit plus
// validate.ts. Only the Re-plan button calls the API, and it always sends the
// locked assignments so human decisions survive.
import { useState } from 'react'

import { api, ApiFailure } from '../../api/client'
import { Button, Card, Warnings } from '../../components/ui'
import { parallelismScore } from '../../lib/validate'
import { Timeline } from '../../components/timeline/Timeline'
import type { AppState, Assignment, Warning } from '../../types'

export function PlanScreen({ state, patch, reassign, locks }: {
  state: AppState
  patch: (p: Partial<AppState>) => void
  reassign: (taskId: string, personId: string) => void
  locks: () => Assignment[]
}) {
  const [busy, setBusy] = useState<'tasks' | 'plan' | null>(null)
  const [error, setError] = useState<Warning[]>([])

  const ready = Boolean(state.project && state.people.length)

  async function generateTasks() {
    if (!state.project) return
    setBusy('tasks'); setError([])
    try { patch({ graph: await api.tasks(state.project) }) }
    catch (e) { const f = e as ApiFailure; setError([{ code: f.code, severity: 'error', message: f.message }]) }
    finally { setBusy(null) }
  }

  async function replan() {
    if (!state.project || !state.graph) return
    setBusy('plan'); setError([])
    try {
      patch({ plan: await api.plan(
        { project: state.project, graph: state.graph, people: state.people }, locks()) })
    } catch (e) {
      const f = e as ApiFailure
      setError([{ code: f.code, severity: 'error', message: f.message }])
    } finally { setBusy(null) }
  }

  const score = state.plan ? parallelismScore(state.people, state.plan) : null

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      <Card title="3 — Task graph"
            right={state.graph && <span style={{ fontSize: 12, color: 'var(--ink-3)' }}>
              {state.graph.tasks.length} tasks
            </span>}>
        <Button onClick={generateTasks} disabled={!ready || busy !== null}>
          {busy === 'tasks' ? 'Writing tasks…' : 'Generate tasks'}
        </Button>
        {/* TODO B: editable task list — title, blocks, section, dependencies. */}
      </Card>

      <Card
        title="4 — Plan"
        right={score !== null && (
          <span className="mono" style={{ fontSize: 12, color: 'var(--ink-3)' }}>
            parallelism {score.toFixed(2)}
          </span>
        )}
      >
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <Button onClick={replan} disabled={!state.graph || busy !== null}>
            {busy === 'plan' ? 'Planning… (20–40 s)' : state.plan ? 'Re-plan' : 'Generate plan'}
          </Button>
          {locks().length > 0 && (
            <span style={{ fontSize: 13, color: 'var(--ink-2)', alignSelf: 'center' }}>
              {locks().length} assignment(s) locked by hand — these are kept.
            </span>
          )}
        </div>

        <Warnings items={error} />

        {state.plan && (
          <>
            <Timeline state={state} onReassign={reassign} />
            {/* The model's own reasoning. Free here, expensive with a solver — show it. */}
            <div style={{ display: 'grid', gap: 6 }}>
              {state.people.map(p => state.plan?.rationale[p.id] && (
                <div key={p.id} style={{ fontSize: 14, color: 'var(--ink-2)' }}>
                  <strong style={{ color: 'var(--ink)' }}>{p.name}</strong> — {state.plan.rationale[p.id]}
                </div>
              ))}
            </div>
            <Warnings items={[...(state.plan.issues ?? []), ...(state.plan.risks ?? [])]} />
          </>
        )}
      </Card>
    </div>
  )
}
