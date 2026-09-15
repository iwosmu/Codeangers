import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { BriefInputs, Output, ProjectBrief, TeamBrief } from '../api/briefTypes'

const empty = (): BriefInputs => ({ setup: { name: '', context: '', constraints: '' }, members: [1, 2].map(i => ({ id: `m${i}`, label: '', text: '' })), projectText: '', projectFiles: [] })
export function useBriefs() {
  const [inputs, setInputs] = useState<BriefInputs>(empty)
  const [team, setTeam] = useState<Output<TeamBrief>>({ busy: false })
  const [project, setProject] = useState<Output<ProjectBrief>>({ busy: false })
  const requests = useRef<Partial<Record<'team' | 'project', AbortController>>>({})
  useEffect(() => () => { Object.values(requests.current).forEach(c => c?.abort()) }, [])
  const busy = team.busy || project.busy
  function update(patch: Partial<BriefInputs>) {
    if (busy) return
    setInputs(current => ({ ...current, ...patch }))
    if (patch.setup || patch.members) setTeam({ busy: false })
    if (patch.setup || patch.projectText !== undefined || patch.projectFiles) setProject({ busy: false })
  }
  async function generate(kind: 'team' | 'project') {
    if (requests.current[kind]) return
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
  function reset() {
    Object.values(requests.current).forEach(c => c?.abort())
    requests.current = {}
    setInputs(empty()); setTeam({ busy: false }); setProject({ busy: false })
  }
  return { inputs, update, team, project, generate, busy, reset }
}
export type BriefSession = ReturnType<typeof useBriefs>
