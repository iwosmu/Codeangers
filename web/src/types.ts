// SHARED CONTRACT. The twin of api/app/schemas.py.
// Edit both in one commit and announce it out loud.

export type Category =
  | 'backend' | 'frontend' | 'ml' | 'data'
  | 'design' | 'devops' | 'domain' | 'pitch'

export const CATEGORIES: Category[] = [
  'backend', 'frontend', 'ml', 'data', 'design', 'devops', 'domain', 'pitch',
]

export type Section = {
  id: string
  name: string
  description: string
  needs: Category[]
  minPeople: number
  maxPeople: number
}

export type ProjectModel = {
  goal: string
  deliverables: string[]
  stack: string[]
  sections: Section[]
  horizonBlocks: number          // 30-minute blocks
}

export type Skill = {
  category: Category
  label: string
  level: 1 | 2 | 3 | 4 | 5
  evidence: string               // verbatim quote; empty means drop the skill
}

export type PersonProfile = {
  id: string
  name: string
  skills: Skill[]
  prefers: Category[]
  avoids: Category[]
  source: 'cv' | 'manual'
}

export type Task = {
  id: string
  title: string
  sectionId: string
  blocks: 1 | 2 | 4
  kind: 'contract' | 'impl' | 'integration'
  dependsOn: string[]
}

export type TaskGraph = { tasks: Task[] }

export type Assignment = {
  taskId: string
  personId: string
  startBlock: number
  endBlock: number               // exclusive
  locked: boolean
}

export type Warning = {
  code: string
  message: string
  severity: 'info' | 'warn' | 'error'
  taskIds?: string[]
  personIds?: string[]
}

export type Metrics = { parallelismScore: number; criticalPath: string[] }

export type Plan = {
  sectionOf: Record<string, string>
  assignments: Assignment[]
  rationale: Record<string, string>
  risks: Warning[]               // written by the model
  issues: Warning[]              // written by the validator, never by the model
  metrics?: Metrics
}

// ---- envelope -------------------------------------------------------

export type ErrorCode =
  | 'bad_input' | 'model_invalid_json' | 'model_failed'
  | 'plan_invalid' | 'rate_limited' | 'internal'

export type Ok<T> = {
  ok: true
  data: T
  warnings: Warning[]
  meta: { ms: number; model?: string; mocked: boolean; cacheHit: boolean }
}

export type Err = {
  ok: false
  error: { code: ErrorCode; message: string; retryable: boolean }
}

export type ApiResult<T> = Ok<T> | Err

// ---- app state ------------------------------------------------------

export type AppState = {
  brief: string
  project?: ProjectModel
  people: PersonProfile[]
  graph?: TaskGraph
  plan?: Plan
}
