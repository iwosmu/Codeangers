import { useRef, useState } from 'react'
import { Upload } from 'lucide-react'
import { Button } from './ui'

export const CV_ACCEPT = '.pdf,.docx,.png,.jpg,.jpeg,.webp,.heic,.heif,.txt,.md'
export const PROJECT_ACCEPT = CV_ACCEPT + ',.pptx,.mp3,.wav,.m4a,.aac,.ogg,.flac,.aiff'
export function SourceUploads({ files, onChange, accept, max, title, help, disabled = false }: { files: File[]; onChange: (files: File[]) => void; accept: string; max: number; title: string; help: string; disabled?: boolean }) {
  const input = useRef<HTMLInputElement>(null)
  const [error, setError] = useState('')
  function add(incoming: File[]) {
    if (disabled || !incoming.length) return
    setError('')
    if (files.length + incoming.length > max) { setError(`Use at most ${max} file${max === 1 ? '' : 's'} here. Remove one before adding more.`); return }
    const extensions = accept.split(',')
    const invalid = incoming.find(f => !extensions.includes('.' + f.name.split('.').pop()?.toLowerCase()) || f.size > 50 * 1024 * 1024)
    if (invalid) { setError(`${invalid.name}: use a supported format under 50 MB.`); return }
    onChange([...files, ...incoming])
  }
  return <div className="source-upload" onPaste={event => { const pasted = Array.from(event.clipboardData.files); if (pasted.length) { event.preventDefault(); add(pasted) } }}>
    <div className="dropzone" onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); add(Array.from(e.dataTransfer.files)) }}>
      <Upload size={22} aria-hidden="true" /><p className="dropzone-title">{title}</p><p className="dropzone-text">{help}</p>
      <input ref={input} aria-label={title} type="file" accept={accept} multiple={max > 1} disabled={disabled} onChange={e => { add(Array.from(e.target.files ?? [])); e.target.value = '' }} />
    </div>
    {files.length > 0 && <ul className="attachment-list">{files.map((file, i) => <li key={`${file.name}-${i}`}><span>{file.name} <small>({(file.size / 1024).toFixed(0)} KB)</small></span><Button kind="ghost" disabled={disabled} onClick={() => { setError(''); onChange(files.filter((_, index) => i !== index)) }}>Remove</Button></li>)}</ul>}
    {error && <p className="notice" role="alert">{error}</p>}
  </div>
}
