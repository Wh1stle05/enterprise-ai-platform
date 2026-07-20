export interface Conversation {
  id: string
  title: string
  message_count: number
  created_at: string
}

export interface ConversationCreate {
  title?: string
}

export interface ConversationDetail {
  id: string
  title: string
  created_at: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'tool' | string
  content: string
  metadata?: Record<string, unknown>
  created_at: string
}

export type RunStatus = 'running' | 'waiting_confirmation' | 'completed' | 'limit_reached' | 'failed'
export type ToolCallStatus = 'pending_confirmation' | 'running' | 'succeeded' | 'denied' | 'expired' | 'failed'
export type Decision = 'confirm' | 'deny'

export interface ToolCall {
  id: string
  run_id: string
  step_number?: number
  provider_call_id: string
  tool_name: string
  arguments: Record<string, unknown>
  side_effect: 'read' | 'write'
  impact: string
  status: ToolCallStatus
  result: Record<string, unknown> | null
  error: string | null
  expires_at: string | null
  created_at?: string
}

export interface AgentTurn {
  run_id: string
  status: RunStatus
  messages?: Message[]
  tool_calls?: ToolCall[]
  answer: string | null
  tool_call: ToolCall | null
  step_count: number
  elapsed_ms: number
}

export type ToolCallResponse = ToolCall
