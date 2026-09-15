// OWNER A builds these in the first hour. B imports them and never re-invents them.
import type { CSSProperties, PropsWithChildren, ReactNode } from 'react'

import type { Warning } from '../../types'
import './tokens.css'

export function Card({ title, right, children }:
  PropsWithChildren<{ title?: ReactNode; right?: ReactNode }>) {
  return (
    <section style={{
      background: 'var(--surface)', border: '1px solid var(--rule)',
      borderRadius: 'var(--radius)', padding: 16, display: 'grid', gap: 'var(--gap)',
    }}>
      {(title || right) && (
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 12 }}>
          <h2 style={{ margin: 0, fontSize: 16 }}>{title}</h2>
          {right}
        </header>
      )}
      {children}
    </section>
  )
}

export function Button({ children, onClick, kind = 'primary', disabled }:
  PropsWithChildren<{ onClick?: () => void; kind?: 'primary' | 'ghost'; disabled?: boolean }>) {
  const base: CSSProperties = {
    font: 'inherit', fontWeight: 500, padding: '8px 14px', borderRadius: 'var(--radius)',
    cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.5 : 1,
  }
  const style: CSSProperties = kind === 'primary'
    ? { ...base, background: 'var(--accent)', color: 'var(--surface)', border: '1px solid var(--accent)' }
    : { ...base, background: 'transparent', color: 'var(--ink)', border: '1px solid var(--rule)' }
  return <button style={style} onClick={onClick} disabled={disabled}>{children}</button>
}

export function Field({ label, value, onChange, rows = 1, placeholder }: {
  label: string; value: string; onChange: (v: string) => void; rows?: number; placeholder?: string
}) {
  const shared: CSSProperties = {
    font: 'inherit', width: '100%', padding: '8px 10px', color: 'var(--ink)',
    background: 'var(--ground)', border: '1px solid var(--rule)', borderRadius: 'var(--radius)',
  }
  return (
    <label style={{ display: 'grid', gap: 5 }}>
      <span style={{ fontSize: 12, letterSpacing: '.08em', textTransform: 'uppercase', color: 'var(--ink-3)' }}>
        {label}
      </span>
      {rows > 1
        ? <textarea style={{ ...shared, resize: 'vertical' }} rows={rows} value={value}
                    placeholder={placeholder} onChange={e => onChange(e.target.value)} />
        : <input style={shared} value={value} placeholder={placeholder}
                 onChange={e => onChange(e.target.value)} />}
    </label>
  )
}

// The warnings panel is a feature, not an error state: the model's risks and the
// validator's issues are the most interesting output this tool produces.
export function Warnings({ items }: { items: Warning[] }) {
  if (!items.length) return null
  return (
    <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gap: 6 }}>
      {items.map((w, i) => (
        <li key={i} style={{
          display: 'grid', gridTemplateColumns: 'auto 1fr', gap: 10, alignItems: 'baseline',
          padding: '8px 10px', borderRadius: 'var(--radius)',
          border: '1px solid ' + (w.severity === 'error' ? 'var(--danger)' : 'var(--rule)'),
          background: w.severity === 'error' ? 'var(--danger-soft)' : 'transparent',
        }}>
          <code style={{ fontSize: 11, color: w.severity === 'error' ? 'var(--danger)' : 'var(--ink-3)' }}>
            {w.code}
          </code>
          <span style={{ fontSize: 14 }}>{w.message}</span>
        </li>
      ))}
    </ul>
  )
}
