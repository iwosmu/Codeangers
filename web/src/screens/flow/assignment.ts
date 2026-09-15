import type { AssignmentResult, TaskFit } from '../../api/briefTypes'

export const fitLabels = { direct: 'Direct match', adjacent: 'Closest skillset · learning needed', unconfirmed: 'Fit unconfirmed' }

export function sameOwners(a: string[] = [], b: string[] = []) {
  return a.length === b.length && a.every(id => b.includes(id))
}
export function currentAssignment(result: AssignmentResult | undefined, owners: Record<number, string[]>) {
  return Boolean(result && Object.entries(result.owners).every(([id, assigned]) => sameOwners(assigned, owners[Number(id)])))
}
export function taskFitLabel(fit: TaskFit | undefined, owners: string[]) {
  if (!fit) return ''
  if (!sameOwners(fit.matches.map(m => m.member_id), owners)) return 'Owner changed · review fit'
  if (fit.matches.some(m => m.match === 'unconfirmed')) return 'Fit unconfirmed'
  if (fit.team_missing_skills.length || fit.matches.some(m => m.match === 'adjacent')) return 'Learning needed'
  return 'Direct match'
}
