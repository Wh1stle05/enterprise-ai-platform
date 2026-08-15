import { useEffect, useRef } from 'react'
import type { Decision, ToolCall } from '../types/chat'

interface Props { call: ToolCall | null; deciding: boolean; onDecide: (decision: Decision) => void; onClose: () => void }

export default function ToolConfirmationDialog({ call, deciding, onDecide, onClose }: Props) {
  const denyRef = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    if (!call) return
    denyRef.current?.focus()
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape' && !deciding) onClose() }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [call, deciding, onClose])
  if (!call) return null
  return (
    <div role="presentation" className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onMouseDown={(event) => { if (event.target === event.currentTarget && !deciding) onClose() }}>
      <div role="dialog" aria-modal="true" aria-labelledby="confirmation-title" className="w-full max-w-lg bg-white p-5 shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <h2 id="confirmation-title" className="text-lg font-semibold text-gray-900">Confirm write operation</h2>
          <button type="button" aria-label="Close confirmation" onClick={onClose} disabled={deciding} className="text-2xl leading-none text-gray-500 disabled:opacity-50">×</button>
        </div>
        <p className="mt-4 text-sm text-gray-700">{call.impact}</p>
        <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-gray-500">Exact parameters</p>
        <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-words bg-gray-50 p-3 text-sm text-gray-800">{JSON.stringify(call.arguments, null, 2)}</pre>
        <div className="mt-5 flex justify-end gap-2">
          <button ref={denyRef} type="button" onClick={() => onDecide('deny')} disabled={deciding} className="border border-gray-300 px-4 py-2 text-sm text-gray-700 disabled:opacity-50">Deny</button>
          <button type="button" onClick={() => onDecide('confirm')} disabled={deciding} className="bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{deciding ? 'Processing...' : 'Confirm action'}</button>
        </div>
      </div>
    </div>
  )
}
