import { buildPipelineStartPayload } from '@/lib/pipelineStartPayload'
import { ExecutionControls } from '@/components/ExecutionControls'
import { useStore } from '@/store'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const DEFAULT_WORKING_DIRECTORY = './test-app'

const resetExecutionState = () => {
  useStore.setState((state) => ({
    ...state,
    viewMode: 'projects',
    activeProjectPath: null,
    activeFlow: null,
    executionFlow: null,
    selectedRunId: null,
    workingDir: DEFAULT_WORKING_DIRECTORY,
    runtimeStatus: 'idle',
    humanGate: null,
    projectRegistry: {},
    projectScopedWorkspaces: {},
    projectRegistrationError: null,
    recentProjectPaths: [],
    diagnostics: [],
    nodeDiagnostics: {},
    edgeDiagnostics: {},
    hasValidationErrors: false,
    logs: [],
    nodeStatuses: {},
    selectedNodeId: null,
    selectedEdgeId: null,
  }))
}

describe('Execution controls behavior', () => {
  beforeEach(() => {
    resetExecutionState()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('builds start payload with project, flow, backend model, and traceability ids', () => {
    const payload = buildPipelineStartPayload(
      {
        projectPath: '/tmp/project',
        flowSource: 'implement-spec.dot',
        workingDirectory: '/tmp/project',
        backend: 'codex',
        model: 'gpt-5',
        specArtifactId: 'spec-123',
        planArtifactId: 'plan-456',
      },
      'digraph G { start -> done }',
    )

    expect(payload).toEqual({
      flow_content: 'digraph G { start -> done }',
      working_directory: '/tmp/project',
      backend: 'codex',
      model: 'gpt-5',
      flow_name: 'implement-spec.dot',
      spec_id: 'spec-123',
      plan_id: 'plan-456',
    })
  })

  it('hides footer when execution mode is inactive and no run context exists', () => {
    useStore.setState((state) => ({
      ...state,
      viewMode: 'projects',
      runtimeStatus: 'idle',
      selectedRunId: null,
    }))

    render(<ExecutionControls />)
    expect(screen.queryByTestId('execution-footer-controls')).not.toBeInTheDocument()
  })

  it('shows launch controls in execution mode before a run starts', () => {
    useStore.setState((state) => ({
      ...state,
      viewMode: 'execution',
      activeProjectPath: '/tmp/project',
      activeFlow: 'implement-spec.dot',
      projectScopedWorkspaces: {
        '/tmp/project': {
          activeFlow: 'implement-spec.dot',
          workingDir: '/tmp/project',
          conversationId: null,
          projectEventLog: [],
          specId: 'spec-123',
          specStatus: 'approved',
          specProvenance: null,
          planId: 'plan-456',
          planStatus: 'approved',
          planProvenance: null,
        },
      },
    }))

    render(<ExecutionControls />)

    expect(screen.getByTestId('execution-footer-controls')).toBeVisible()
    expect(screen.getByTestId('execute-button')).toBeVisible()
    expect(screen.queryByTestId('execution-footer-run-status')).not.toBeInTheDocument()
  })

  it('launches from the inspected execution flow without overwriting project flow preference', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
      if (url.includes('/workspace/api/projects/metadata')) {
        return new Response(JSON.stringify({ branch: 'main' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      if (url.endsWith('/attractor/api/flows/run-opened.dot')) {
        return new Response(JSON.stringify({
          name: 'run-opened.dot',
          content: 'digraph run_opened { start -> done }',
        }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      if (url.endsWith('/attractor/pipelines') && init?.method === 'POST') {
        return new Response(JSON.stringify({ status: 'started', pipeline_id: 'run-123' }), {
          status: 202,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      return new Response(JSON.stringify({}), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    })
    vi.stubGlobal('fetch', fetchMock)
    vi.spyOn(window, 'confirm').mockReturnValue(true)

    useStore.setState((state) => ({
      ...state,
      viewMode: 'execution',
      activeProjectPath: '/tmp/project',
      activeFlow: 'preferred.dot',
      executionFlow: 'run-opened.dot',
      projectScopedWorkspaces: {
        '/tmp/project': {
          activeFlow: 'preferred.dot',
          workingDir: '/tmp/project',
          conversationId: null,
          projectEventLog: [],
          specId: null,
          specStatus: null,
          specProvenance: null,
          planId: 'plan-123',
          planStatus: 'approved',
          planProvenance: null,
        },
      },
    }))

    render(<ExecutionControls />)

    await user.click(screen.getByTestId('execute-button'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/attractor/pipelines',
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('"flow_name":"run-opened.dot"'),
        }),
      )
    })
    expect(useStore.getState().activeFlow).toBe('preferred.dot')
    expect(useStore.getState().executionFlow).toBe('run-opened.dot')
  })

  it('renders runtime state and disables unsupported pause/resume controls', () => {
    useStore.setState((state) => ({
      ...state,
      viewMode: 'execution',
      runtimeStatus: 'running',
      selectedRunId: 'run-42',
    }))

    render(<ExecutionControls />)

    expect(screen.getByTestId('execution-footer-controls')).toBeVisible()
    expect(screen.getByTestId('execution-footer-run-status')).toHaveTextContent('Running')
    expect(screen.getByTestId('execution-footer-run-identity')).toHaveTextContent('run-42')
    expect(screen.getByTestId('execution-footer-cancel-button')).toBeEnabled()
    expect(screen.getByTestId('execution-footer-pause-button')).toBeDisabled()
    expect(screen.getByTestId('execution-footer-resume-button')).toBeDisabled()
    expect(screen.getByTestId('execution-footer-unsupported-controls-reason')).toHaveTextContent(
      'Pause/Resume is unavailable',
    )
  })

  it('requests cancel and transitions runtime status to cancel_requested', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ status: 'accepted', pipeline_id: 'run-99' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    vi.spyOn(window, 'confirm').mockReturnValue(true)

    useStore.setState((state) => ({
      ...state,
      viewMode: 'execution',
      runtimeStatus: 'running',
      selectedRunId: 'run-99',
    }))

    render(<ExecutionControls />)
    await user.click(screen.getByTestId('execution-footer-cancel-button'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/attractor/pipelines/run-99/cancel', { method: 'POST' })
    })
    expect(useStore.getState().runtimeStatus).toBe('cancel_requested')
  })

  it('restores running state and alerts when cancel request fails', async () => {
    const user = userEvent.setup()
    vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 500 })))
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => undefined)
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => undefined)

    useStore.setState((state) => ({
      ...state,
      viewMode: 'execution',
      runtimeStatus: 'running',
      selectedRunId: 'run-13',
    }))

    render(<ExecutionControls />)
    await user.click(screen.getByTestId('execution-footer-cancel-button'))

    await waitFor(() => {
      expect(useStore.getState().runtimeStatus).toBe('running')
    })
    expect(consoleErrorSpy).not.toHaveBeenCalled()
    expect(alertSpy).toHaveBeenCalledWith('Failed to request cancel. Check backend logs for details.')
  })

  it('shows pending human gate context when available', () => {
    useStore.setState((state) => ({
      ...state,
      viewMode: 'execution',
      runtimeStatus: 'running',
      selectedRunId: 'run-77',
      humanGate: {
        id: 'gate-1',
        runId: 'run-77',
        nodeId: 'node_review',
        prompt: 'Approve deployment?',
        options: [],
      },
    }))

    render(<ExecutionControls />)

    expect(screen.getByTestId('execution-pending-human-gate-banner')).toHaveTextContent(
      'Pending human gate: Approve deployment?',
    )
  })
})
