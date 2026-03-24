import { TriggersPanel } from '@/components/TriggersPanel'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const jsonResponse = (payload: unknown) =>
  new Response(JSON.stringify(payload), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
const TEST_TRIGGER_FLOW = 'test-planning.dot'

const resolveRequestUrl = (input: RequestInfo | URL): string => {
  if (typeof input === 'string') return input
  if (input instanceof URL) return input.toString()
  return input.url
}

describe('TriggersPanel', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('creates a schedule trigger and refreshes the list', async () => {
    const fetchMock = vi.mocked(global.fetch)
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = resolveRequestUrl(input)
      const method = init?.method ?? 'GET'
      if (url.endsWith('/workspace/api/triggers') && method === 'GET') {
        const payload = fetchMock.mock.calls.filter(
          ([request, requestInit]) => resolveRequestUrl(request as RequestInfo | URL).endsWith('/workspace/api/triggers') && (requestInit?.method ?? 'GET') === 'POST',
        ).length > 0
          ? [
            {
              id: 'trigger-created',
              name: 'Created schedule',
              enabled: true,
              protected: false,
              source_type: 'schedule',
              created_at: '2026-03-22T00:00:00Z',
              updated_at: '2026-03-22T00:00:00Z',
              action: { flow_name: TEST_TRIGGER_FLOW, project_path: null, static_context: {} },
              source: { kind: 'interval', interval_seconds: 300 },
              state: { last_fired_at: null, last_result: null, last_error: null, next_run_at: '2026-03-22T00:05:00Z', recent_history: [] },
            },
          ]
          : []
        return jsonResponse(payload)
      }
      if (url.endsWith('/workspace/api/triggers') && method === 'POST') {
        return jsonResponse({
          id: 'trigger-created',
          name: 'Created schedule',
          enabled: true,
          protected: false,
          source_type: 'schedule',
          created_at: '2026-03-22T00:00:00Z',
          updated_at: '2026-03-22T00:00:00Z',
          action: { flow_name: TEST_TRIGGER_FLOW, project_path: null, static_context: {} },
          source: { kind: 'interval', interval_seconds: 300 },
          state: { last_fired_at: null, last_result: null, last_error: null, next_run_at: '2026-03-22T00:05:00Z', recent_history: [] },
        })
      }
      throw new Error(`Unhandled request: ${method} ${url}`)
    })

    const user = userEvent.setup()
    render(<TriggersPanel />)

    await user.type(screen.getByLabelText('Name'), 'Created schedule')
    await user.clear(screen.getByLabelText('Target Flow'))
    await user.type(screen.getByLabelText('Target Flow'), TEST_TRIGGER_FLOW)
    await user.click(screen.getByTestId('trigger-create-button'))

    await waitFor(() => {
      expect(screen.getByText('Created schedule')).toBeVisible()
    })
  })

  it('shows shared webhook ingress details and regenerates webhook secrets', async () => {
    const fetchMock = vi.mocked(global.fetch)
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = resolveRequestUrl(input)
      const method = init?.method ?? 'GET'
      if (url.endsWith('/workspace/api/triggers') && method === 'GET') {
        return jsonResponse([
          {
            id: 'trigger-webhook',
            name: 'Webhook trigger',
            enabled: true,
            protected: false,
            source_type: 'webhook',
            created_at: '2026-03-22T00:00:00Z',
            updated_at: '2026-03-22T00:00:00Z',
            action: { flow_name: 'webhook.dot', project_path: null, static_context: {} },
            source: { webhook_key: 'webhook-key-1' },
            state: { last_fired_at: null, last_result: null, last_error: null, next_run_at: null, recent_history: [] },
          },
        ])
      }
      if (url.endsWith('/workspace/api/triggers/trigger-webhook') && method === 'PATCH') {
        return jsonResponse({
          id: 'trigger-webhook',
          name: 'Webhook trigger',
          enabled: true,
          protected: false,
          source_type: 'webhook',
          created_at: '2026-03-22T00:00:00Z',
          updated_at: '2026-03-22T00:01:00Z',
          action: { flow_name: 'webhook.dot', project_path: null, static_context: {} },
          source: { webhook_key: 'webhook-key-1' },
          state: { last_fired_at: null, last_result: null, last_error: null, next_run_at: null, recent_history: [] },
          webhook_secret: 'new-webhook-secret',
        })
      }
      throw new Error(`Unhandled request: ${method} ${url}`)
    })

    const user = userEvent.setup()
    render(<TriggersPanel />)

    await user.click(await screen.findByText('Webhook trigger'))
    expect(screen.getByText(/POST JSON to/i)).toBeVisible()
    expect(screen.getAllByText(/webhook-key-1/).length).toBeGreaterThan(0)

    await user.click(screen.getByTestId('trigger-regenerate-secret-button'))

    await waitFor(() => {
      expect(screen.getByText(/new-webhook-secret/)).toBeVisible()
    })
  })
})
