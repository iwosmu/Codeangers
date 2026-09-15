// OWNER B. One lane per person, one bar per task, blocks on the x axis.
// Placeholder rendering — replace with the real board, keep the props.
import { Fragment } from 'react'

import type { AppState } from '../../types'

export function Timeline({ state, onReassign }: {
  state: AppState
  onReassign: (taskId: string, personId: string) => void
}) {
  const plan = state.plan
  const graph = state.graph
  if (!plan || !graph) return null

  const horizon = Math.max(1, ...plan.assignments.map(a => a.endBlock))
  const titleOf = (id: string) => graph.tasks.find(t => t.id === id)?.title ?? id
  const critical = new Set(plan.metrics?.criticalPath ?? [])

  return (
    <div className="timeline-shell">
      <div style={{
        display: 'grid',
        gridTemplateColumns: `120px repeat(${horizon}, minmax(22px, 1fr))`,
        rowGap: 6, minWidth: 720,
      }}>
        {state.people.map((p, row) => (
          <Fragment key={p.id}>
            <div className="mono" style={{
              gridColumn: 1, gridRow: row + 1, display: 'flex', alignItems: 'center',
              fontSize: 12, fontWeight: 600, paddingRight: 10,
            }}>
              {p.name}
            </div>
            {plan.assignments.filter(a => a.personId === p.id).map(a => (
              <div
                key={a.taskId}
                title={titleOf(a.taskId)}
                onClick={() => onReassign(a.taskId, p.id)}
                style={{
                  gridRow: row + 1,
                  gridColumn: `${a.startBlock + 2} / span ${Math.max(1, a.endBlock - a.startBlock)}`,
                  height: 26, display: 'flex', alignItems: 'center', padding: '0 6px',
                  fontSize: 11, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                  borderRadius: 2, cursor: 'pointer',
                  background: critical.has(a.taskId) ? 'var(--danger-soft)' : 'var(--accent-soft)',
                  border: '1px solid ' + (a.locked ? 'var(--accent)' : 'transparent'),
                }}
              >
                {titleOf(a.taskId)}
              </div>
            ))}
          </Fragment>
        ))}
      </div>
    </div>
  )
}
