import { Editor } from '@/features/editor/Editor'
import { useStore } from '@/store'
import { ReactFlowProvider } from '@xyflow/react'
import { act, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { EditorPreviewResponse } from '@/features/editor/services/editorPreview'
import {
  loadEditorFlowPayload,
  loadEditorPreview,
} from '@/features/editor/services/editorPreview'

vi.mock('@/features/editor/services/editorPreview', () => ({
  loadEditorFlowPayload: vi.fn(),
  loadEditorPreview: vi.fn(),
}))

vi.mock('@/features/editor/components/ValidationPanel', () => ({
  ValidationPanel: () => null,
}))

type Deferred<T> = {
  promise: Promise<T>
  resolve: (value: T) => void
  reject: (reason?: unknown) => void
}

const createDeferred = <T,>(): Deferred<T> => {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

const buildPreview = (nodeCount: number): EditorPreviewResponse => ({
  status: 'ok',
  graph: {
    nodes: Array.from({ length: nodeCount }, (_, index) => ({
      id: `node_${index + 1}`,
      label: `Node ${index + 1}`,
      shape: 'box',
      prompt: `Prompt ${index + 1}`,
    })),
    edges: [],
    graph_attrs: {},
  },
  diagnostics: [],
  errors: [],
})

const resetEditorState = (activeFlow: string | null) => {
  useStore.setState((state) => ({
    ...state,
    viewMode: 'editor',
    activeFlow,
    executionFlow: null,
    suppressPreview: true,
    graphAttrs: {},
    diagnostics: [],
    nodeDiagnostics: {},
    edgeDiagnostics: {},
    hasValidationErrors: false,
    selectedNodeId: null,
    selectedEdgeId: null,
    uiDefaults: {
      llm_provider: 'openai',
      llm_model: 'gpt-5.4-mini',
      reasoning_effort: 'high',
    },
  }))
}

const renderEditor = () => render(
  <ReactFlowProvider>
    <Editor />
  </ReactFlowProvider>,
)

describe('Editor flow loading behavior', () => {
  beforeEach(() => {
    resetEditorState('flow-a.dot')
    vi.mocked(loadEditorFlowPayload).mockImplementation(async (flowName: string) => ({
      name: flowName,
      content: flowName,
    }))
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('clears the previous canvas when the next flow load fails', async () => {
    const previewDeferreds = new Map<string, Deferred<EditorPreviewResponse>>([
      ['flow-a.dot', createDeferred<EditorPreviewResponse>()],
      ['flow-b.dot', createDeferred<EditorPreviewResponse>()],
    ])
    vi.mocked(loadEditorPreview).mockImplementation((dot: string) => {
      const deferred = previewDeferreds.get(dot)
      if (!deferred) {
        throw new Error(`Unexpected preview request: ${dot}`)
      }
      return deferred.promise
    })

    renderEditor()
    const profile = await screen.findByTestId('canvas-performance-profile')

    act(() => {
      previewDeferreds.get('flow-a.dot')?.resolve(buildPreview(1))
    })
    await waitFor(() => expect(profile).toHaveAttribute('data-node-count', '1'))

    act(() => {
      useStore.setState((state) => ({ ...state, activeFlow: 'flow-b.dot' }))
    })
    await waitFor(() => expect(profile).toHaveAttribute('data-node-count', '0'))

    act(() => {
      previewDeferreds.get('flow-b.dot')?.reject(new Error('preview failed'))
    })
    await waitFor(() => expect(profile).toHaveAttribute('data-node-count', '0'))
  })

  it('ignores a superseded flow load that resolves after a newer selection', async () => {
    const previewDeferreds = new Map<string, Deferred<EditorPreviewResponse>>([
      ['flow-a.dot', createDeferred<EditorPreviewResponse>()],
      ['flow-b.dot', createDeferred<EditorPreviewResponse>()],
      ['flow-c.dot', createDeferred<EditorPreviewResponse>()],
    ])
    vi.mocked(loadEditorPreview).mockImplementation((dot: string) => {
      const deferred = previewDeferreds.get(dot)
      if (!deferred) {
        throw new Error(`Unexpected preview request: ${dot}`)
      }
      return deferred.promise
    })

    renderEditor()
    const profile = await screen.findByTestId('canvas-performance-profile')

    act(() => {
      previewDeferreds.get('flow-a.dot')?.resolve(buildPreview(1))
    })
    await waitFor(() => expect(profile).toHaveAttribute('data-node-count', '1'))

    act(() => {
      useStore.setState((state) => ({ ...state, activeFlow: 'flow-b.dot' }))
    })
    await waitFor(() => expect(profile).toHaveAttribute('data-node-count', '0'))

    act(() => {
      useStore.setState((state) => ({ ...state, activeFlow: 'flow-c.dot' }))
    })

    act(() => {
      previewDeferreds.get('flow-c.dot')?.resolve(buildPreview(3))
    })
    await waitFor(() => expect(profile).toHaveAttribute('data-node-count', '3'))

    act(() => {
      previewDeferreds.get('flow-b.dot')?.resolve(buildPreview(2))
    })
    await waitFor(() => expect(profile).toHaveAttribute('data-node-count', '3'))
  })
})
