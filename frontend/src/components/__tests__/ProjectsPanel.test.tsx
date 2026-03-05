import { ProjectsPanel } from '@/components/ProjectsPanel'
import { useStore } from '@/store'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const DEFAULT_WORKING_DIRECTORY = './test-app'

const resetProjectScopeState = () => {
  useStore.setState((state) => ({
    ...state,
    viewMode: 'projects',
    activeProjectPath: null,
    activeFlow: null,
    selectedRunId: null,
    workingDir: DEFAULT_WORKING_DIRECTORY,
    projectRegistry: {},
    projectScopedWorkspaces: {},
    projectRegistrationError: null,
    recentProjectPaths: [],
  }))
}

describe('ProjectsPanel', () => {
  beforeEach(() => {
    resetProjectScopeState()
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(JSON.stringify({ branch: 'main' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('renders the project registration form and controls', () => {
    render(<ProjectsPanel />)

    expect(screen.getByTestId('quick-switch-new-button')).toBeVisible()
    expect(screen.getByTestId('project-directory-picker-input')).toBeInTheDocument()
    expect(screen.getByTestId('project-register-form')).toBeVisible()
    expect(screen.getByTestId('project-event-log-surface')).toBeVisible()
    expect(screen.getByLabelText('Project directory path')).toBeVisible()
    expect(screen.getByTestId('project-path-input')).toBeVisible()
    expect(screen.getByTestId('project-register-button')).toHaveAttribute('type', 'submit')
  })

  it('blocks relative paths and accepts absolute paths', async () => {
    const user = userEvent.setup()
    render(<ProjectsPanel />)

    const input = screen.getByTestId('project-path-input')
    const registerButton = screen.getByTestId('project-register-button')

    await user.type(input, 'relative/path')
    await user.click(registerButton)

    expect(screen.getByTestId('project-registration-error')).toHaveTextContent(
      'Project directory path must be absolute.',
    )

    await user.clear(input)
    await user.type(input, '/tmp/demo-project')
    await user.click(registerButton)

    await waitFor(() => {
      expect(screen.queryByTestId('project-registration-error')).not.toBeInTheDocument()
    })

    expect(screen.getByTestId('project-registry-list')).toHaveTextContent('/tmp/demo-project')
    expect(screen.getByTestId('project-path-input')).toHaveValue('')
    expect(useStore.getState().projectRegistry['/tmp/demo-project']).toBeDefined()
    expect(useStore.getState().activeProjectPath).toBe('/tmp/demo-project')
  })

  it('registers a selected directory from Quick Switch new-button picker', async () => {
    const user = userEvent.setup()
    render(<ProjectsPanel />)

    const pickerInput = screen.getByTestId('project-directory-picker-input') as HTMLInputElement
    const pickerClickSpy = vi.spyOn(pickerInput, 'click')
    await user.click(screen.getByTestId('quick-switch-new-button'))
    expect(pickerClickSpy).toHaveBeenCalled()

    const selectedFile = new File(['console.log("hello")'], 'main.ts', { type: 'text/plain' })
    Object.defineProperty(selectedFile, 'path', {
      configurable: true,
      value: '/tmp/quick-switch-project/src/main.ts',
    })
    Object.defineProperty(selectedFile, 'webkitRelativePath', {
      configurable: true,
      value: 'quick-switch-project/src/main.ts',
    })

    fireEvent.change(pickerInput, {
      target: {
        files: [selectedFile],
      },
    })

    await waitFor(() => {
      expect(useStore.getState().projectRegistry['/tmp/quick-switch-project']).toBeDefined()
    })
    expect(screen.getByTestId('recent-projects-list')).toHaveTextContent('/tmp/quick-switch-project')
    expect(useStore.getState().activeProjectPath).toBe('/tmp/quick-switch-project')
  })
})
