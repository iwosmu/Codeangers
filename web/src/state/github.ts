import { useState } from 'react'
import { api } from '../api/client'
import type { ExportInput, ExportPreview, ExportResult } from '../api/githubTypes'

export function useGithub() {
  const [profiles, setProfiles] = useState<Record<string, string>>({})
  const [owners, setOwners] = useState<Record<number, string[]>>({})
  const [repository, setRepository] = useState('')
  const [token, setToken] = useState('')
  const [preview, setPreview] = useState<ExportPreview>()
  const [snapshot, setSnapshot] = useState<ExportInput>()
  const [result, setResult] = useState<ExportResult>()
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [started, setStarted] = useState(false)
  function invalidate() { if (!started) { setPreview(undefined); setSnapshot(undefined); setError('') } }
  function reset() { setProfiles({}); setOwners({}); setRepository(''); setToken(''); setPreview(undefined); setSnapshot(undefined); setResult(undefined); setError(''); setStarted(false) }
  async function review(input: Omit<ExportInput, 'export_id'>) {
    if (busy || started) return
    setBusy(true); setError(''); setPreview(undefined)
    const data = { ...input, export_id: crypto.randomUUID() }
    try { setPreview(await api.githubPreview(data, token)); setSnapshot(data) }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not prepare export.') }
    finally { setBusy(false) }
  }
  async function publish() {
    if (busy || !snapshot || result?.complete) return
    setBusy(true); setStarted(true); setError('')
    try { setResult(await api.githubExport(snapshot, token)) }
    catch (e) { setError(e instanceof Error ? e.message : 'Export interrupted. Resume to reconcile existing issues.') }
    finally { setBusy(false) }
  }
  return { profiles, setProfiles, owners, setOwners, repository, setRepository, token, setToken, preview, result, error, busy, started, invalidate, reset, review, publish }
}
