import {
  primeFlowSaveBaseline,
  resetFlowSaveBaselines,
  retryLastSaveContent,
  saveFlowContent,
  saveFlowContentExpectingSemanticEquivalence,
} from '@/lib/flowPersistence'
import { resolveSaveRemediation } from '@/lib/saveRemediation'
import { useStore } from '@/store'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const resetSaveState = () => {
  useStore.setState((state) => ({
    ...state,
    saveState: 'idle',
    saveStateVersion: 0,
    saveErrorMessage: null,
    saveErrorKind: null,
  }))
}

describe('Editor save state behavior', () => {
  beforeEach(() => {
    resetSaveState()
    resetFlowSaveBaselines()
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('classifies parse and validation errors with actionable remediation', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              detail: { status: 'parse_error', error: 'line 3: expected node identifier' },
            }),
            { status: 400, headers: { 'Content-Type': 'application/json' } },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({
              detail: { status: 'validation_error', error: 'Unknown retry target node.' },
            }),
            { status: 422, headers: { 'Content-Type': 'application/json' } },
          ),
        ),
    )

    const parseSave = await saveFlowContent('demo.dot', 'digraph Demo {')
    expect(parseSave).toBe(false)
    let saveState = useStore.getState()
    expect(saveState.saveState).toBe('error')
    expect(saveState.saveErrorKind).toBe('parse_error')
    expect(saveState.saveErrorMessage).toContain('Save blocked by DOT parse error')
    expect(resolveSaveRemediation(saveState.saveState, saveState.saveErrorKind)).toEqual({
      message: 'Fix DOT syntax issues in Raw DOT mode, then save again.',
      allowRetry: false,
    })

    const validationSave = await saveFlowContent('demo.dot', 'digraph Demo { start -> end }')
    expect(validationSave).toBe(false)
    saveState = useStore.getState()
    expect(saveState.saveState).toBe('error')
    expect(saveState.saveErrorKind).toBe('validation_error')
    expect(saveState.saveErrorMessage).toContain('Save blocked by validation errors')
    expect(resolveSaveRemediation(saveState.saveState, saveState.saveErrorKind)).toEqual({
      message: 'Resolve highlighted validation errors, then save again.',
      allowRetry: false,
    })
  })

  it('supports retrying a transient network failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockRejectedValueOnce(new Error('offline'))
        .mockResolvedValueOnce(
          new Response(JSON.stringify({ status: 'saved' }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        ),
    )

    const firstAttempt = await saveFlowContent('demo.dot', 'digraph Demo { start -> end }')
    expect(firstAttempt).toBe(false)
    let saveState = useStore.getState()
    expect(saveState.saveState).toBe('error')
    expect(saveState.saveErrorKind).toBe('network')
    expect(resolveSaveRemediation(saveState.saveState, saveState.saveErrorKind)).toEqual({
      message: 'Retry save now, and verify backend connectivity if this repeats.',
      allowRetry: true,
    })

    const retryAttempt = await retryLastSaveContent()
    expect(retryAttempt).toBe(true)
    saveState = useStore.getState()
    expect(saveState.saveState).toBe('saved')
    expect(saveState.saveErrorMessage).toBeNull()
    expect(saveState.saveErrorKind).toBeNull()
  })

  it('sets semantic-equivalence expectation when requested', async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ status: 'saved' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const saved = await saveFlowContentExpectingSemanticEquivalence('demo.dot', 'digraph Demo { start -> end }')
    expect(saved).toBe(true)

    const [, requestInit] = fetchMock.mock.calls[0]
    const body = JSON.parse(String((requestInit as RequestInit).body))
    expect(body).toMatchObject({
      name: 'demo.dot',
      expect_semantic_equivalence: true,
    })
  })

  it('skips no-op saves that match the loaded baseline', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    primeFlowSaveBaseline('demo.dot', 'digraph Demo { start -> end }')

    const saved = await saveFlowContent('demo.dot', 'digraph Demo { start -> end }')
    expect(saved).toBe(true)
    expect(fetchMock).not.toHaveBeenCalled()

    const saveState = useStore.getState()
    expect(saveState.saveState).toBe('idle')
    expect(saveState.saveErrorMessage).toBeNull()
    expect(saveState.saveErrorKind).toBeNull()
  })
})
