// OWNER D. The browser twin of api/app/services/validate.py.
// Runs after every drag, so a human edit gets feedback in milliseconds instead of
// waiting 30 seconds for the model. The two implementations must agree.
import type { PersonProfile, Plan, ProjectModel, TaskGraph, Warning } from '../types'

export function validatePlan(
  project: ProjectModel, people: PersonProfile[], graph: TaskGraph, plan: Plan,
): Warning[] {
  const out: Warning[] = []
  const tasks = new Map(graph.tasks.map(t => [t.id, t]))
  const personIds = new Set(people.map(p => p.id))
  const sectionIds = new Set(project.sections.map(s => s.id))
  const endOf = new Map<string, number>()
  const byPerson = new Map<string, typeof plan.assignments>()
  const nameOf = (id: string) => people.find(p => p.id === id)?.name ?? id

  for (const a of plan.assignments) {
    if (!tasks.has(a.taskId)) {
      out.push({ code: 'unknown_ref', severity: 'error', taskIds: [a.taskId],
        message: `Plan assigns task ${a.taskId}, which is not in the graph.` })
      continue
    }
    if (!personIds.has(a.personId)) {
      out.push({ code: 'unknown_ref', severity: 'error', personIds: [a.personId],
        message: `Plan assigns work to ${a.personId}, who is not on the team.` })
      continue
    }
    endOf.set(a.taskId, a.endBlock)
    const list = byPerson.get(a.personId) ?? []
    list.push(a)
    byPerson.set(a.personId, list)
  }

  // one person, two tasks, same time
  for (const [pid, items] of byPerson) {
    items.sort((x, y) => x.startBlock - y.startBlock)
    for (let i = 1; i < items.length; i++) {
      const prev = items[i - 1], cur = items[i]
      if (cur.startBlock < prev.endBlock) {
        out.push({ code: 'overlap', severity: 'error', personIds: [pid],
          taskIds: [prev.taskId, cur.taskId],
          message: `${nameOf(pid)} is on ${prev.taskId} and ${cur.taskId} at the same time.` })
      }
    }
  }

  // a task that starts before something it depends on has finished
  for (const a of plan.assignments) {
    const t = tasks.get(a.taskId)
    if (!t) continue
    for (const dep of t.dependsOn) {
      const depEnd = endOf.get(dep)
      if (depEnd === undefined) {
        out.push({ code: 'orphan_task', severity: 'error', taskIds: [dep],
          message: `Task ${a.taskId} depends on ${dep}, which nobody is doing.` })
      } else if (a.startBlock < depEnd) {
        out.push({ code: 'dep_violation', severity: 'error', taskIds: [dep, a.taskId],
          message: `${a.taskId} starts at block ${a.startBlock} but ${dep} is not done until ${depEnd}.` })
      }
    }
  }

  for (const t of graph.tasks) {
    if (!endOf.has(t.id)) {
      out.push({ code: 'orphan_task', severity: 'error', taskIds: [t.id],
        message: `Nobody is assigned to ${t.id} (${t.title}).` })
    }
  }

  for (const p of people) {
    const sec = plan.sectionOf[p.id]
    if (!sec) {
      out.push({ code: 'unknown_ref', severity: 'error', personIds: [p.id], message: `${p.name} has no section.` })
    } else if (!sectionIds.has(sec)) {
      out.push({ code: 'unknown_ref', severity: 'error', personIds: [p.id],
        message: `${p.name} is in unknown section ${sec}.` })
    }
    if (!byPerson.get(p.id)?.length) {
      out.push({ code: 'idle_person', severity: 'warn', personIds: [p.id], message: `${p.name} has no tasks at all.` })
    }
  }

  for (const [pid, items] of byPerson) {
    const last = Math.max(...items.map(x => x.endBlock))
    if (last > project.horizonBlocks) {
      out.push({ code: 'over_horizon', severity: 'warn', personIds: [pid],
        message: `${nameOf(pid)} is still working at block ${last}, past the horizon of ${project.horizonBlocks}.` })
    }
  }

  return out
}

// Share of elapsed blocks in which every single person has work. Derived, not guessed.
export function parallelismScore(people: PersonProfile[], plan: Plan): number {
  const horizon = Math.max(0, ...plan.assignments.map(a => a.endBlock))
  if (!horizon || !people.length) return 0
  const index = new Map(people.map((p, i) => [p.id, i]))
  const busy = people.map(() => new Array<boolean>(horizon).fill(false))
  for (const a of plan.assignments) {
    const i = index.get(a.personId)
    if (i === undefined) continue
    for (let b = Math.max(0, a.startBlock); b < Math.min(horizon, a.endBlock); b++) busy[i][b] = true
  }
  let full = 0
  for (let b = 0; b < horizon; b++) if (busy.every(row => row[b])) full++
  return Math.round((full / horizon) * 1000) / 1000
}
