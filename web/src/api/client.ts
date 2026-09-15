import type { ApiResult } from '../types'
import type { BriefInputs, DocumentResult, ProjectBrief, TeamBrief, TaskGraphResult } from './briefTypes'

export class ApiFailure extends Error {
  constructor(public code: string, message: string, public retryable: boolean) { super(message) }
}

async function call<T>(path: string, init: RequestInit): Promise<T> {
  let res: Response
  try { res = await fetch('/api' + path, init) }
  catch { throw new ApiFailure('network', 'Cannot reach the API. Check the connection and retry.', true) }
  if (!(res.headers.get('content-type') ?? '').includes('application/json')) {
    throw new ApiFailure('unavailable', 'The API is unavailable. Check that the backend is running.', true)
  }
  const body = await res.json() as ApiResult<T>
  if (!body.ok) throw new ApiFailure(body.error.code, body.error.message, body.error.retryable)
  if (!res.ok) throw new ApiFailure('unavailable', 'The API could not complete this request.', true)
  return body.data
}

async function brief<T>(kind: 'team' | 'project', inputs: BriefInputs, signal?: AbortSignal): Promise<DocumentResult<T>> {
  const form = new FormData()
  const input = kind === 'team'
    ? { setup: inputs.setup, members: inputs.members.map(({ id, label, text }) => ({ id, label, text })) }
    : { setup: inputs.setup, project_text: inputs.projectText }
  form.append('input', JSON.stringify(input))
  if (kind === 'team') inputs.members.forEach(m => { if (m.file) form.append(`cv:${m.id}`, m.file) })
  else inputs.projectFiles.forEach(file => form.append('project', file))
  const result = await call<DocumentResult<T> | { error: { code: string; message: string; retryable: boolean }; warnings: string[] }>(`/briefs/${kind}`, { method: 'POST', body: form, signal })
  if ('error' in result) throw new ApiFailure(result.error.code, [result.error.message, ...result.warnings].join(' '), result.error.retryable)
  return result
}

export const api = {
  taskGraph: (project_md: string, team_md: string, team_size: number, signal?: AbortSignal) => call<TaskGraphResult>('/task-graph', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ project_md, team_md, team_size }), signal }),
  health: () => call<{ mockMode: boolean; hasKey: boolean }>('/health', { method: 'GET' }),
  team: (inputs: BriefInputs, signal?: AbortSignal) => brief<TeamBrief>('team', inputs, signal),
  project: (inputs: BriefInputs, signal?: AbortSignal) => brief<ProjectBrief>('project', inputs, signal),
}
