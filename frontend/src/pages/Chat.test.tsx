import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Chat from './Chat'

const call = {
  id: 'call-1', run_id: 'run-1', provider_call_id: 'provider-1', tool_name: 'create_work_ticket',
  arguments: { title: 'Blue screen', description: 'Stops at boot', priority: 'high' }, side_effect: 'write' as const,
  impact: "Create a high priority IT ticket titled 'Blue screen'.", status: 'pending_confirmation' as const,
  result: null, error: null, expires_at: null,
}

vi.mock('../hooks/useAuth', () => ({ useAuth: () => ({ user: { username: 'alice' }, logout: vi.fn() }) }))
vi.mock('../hooks/useChat', () => ({
  useChat: () => ({
    conversations: [{ id: 'conversation-1', title: 'Support', message_count: 0, created_at: '' }],
    messages: [], toolCalls: [call], pendingCall: call, deciding: false, selectedId: 'conversation-1', loading: false, error: null,
    loadConversations: vi.fn(), selectConversation: vi.fn(), newConversation: vi.fn(), sendMessage: vi.fn(),
    reviewToolCall: vi.fn(), closeReview: vi.fn(), decide: vi.fn(),
  }),
}))

describe('chat tool confirmation workflow', () => {
  it('shows exact write arguments and exposes confirmation controls', async () => {
    render(<MemoryRouter><Chat /></MemoryRouter>)
    expect(screen.getByText('create_work_ticket')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Review action' }))
    expect(await screen.findByText('Confirm write operation')).toBeInTheDocument()
    expect(screen.getAllByText(/Blue screen/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/high priority/).length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: 'Deny' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirm action' })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('button', { name: 'Close confirmation' })).toBeInTheDocument())
  })
})
