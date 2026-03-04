import { ProjectsPanel } from '@/components/ProjectsPanel'
import { useStore } from '@/store'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const DEFAULT_WORKING_DIRECTORY = './test-app'

const resetProjectWorkflowState = () => {
  useStore.setState((state) => ({
    ...state,
    viewMode: 'projects',
    activeProjectPath: null,
    activeFlow: null,
    selectedRunId: null,
    workingDir: DEFAULT_WORKING_DIRECTORY,
    model: 'gpt-5.3',
    projectRegistry: {},
    projectScopedWorkspaces: {},
    projectRegistrationError: null,
    recentProjectPaths: [],
    diagnostics: [],
    nodeDiagnostics: {},
    edgeDiagnostics: {},
    hasValidationErrors: false,
    logs: [],
  }))
}

const resolveRequestUrl = (input: RequestInfo | URL): string => {
  if (typeof input === 'string') return input
  if (input instanceof URL) return input.toString()
  return input.url
}

describe('Project-scoped workflow behavior', () => {
  let planStatusContractUnavailable = false

  beforeEach(() => {
    planStatusContractUnavailable = false
    resetProjectWorkflowState()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = resolveRequestUrl(input)
        if (url.includes('/api/projects/metadata')) {
          return new Response(JSON.stringify({ branch: 'main', commit: 'abc123def456' }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          })
        }
        if (url.includes('/api/flows/')) {
          return new Response(JSON.stringify({ content: 'digraph Plan { start -> end }' }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          })
        }
        if (url.endsWith('/pipelines') && init?.method === 'POST') {
          return new Response(JSON.stringify({ status: 'started', pipeline_id: 'run-plan-101' }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          })
        }
        if (url.endsWith('/pipelines/run-plan-101')) {
          if (planStatusContractUnavailable) {
            return new Response(JSON.stringify({ detail: 'plan status endpoint unavailable' }), {
              status: 503,
              headers: { 'Content-Type': 'application/json' },
            })
          }
          return new Response(
            JSON.stringify({
              pipeline_id: 'run-plan-101',
              status: 'running',
              flow_name: 'plan-generation.dot',
              working_directory: '/tmp/plan-project',
              model: 'gpt-5.3',
            }),
            {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            },
          )
        }
        return new Response(JSON.stringify({}), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }),
    )
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('creates project-scoped conversation history and requires explicit confirmation before applying proposal edits', async () => {
    const user = userEvent.setup()
    act(() => {
      useStore.getState().registerProject('/tmp/workflow-project')
      useStore.getState().setActiveProjectPath('/tmp/workflow-project')
    })

    render(<ProjectsPanel />)
    expect(screen.getByTestId('project-scope-entrypoints')).toBeVisible()
    expect(screen.getByTestId('project-ai-conversation-surface')).toBeVisible()
    expect(screen.getByTestId('project-spec-edit-proposal-surface')).toBeVisible()

    await user.click(screen.getByTestId('project-ai-conversation-start-button'))
    expect(screen.getByTestId('project-ai-conversation-history-list')).toHaveTextContent('Started conversation')

    await user.click(screen.getByTestId('project-spec-edit-proposal-preview-button'))
    expect(screen.getByTestId('project-spec-edit-proposal-preview')).toBeVisible()

    const confirmSpy = vi.spyOn(window, 'confirm')
    confirmSpy.mockReturnValueOnce(false)
    await user.click(screen.getByTestId('project-spec-edit-proposal-apply-button'))
    expect(screen.getByTestId('project-spec-edit-proposal-preview')).toBeVisible()
    expect(useStore.getState().projectScopedWorkspaces['/tmp/workflow-project']?.specId).toBeNull()

    confirmSpy.mockReturnValueOnce(true)
    await user.click(screen.getByTestId('project-spec-edit-proposal-apply-button'))
    await waitFor(() => {
      expect(screen.queryByTestId('project-spec-edit-proposal-preview')).not.toBeInTheDocument()
    })

    const projectScope = useStore.getState().projectScopedWorkspaces['/tmp/workflow-project']
    expect(projectScope.specId).toMatch(/^spec-/)
    expect(projectScope.specStatus).toBe('draft')
    expect(projectScope.specProvenance).toEqual(
      expect.objectContaining({
        source: 'spec-edit-proposal',
        referenceId: expect.stringMatching(/^proposal-/),
        runId: null,
        gitBranch: 'main',
        gitCommit: 'abc123def456',
      }),
    )
    expect(projectScope.specProvenance?.capturedAt).toEqual(expect.any(String))
  })

  it('enforces spec approval before launching plan workflow and records run context on launch', async () => {
    const user = userEvent.setup()
    act(() => {
      useStore.getState().registerProject('/tmp/plan-project')
      useStore.getState().setActiveProjectPath('/tmp/plan-project')
      useStore.getState().setActiveFlow('plan-generation.dot')
    })

    render(<ProjectsPanel />)
    expect(screen.getByTestId('project-plan-generation-surface')).toBeVisible()
    expect(screen.getByTestId('project-plan-gate-surface')).toBeVisible()

    await user.click(screen.getByRole('button', { name: 'Create spec' }))
    const launchButton = screen.getByTestId('project-plan-generation-launch-button')
    expect(launchButton).toBeDisabled()

    await user.click(screen.getByTestId('project-spec-approve-for-plan-button'))
    expect(launchButton).toBeEnabled()

    await user.click(launchButton)
    await waitFor(() => {
      expect(useStore.getState().selectedRunId).toBe('run-plan-101')
    })

    const state = useStore.getState()
    const scope = state.projectScopedWorkspaces['/tmp/plan-project']
    expect(scope.planId).toMatch(/^plan-/)
    expect(scope.planStatus).toBe('draft')
    expect(scope.planProvenance).toEqual(
      expect.objectContaining({
        source: 'plan-generation-workflow',
        referenceId: 'run-plan-101',
        capturedAt: expect.any(String),
        runId: 'run-plan-101',
        gitBranch: 'main',
        gitCommit: 'abc123def456',
      }),
    )
    expect(state.viewMode).toBe('execution')
  })

  it('[CID:12.4.03] keeps plan-generation launch active when status retrieval is degraded', async () => {
    planStatusContractUnavailable = true
    const user = userEvent.setup()
    act(() => {
      useStore.getState().registerProject('/tmp/plan-status-degraded-project')
      useStore.getState().setActiveProjectPath('/tmp/plan-status-degraded-project')
      useStore.getState().setActiveFlow('plan-generation.dot')
    })

    render(<ProjectsPanel />)

    await user.click(screen.getByRole('button', { name: 'Create spec' }))
    await user.click(screen.getByTestId('project-spec-approve-for-plan-button'))
    await user.click(screen.getByTestId('project-plan-generation-launch-button'))

    await waitFor(() => {
      expect(useStore.getState().selectedRunId).toBe('run-plan-101')
    })

    expect(screen.getByTestId('project-plan-generation-status-degraded')).toHaveTextContent(
      'plan status endpoint unavailable',
    )
    expect(useStore.getState().projectScopedWorkspaces['/tmp/plan-status-degraded-project']?.planStatus).toBe('draft')
    expect(useStore.getState().viewMode).toBe('execution')
  })
})
