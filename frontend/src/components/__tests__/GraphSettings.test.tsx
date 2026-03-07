import { GraphSettings } from '@/components/GraphSettings'
import { SettingsPanel } from '@/components/SettingsPanel'
import { StylesheetEditor } from '@/components/StylesheetEditor'
import { useStore } from '@/store'
import { ReactFlowProvider } from '@xyflow/react'
import { act, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const DEFAULT_WORKING_DIRECTORY = './test-app'

const resetGraphSettingsState = () => {
  useStore.setState((state) => ({
    ...state,
    viewMode: 'editor',
    activeProjectPath: '/tmp/project-graph-settings',
    activeFlow: 'implement-spec.dot',
    selectedRunId: null,
    workingDir: DEFAULT_WORKING_DIRECTORY,
    projectRegistry: {
      '/tmp/project-graph-settings': {
        directoryPath: '/tmp/project-graph-settings',
        isFavorite: false,
        lastAccessedAt: null,
      },
    },
    projectScopedWorkspaces: {
      '/tmp/project-graph-settings': {
        activeFlow: 'implement-spec.dot',
        selectedRunId: null,
        workingDir: DEFAULT_WORKING_DIRECTORY,
        conversationId: null,
        specId: null,
        specStatus: 'draft',
        planId: null,
        planStatus: 'draft',
        artifactRunId: null,
      },
    },
    projectRegistrationError: null,
    recentProjectPaths: ['/tmp/project-graph-settings'],
    graphAttrs: {},
    graphAttrErrors: {},
    diagnostics: [],
    nodeDiagnostics: {},
    edgeDiagnostics: {},
    hasValidationErrors: false,
    uiDefaults: {
      llm_provider: 'openai',
      llm_model: 'gpt-5.3',
      reasoning_effort: 'high',
    },
  }))
}

const wrapWithFlowProvider = (node: ReactNode) => render(<ReactFlowProvider>{node}</ReactFlowProvider>)

describe('Graph and settings behavior', () => {
  beforeEach(() => {
    resetGraphSettingsState()
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(JSON.stringify({ status: 'saved' }), {
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

  it('persists global LLM defaults from settings panel inputs', async () => {
    const user = userEvent.setup()
    render(<SettingsPanel />)

    await user.clear(screen.getByPlaceholderText('openai'))
    await user.type(screen.getByPlaceholderText('openai'), 'anthropic')
    await user.clear(screen.getByPlaceholderText('gpt-5.2'))
    await user.type(screen.getByPlaceholderText('gpt-5.2'), 'claude-3.7-sonnet')
    const reasoningSelect = screen
      .getAllByRole('combobox')
      .find((element) => element.tagName === 'SELECT')
    expect(reasoningSelect).toBeDefined()
    await user.selectOptions(reasoningSelect as HTMLSelectElement, 'medium')

    expect(useStore.getState().uiDefaults).toEqual({
      llm_provider: 'anthropic',
      llm_model: 'claude-3.7-sonnet',
      reasoning_effort: 'medium',
    })
  })

  it('highlights stylesheet tokens and emits changes through textarea editing', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    const initialStylesheet = '#review {\n  llm_model: "gpt-5";\n}'

    const { container } = render(<StylesheetEditor value={initialStylesheet} onChange={onChange} />)

    const highlight = screen.getByTestId('model-stylesheet-editor-highlight')
    expect(highlight).toBeVisible()
    expect(container.querySelector('[data-token-type="selector"]')).toBeTruthy()
    expect(container.querySelector('[data-token-type="property"]')).toBeTruthy()

    const textarea = screen.getByRole('textbox')
    fireEvent.change(textarea, { target: { value: '* llm_provider_openai' } })

    expect(onChange).toHaveBeenCalledWith('* llm_provider_openai')
  })

  it('validates graph attrs and surfaces stylesheet diagnostics in advanced settings', async () => {
    const user = userEvent.setup()
    wrapWithFlowProvider(<GraphSettings inline />)

    expect(screen.getByTestId('graph-structured-form')).toBeVisible()
    expect(screen.getByTestId('graph-attrs-help')).toHaveTextContent('Graph attributes are baseline defaults')
    expect(screen.getByRole('button', { name: 'Apply To Nodes' })).toBeEnabled()

    const fidelityInput = screen.getByPlaceholderText('full')
    await user.clear(fidelityInput)
    await user.type(fidelityInput, 'invalid')

    expect(screen.getByText(/Default fidelity must be one of/i)).toBeVisible()
    expect(useStore.getState().graphAttrErrors.default_fidelity).toContain('Default fidelity must be one of')

    await user.click(screen.getByTestId('graph-advanced-toggle'))
    expect(screen.getByTestId('graph-model-stylesheet-selector-guidance')).toBeVisible()
    expect(screen.getByTestId('graph-model-stylesheet-selector-preview')).toBeVisible()
    expect(screen.getByTestId('graph-model-stylesheet-effective-preview')).toBeVisible()

    const stylesheetInput = within(screen.getByTestId('graph-model-stylesheet-editor')).getByRole('textbox')
    await user.type(stylesheetInput, '#n1-model-stylesheet')
    expect(useStore.getState().graphAttrs.model_stylesheet).toContain('#n1')

    act(() => {
      useStore.getState().setDiagnostics([
        {
          rule_id: 'stylesheet_syntax',
          severity: 'error',
          message: 'Invalid stylesheet selector syntax.',
          line: 1,
        },
      ])
    })

    expect(screen.getByTestId('graph-model-stylesheet-diagnostics')).toHaveTextContent(
      'Invalid stylesheet selector syntax.',
    )
  })
})
