import { useStore } from '@/store'
import { beforeEach, describe, expect, it } from 'vitest'

const DEFAULT_WORKING_DIRECTORY = './test-app'

const resetStore = () => {
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

describe('project scope store behavior', () => {
  beforeEach(() => {
    resetStore()
  })

  it('forces projects mode when selecting editor without an active project', () => {
    const store = useStore.getState()
    store.setViewMode('editor')

    expect(useStore.getState().viewMode).toBe('projects')
  })

  it('rejects non-absolute project paths', () => {
    const result = useStore.getState().registerProject('relative/path')

    expect(result.ok).toBe(false)
    expect(result.error).toBe('Project directory path must be absolute.')
    expect(useStore.getState().projectRegistrationError).toBe('Project directory path must be absolute.')
  })

  it('normalizes and registers an absolute project path', () => {
    const result = useStore.getState().registerProject(' /tmp/demo//project/./subdir/.. ')

    expect(result.ok).toBe(true)
    expect(result.normalizedPath).toBe('/tmp/demo/project')
    expect(useStore.getState().projectRegistry['/tmp/demo/project']).toBeDefined()
    expect(useStore.getState().activeProjectPath).toBe('/tmp/demo/project')
  })

  it('prevents duplicate project registrations', () => {
    useStore.getState().registerProject('/tmp/demo/project')

    const duplicateResult = useStore.getState().registerProject('/tmp/demo/project')

    expect(duplicateResult.ok).toBe(false)
    expect(duplicateResult.error).toBe('Project already registered: /tmp/demo/project')
  })

  it('resets execution context when switching active projects', () => {
    const store = useStore.getState()
    store.registerProject('/tmp/project-a')
    store.registerProject('/tmp/project-b')

    store.setRuntimeStatus('running')
    store.addLog({ time: '12:00', msg: 'running', type: 'info' })
    store.setSelectedNodeId('node-a')
    store.setDiagnostics([
      {
        rule_id: 'test',
        severity: 'warning',
        message: 'diag',
      },
    ])
    store.setGraphAttrs({ goal: 'A' })
    store.markSaveSuccess()
    store.setActiveProjectPath('/tmp/project-b')

    const next = useStore.getState()
    expect(next.runtimeStatus).toBe('idle')
    expect(next.logs).toEqual([])
    expect(next.selectedNodeId).toBeNull()
    expect(next.diagnostics).toEqual([])
    expect(next.graphAttrs).toEqual({})
    expect(next.saveState).toBe('idle')
  })
})
