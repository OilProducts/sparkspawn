import { RunsPanel } from '@/features/runs/RunsPanel'
import { useStore } from '@/store'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const jsonResponse = (payload: unknown) =>
  new Response(JSON.stringify(payload), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })

const resolveRequestUrl = (input: RequestInfo | URL): string => {
  if (typeof input === 'string') return input
  if (input instanceof URL) return input.toString()
  return input.url
}

const resetRunsState = () => {
  useStore.setState({
    viewMode: 'runs',
    activeProjectPath: null,
    selectedRunId: null,
    executionFlow: null,
    projectRegistry: {},
    projectSessionsByPath: {},
    recentProjectPaths: [],
  })
}

const makeRun = (overrides: Partial<Record<string, unknown>> = {}) => ({
  run_id: String(overrides.run_id ?? 'run-1'),
  flow_name: String(overrides.flow_name ?? 'review.dot'),
  status: String(overrides.status ?? 'completed'),
  outcome: (overrides.outcome as 'success' | 'failure' | null | undefined) ?? 'success',
  outcome_reason_code: null,
  outcome_reason_message: null,
  working_directory: String(overrides.working_directory ?? '/tmp/workdir'),
  project_path: String(overrides.project_path ?? '/tmp/project-one'),
  git_branch: 'main',
  git_commit: 'abcdef0',
  spec_id: null,
  plan_id: null,
  model: 'gpt-5.3-codex-spark',
  started_at: '2026-03-22T00:00:00Z',
  ended_at: '2026-03-22T00:05:00Z',
  last_error: null,
  token_usage: 1234,
})

describe('RunsPanel', () => {
  beforeEach(() => {
    resetRunsState()
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('defaults to the active project scope and can switch to all projects', async () => {
    const fetchMock = vi.mocked(global.fetch)
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = resolveRequestUrl(input)
      const method = init?.method ?? 'GET'
      if (method !== 'GET') {
        throw new Error(`Unhandled request: ${method} ${url}`)
      }
      if (url.includes('/attractor/runs?project_path=%2Ftmp%2Fproject-one')) {
        return jsonResponse({
          runs: [
            makeRun({
              run_id: 'run-project-one',
              flow_name: 'project-one.dot',
              project_path: '/tmp/project-one',
            }),
          ],
        })
      }
      if (url.endsWith('/attractor/runs')) {
        return jsonResponse({
          runs: [
            makeRun({
              run_id: 'run-project-one',
              flow_name: 'project-one.dot',
              project_path: '/tmp/project-one',
            }),
            makeRun({
              run_id: 'run-project-two',
              flow_name: 'project-two.dot',
              project_path: '/tmp/project-two',
            }),
          ],
        })
      }
      throw new Error(`Unhandled request: ${method} ${url}`)
    })

    act(() => {
      useStore.getState().registerProject('/tmp/project-one')
      useStore.getState().setActiveProjectPath('/tmp/project-one')
    })

    const user = userEvent.setup()
    render(<RunsPanel />)

    await waitFor(() => {
      expect(screen.getByText('project-one.dot')).toBeVisible()
    })
    expect(
      fetchMock.mock.calls.some(([request]) =>
        resolveRequestUrl(request as RequestInfo | URL).includes('/attractor/runs?project_path=%2Ftmp%2Fproject-one'),
      ),
    ).toBe(true)
    expect(screen.getByText('Run history for the active project.')).toBeVisible()

    await user.click(screen.getByTestId('runs-scope-all-projects'))

    await waitFor(() => {
      expect(screen.getByText('project-two.dot')).toBeVisible()
    })
    expect(
      fetchMock.mock.calls.some(([request]) => {
        const url = resolveRequestUrl(request as RequestInfo | URL)
        return url.endsWith('/attractor/runs') && !url.includes('project_path=')
      }),
    ).toBe(true)
    expect(screen.getByText('Run history across all projects.')).toBeVisible()
  })

  it('shows an explicit no-project notice before fetching all-project runs', async () => {
    const fetchMock = vi.mocked(global.fetch)
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = resolveRequestUrl(input)
      const method = init?.method ?? 'GET'
      if (url.endsWith('/attractor/runs') && method === 'GET') {
        return jsonResponse({
          runs: [
            makeRun({
              run_id: 'run-global',
              flow_name: 'global.dot',
              project_path: '/tmp/project-two',
            }),
          ],
        })
      }
      throw new Error(`Unhandled request: ${method} ${url}`)
    })

    const user = userEvent.setup()
    render(<RunsPanel />)

    expect(screen.getByText('Choose an active project or switch to all projects to view run history.')).toBeVisible()
    expect(fetchMock).not.toHaveBeenCalled()

    await user.click(screen.getByTestId('runs-scope-all-projects'))

    await waitFor(() => {
      expect(screen.getByText('global.dot')).toBeVisible()
    })
    expect(fetchMock).toHaveBeenCalled()
  })
})
