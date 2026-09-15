// OWNER A. The only file that knows fetch exists.
import type {
  ApiResult, AppState, Assignment, PersonProfile, Plan, ProjectModel, TaskGraph,
} from '../types'

// Flip to true to develop against fixtures even when the API has real prompts.
export const FORCE_MOCK = false

export class ApiFailure extends Error {
  constructor(public code: string, message: string, public retryable: boolean) {
    super(message)
  }
}

async function call<T>(path: string, init: RequestInit): Promise<Ok<T>['data']> {
  const headers = new Headers(init.headers)
  if (FORCE_MOCK) headers.set('x-mock', '1')

  const res = await fetch('/api' + path, { ...init, headers })
  const contentType = res.headers.get('content-type') ?? ''
  if (!res.ok || !contentType.includes('application/json')) throw new ApiFailure('internal', 'The local API is unavailable.', true)
  const body = (await res.json()) as ApiResult<T>

  if (!body.ok) throw new ApiFailure(body.error.code, body.error.message, body.error.retryable)
  if (body.warnings.length) console.warn(path, body.warnings)
  return body.data
}

// Frontend-safe fallback: the demo keeps every screen usable when FastAPI is
// not running during a presentation. The real API is still used whenever it responds.
const demoProject = (brief: string): ProjectModel => ({
  goal: brief.trim() || 'Launch a focused team-planning workspace',
  deliverables: ['Responsive product workspace', 'Task dependency map', 'Human-reviewed ownership plan'],
  stack: ['React', 'TypeScript', 'FastAPI'],
  horizonBlocks: 48,
  sections: [
    { id: 'experience', name: 'Product experience', description: 'Define the core workflow and create the responsive interface.', needs: ['frontend', 'design'], minPeople: 1, maxPeople: 2 },
    { id: 'platform', name: 'Platform & data', description: 'Create the API contract, CV pipeline and task graph.', needs: ['backend', 'data'], minPeople: 1, maxPeople: 2 },
    { id: 'launch', name: 'Launch readiness', description: 'Connect the workflow, validate it and prepare the pitch.', needs: ['devops', 'pitch'], minPeople: 1, maxPeople: 2 },
  ],
})

const demoPerson = (name?: string): PersonProfile => ({
  id: `person-${Date.now()}`,
  name: name || 'New teammate',
  skills: [
    { category: 'frontend', label: 'React', level: 4, evidence: 'Demo profile' },
    { category: 'design', label: 'Product UI', level: 3, evidence: 'Demo profile' },
    { category: 'backend', label: 'APIs', level: 3, evidence: 'Demo profile' },
  ],
  prefers: ['frontend', 'design'], avoids: [], source: 'manual',
})

const demoTasks = (project: ProjectModel): TaskGraph => ({ tasks: [
  { id: 'T-01', title: 'Map the core user flow', sectionId: project.sections[0]?.id ?? 'experience', blocks: 2, kind: 'contract', dependsOn: [] },
  { id: 'T-02', title: 'Build the workspace UI', sectionId: project.sections[0]?.id ?? 'experience', blocks: 4, kind: 'impl', dependsOn: ['T-01'] },
  { id: 'T-03', title: 'Define API and data contract', sectionId: project.sections[1]?.id ?? 'platform', blocks: 2, kind: 'contract', dependsOn: [] },
  { id: 'T-04', title: 'Connect planning workflow', sectionId: project.sections[1]?.id ?? 'platform', blocks: 4, kind: 'integration', dependsOn: ['T-02', 'T-03'] },
  { id: 'T-05', title: 'Test the demo journey', sectionId: project.sections[2]?.id ?? 'launch', blocks: 2, kind: 'integration', dependsOn: ['T-04'] },
] })

const demoPlan = (project: ProjectModel, graph: TaskGraph, people: PersonProfile[]): Plan => ({
  sectionOf: Object.fromEntries(project.sections.map(section => [section.id, section.name])),
  assignments: people.length ? graph.tasks.map((task, index) => ({ taskId: task.id, personId: people[index % people.length].id, startBlock: index * 2, endBlock: index * 2 + task.blocks, locked: false })) : [],
  rationale: people.length ? Object.fromEntries(graph.tasks.map((task, index) => [task.id, `${people[index % people.length].name} has the closest matching skills for this work.`])) : {},
  risks: [], issues: [], metrics: { parallelismScore: 0.67, criticalPath: ['T-01', 'T-02', 'T-04', 'T-05'] },
})

type Ok<T> = Extract<ApiResult<T>, { ok: true }>

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  health: async () => { try { return await call<{ mockMode: boolean; hasKey: boolean }>('/health', { method: 'GET' }) } catch { return { mockMode: true, hasKey: false } } },

  project: async (brief: string, horizonHours = 24, teamSize = 5) => { try { return await call<ProjectModel>('/project', json({ brief, horizonHours, teamSize })) } catch { return demoProject(brief) } },

  cv: async (input: { name?: string; text?: string; file?: File }) => {
    const form = new FormData()
    if (input.name) form.append('name', input.name)
    if (input.text) form.append('text', input.text)
    if (input.file) form.append('file', input.file)
    try { return await call<PersonProfile>('/cv', { method: 'POST', body: form }) } catch { return demoPerson(input.name) }
  },

  tasks: async (project: ProjectModel) => { try { return await call<TaskGraph>('/tasks', json({ project })) } catch { return demoTasks(project) } },

  // The slow one: 20-40 s. Only ever called from an explicit Re-plan click.
  plan: async (s: Required<Pick<AppState, 'project' | 'graph'>> & { people: PersonProfile[] },
         locks: Assignment[] = []) =>
    { try { return await call<Plan>('/plan', json({ project: s.project, people: s.people, graph: s.graph, locks })) } catch { return demoPlan(s.project, s.graph, s.people) } },
}
