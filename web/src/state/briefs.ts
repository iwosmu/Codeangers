import { useGithub } from './github'
import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { BriefInputs, Output, ProjectBrief, TeamBrief, TaskGraphResult } from '../api/briefTypes'

const empty = (): BriefInputs => ({ setup: { name: '', context: '', constraints: '' }, members: [1, 2].map(i => ({ id: `m${i}`, label: '', text: '' })), projectText: '', projectFiles: [] })
export function useBriefs() {
  const github = useGithub()
  const [inputs, setInputs] = useState<BriefInputs>(empty)
  const [team, setTeam] = useState<Output<TeamBrief>>({ busy: false })
  const [project, setProject] = useState<Output<ProjectBrief>>({ busy: false })
  const [flow, setFlow] = useState<{ result?: TaskGraphResult; busy: boolean; error?: string }>({ busy: false })
  const requests = useRef<Partial<Record<'team' | 'project' | 'flow', AbortController>>>({})
  useEffect(() => () => { Object.values(requests.current).forEach(c => c?.abort()) }, [])
  const busy = team.busy || project.busy || flow.busy || github.busy
  function update(patch: Partial<BriefInputs>) {
    if (busy) return
    github.reset()
    setFlow({ busy: false })
    setInputs(current => ({ ...current, ...patch }))
    if (patch.setup || patch.members) setTeam({ busy: false })
    if (patch.setup || patch.projectText !== undefined || patch.projectFiles) setProject({ busy: false })
  }
  async function generate(kind: 'team' | 'project') {
    if (busy || requests.current[kind] || requests.current.flow) return
    github.reset()
    setFlow({ busy: false })
    const controller = new AbortController()
    requests.current[kind] = controller
    const setOutput = kind === 'team' ? setTeam : setProject
    setOutput({ busy: true })
    try {
      if (kind === 'team') {
        const document = await api.team(inputs, controller.signal)
        if (!controller.signal.aborted) setTeam({ busy: false, document })
      } else {
        const document = await api.project(inputs, controller.signal)
        if (!controller.signal.aborted) setProject({ busy: false, document })
      }
    } catch (error) {
      if (!controller.signal.aborted) setOutput({ busy: false, error: error instanceof Error ? error.message : 'Generation failed. Please retry.' })
    } finally { if (requests.current[kind] === controller) delete requests.current[kind] }
  }
  async function generateFlow() {
    if (busy || requests.current.flow || !team.document || !project.document) return
    github.reset()
    const controller = new AbortController()
    requests.current.flow = controller
    setFlow({ busy: true })
    try {
      const result = await api.taskGraph(project.document.markdown, team.document.markdown, team.document.structured.members.length, controller.signal)
      if (!controller.signal.aborted) setFlow({ busy: false, result })
    } catch (error) {
      if (!controller.signal.aborted) setFlow({ busy: false, error: error instanceof Error ? error.message : 'Task planning failed. Please retry.' })
    } finally { if (requests.current.flow === controller) delete requests.current.flow }
  }
  function reset() {
    if (github.busy) return
    github.reset()
    Object.values(requests.current).forEach(c => c?.abort())
    requests.current = {}
    setFlow({ busy: false }); setInputs(empty()); setTeam({ busy: false }); setProject({ busy: false })
  }
  return { github, inputs, update, team, project, flow, generate, generateFlow, busy, reset }
}
export type BriefSession = ReturnType<typeof useBriefs>
