import type { ToolCall } from '../types/chat'

interface Props {
  calls: ToolCall[]
  onReview: (call: ToolCall) => void
}

const labels: Record<string, string> = {
  pending_confirmation: 'Awaiting confirmation', running: 'Running', succeeded: 'Completed',
  denied: 'Denied', expired: 'Expired', failed: 'Failed',
}

export default function ToolActivity({ calls, onReview }: Props) {
  if (calls.length === 0) return null
  return (
    <section aria-label="Tool activity" className="border-t border-gray-200 px-4 py-3">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">Tool activity</h2>
      <div className="space-y-3">
        {calls.map((call) => (
          <article key={call.id} className="border-l-2 border-blue-200 pl-3 text-sm">
            <div className="flex items-center justify-between gap-3">
              <strong className="text-gray-800">{call.tool_name}</strong>
              <span className="text-xs text-gray-500">{labels[call.status] ?? call.status}</span>
            </div>
            <p className="mt-1 text-xs text-gray-500">{call.side_effect === 'write' ? 'Write operation' : 'Read operation'}</p>
            <pre className="mt-2 max-h-28 overflow-auto whitespace-pre-wrap break-words bg-gray-50 p-2 text-xs text-gray-700">{JSON.stringify(call.arguments, null, 2)}</pre>
            {call.impact && <p className="mt-2 text-xs text-gray-600">{call.impact}</p>}
            {call.error && <p className="mt-2 text-xs text-red-600">{call.error}</p>}
            {call.result && <pre className="mt-2 max-h-28 overflow-auto whitespace-pre-wrap break-words bg-green-50 p-2 text-xs text-green-800">{JSON.stringify(call.result, null, 2)}</pre>}
            {call.status === 'pending_confirmation' && call.side_effect === 'write' && (
              <button type="button" onClick={() => onReview(call)} className="mt-2 text-sm font-medium text-blue-700 hover:text-blue-900">Review action</button>
            )}
          </article>
        ))}
      </div>
    </section>
  )
}
