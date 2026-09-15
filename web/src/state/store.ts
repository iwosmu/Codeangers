// OWNER A. One store, one owner. B reads it and emits edits; B never mutates it.
import { useCallback, useState } from 'react'

import { validatePlan } from '../lib/validate'
import type { Assignment, AppState, Plan } from '../types'

const EMPTY: AppState = { brief: '', people: [] }

export function useAppState() {
  const [state, setState] = useState<AppState>(EMPTY)

  const patch = useCallback((p: Partial<AppState>) => setState(s => ({ ...s, ...p })), [])

  // A drag never calls the model. Local edit, local re-validation, instant feedback.
  const reassign = useCallback((taskId: string, personId: string) => {
    setState(s => {
      if (!s.plan || !s.project || !s.graph) return s
      const assignments = s.plan.assignments.map(a =>
        a.taskId === taskId ? { ...a, personId, locked: true } : a)
      const next: Plan = { ...s.plan, assignments }
      next.issues = validatePlan(s.project, s.people, s.graph, next)
      return { ...s, plan: next }
    })
  }, [])

  const locks = useCallback((): Assignment[] =>
    state.plan?.assignments.filter(a => a.locked) ?? [], [state.plan])

  const reset = useCallback(() => setState(EMPTY), [])

  // The whole session is one JSON object: export, import, and the offline path at once.
  const exportJson = useCallback(() => JSON.stringify(state, null, 2), [state])
  const importJson = useCallback((text: string) => setState(JSON.parse(text) as AppState), [])

  return { state, patch, reassign, locks, reset, exportJson, importJson }
}
