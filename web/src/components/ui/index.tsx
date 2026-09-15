import type { KeyboardEvent, PropsWithChildren, ReactNode } from 'react'
import type { Warning } from '../../types'
import './tokens.css'
import './premium.css'
import './wizard.css'
import './taskpilot.css'
export function Card({ title, right, children, className = '' }: PropsWithChildren<{ title?: ReactNode; right?: ReactNode; className?: string }>) { return <section className={`card ${className}`}>{(title || right) && <header className="card-heading"><h3>{title}</h3>{right}</header>}{children}</section> }
export function Button({ children, onClick, kind = 'primary', disabled, type = 'button' }: PropsWithChildren<{ onClick?: () => void; kind?: 'primary' | 'ghost' | 'secondary'; disabled?: boolean; type?: 'button' | 'submit' }>) { return <button type={type} className={`button button-${kind}`} onClick={onClick} disabled={disabled}>{children}</button> }
export function Field({ label, value, onChange, rows = 1, placeholder, onKeyDown }: { label: string; value: string; onChange: (v: string) => void; rows?: number; placeholder?: string; onKeyDown?: (event: KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) => void }) { return <label className="field"><span className="field-label">{label}</span>{rows > 1 ? <textarea className="input" style={{ resize: 'vertical' }} rows={rows} value={value} placeholder={placeholder} onChange={e => onChange(e.target.value)} onKeyDown={onKeyDown} /> : <input className="input" value={value} placeholder={placeholder} onChange={e => onChange(e.target.value)} onKeyDown={onKeyDown} />}</label> }
export function Warnings({ items }: { items: Warning[] }) { if (!items.length) return null; return <ul className="warning-list">{items.map(w => <li key={`${w.code}-${w.message}`} className={w.severity === 'error' ? 'error' : ''}><strong>{w.code}</strong> — {w.message}</li>)}</ul> }
