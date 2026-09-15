// OWNER A. The only file that knows fetch exists.
import type {
  ApiResult, AppState, Assignment, PersonProfile, Plan, ProjectModel, TaskGraph,
} from '../types'

// Flip to true to develop against fixtures even when the API has real prompts.
export const FORCE_MOCK = false

// Empty by default: in dev the Vite proxy forwards /api, and on Render the static
// site rewrites /api to the API service -- both same-origin, so no CORS anywhere.
// Set VITE_API_BASE only if the two halves ever live on different origins.
const BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '')

export class ApiFailure extends Error {
  constructor(public code: string, message: string, public retryable: boolean) {
    super(message)
  }
}

async function call<T>(path: string, init: RequestInit): Promise<Ok<T>['data']> {
  const headers = new Headers(init.headers)
  if (FORCE_MOCK) headers.set('x-mock', '1')

  const res = await fetch(BASE + '/api' + path, { ...init, headers })
  const body = (await res.json()) as ApiResult<T>

  if (!body.ok) throw new ApiFailure(body.error.code, body.error.message, body.error.retryable)
  if (body.warnings.length) console.warn(path, body.warnings)
  return body.data
}

type Ok<T> = Extract<ApiResult<T>, { ok: true }>

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  health: () => call<{ mockMode: boolean; hasKey: boolean }>('/health', { method: 'GET' }),

  project: (brief: string, horizonHours = 24, teamSize = 5) =>
    call<ProjectModel>('/project', json({ brief, horizonHours, teamSize })),

  cv: (input: { name?: string; text?: string; file?: File }) => {
    const form = new FormData()
    if (input.name) form.append('name', input.name)
    if (input.text) form.append('text', input.text)
    if (input.file) form.append('file', input.file)
    return call<PersonProfile>('/cv', { method: 'POST', body: form })
  },

  tasks: (project: ProjectModel) => call<TaskGraph>('/tasks', json({ project })),

  // The slow one: 20-40 s. Only ever called from an explicit Re-plan click.
  plan: (s: Required<Pick<AppState, 'project' | 'graph'>> & { people: PersonProfile[] },
         locks: Assignment[] = []) =>
    call<Plan>('/plan', json({ project: s.project, people: s.people, graph: s.graph, locks })),
}
