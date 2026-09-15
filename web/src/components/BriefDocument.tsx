import { useState, type ReactNode } from 'react'
import { Download, FileText } from 'lucide-react'
import type { DocumentResult, Output } from '../api/briefTypes'
import { Card } from './ui'

const plain = (text: string) => text.replace(/\\([\\`*_{}\[\]<>|#+.\-])/g, '$1')
function Markdown({ text }: { text: string }) {
  const lines = text.split('\n'), blocks: ReactNode[] = []
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    if (!line.trim()) continue
    const heading = /^(#{1,3}) (.*)$/.exec(line)
    if (heading) { const Tag = `h${Number(heading[1].length) + 1}` as 'h2' | 'h3' | 'h4'; blocks.push(<Tag key={i}>{plain(heading[2])}</Tag>); continue }
    if (line.startsWith('| ')) {
      const rows: string[][] = [], key = i
      while (i < lines.length && lines[i].startsWith('| ')) {
        rows.push(lines[i].slice(1, -1).split(/(?<!\\)\|/).map(cell => plain(cell.trim()))); i++
      }
      i--
      blocks.push(<div className="table-scroll" key={key}><table><thead><tr>{rows[0].map((cell, j) => <th key={j}>{cell}</th>)}</tr></thead><tbody>{rows.slice(2).map((row, j) => <tr key={j}>{row.map((cell, k) => <td key={k}>{cell}</td>)}</tr>)}</tbody></table></div>); continue
    }
    if (line.startsWith('- ')) {
      const items: string[] = [], key = i
      while (i < lines.length && lines[i].startsWith('- ')) { items.push(lines[i].slice(2)); i++ }
      i--; blocks.push(<ul key={key}>{items.map((item, j) => <li key={j}>{plain(item)}</li>)}</ul>); continue
    }
    blocks.push(<p key={i}>{plain(line)}</p>)
  }
  return <article className="brief-markdown">{blocks}</article>
}
export function DownloadDocument({ document }: { document: DocumentResult<unknown> }) {
  return <form method="post" action={`/api/download/${document.filename}`}><input type="hidden" name="markdown" value={document.markdown} /><button className="button button-secondary" type="submit"><Download size={16} aria-hidden="true" /> Download {document.filename}</button></form>
}
export function BriefDocument({ output, kind }: { output: Output<unknown>; kind: 'team' | 'project' }) {
  const [raw, setRaw] = useState(false)
  return <Card title={<><FileText size={16} aria-hidden="true" /> {kind}.md</>} right={output.document && <span className="pill">{(output.document.ms / 1000).toFixed(1)}s</span>}>
    {output.busy && <p role="status">Reading sources and generating {kind}.md… You can move between steps while this runs.</p>}
    {output.error && <p className="notice" role="alert">{output.error}</p>}
    {!output.document && !output.busy && !output.error && <p className="muted">Your {kind} document will appear here after generation.</p>}
    {output.document && <><div className="document-actions"><DownloadDocument document={output.document} /><button className="button button-ghost" onClick={() => setRaw(!raw)}>{raw ? 'Read document' : 'View Markdown'}</button></div>
      {output.document.warnings.length > 0 && <details><summary>Review notes ({output.document.warnings.length})</summary><ul>{output.document.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul></details>}
      <div className="document-body">{raw ? <pre>{output.document.markdown}</pre> : <Markdown text={output.document.markdown} />}</div></>}
  </Card>
}
