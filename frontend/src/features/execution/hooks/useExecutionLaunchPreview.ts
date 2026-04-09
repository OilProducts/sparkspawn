import { useEffect, useState } from 'react'

import { buildHydratedFlowGraph, normalizeLegacyDot, type HydratedFlowGraph } from '@/features/workflow-canvas'
import { isAbortError } from '@/lib/api/shared'
import { useStore } from '@/store'
import type { ExecutionContinuationDraft } from '@/state/store-types'

import {
    loadExecutionFlowPayload,
    loadExecutionFlowPreview,
    loadExecutionRunGraphPreview,
} from '../services/executionPreviewTransport'

const unexpectedPreviewLoadMessage = 'Unable to load flow preview for launch inputs.'

export function useExecutionLaunchPreview(
    executionFlow: string | null,
    executionContinuation: ExecutionContinuationDraft | null,
    expandChildFlows: boolean,
) {
    const uiDefaults = useStore((state) => state.uiDefaults)
    const replaceExecutionGraphAttrs = useStore((state) => state.replaceExecutionGraphAttrs)
    const setExecutionDiagnostics = useStore((state) => state.setExecutionDiagnostics)
    const clearExecutionDiagnostics = useStore((state) => state.clearExecutionDiagnostics)
    const [isLoadingPreview, setIsLoadingPreview] = useState(false)
    const [previewLoadError, setPreviewLoadError] = useState<string | null>(null)
    const [hydratedGraph, setHydratedGraph] = useState<HydratedFlowGraph | null>(null)

    useEffect(() => {
        const useRunSnapshot =
            executionContinuation?.flowSourceMode === 'snapshot'
            && Boolean(executionContinuation.sourceRunId)
        const canLoadFlowPreview = Boolean(executionFlow)
        if (!useRunSnapshot && !canLoadFlowPreview) {
            replaceExecutionGraphAttrs({})
            clearExecutionDiagnostics()
            setPreviewLoadError(null)
            setHydratedGraph(null)
            setIsLoadingPreview(false)
            return
        }

        const loadAbort = new AbortController()
        let cancelled = false

        const loadPreview = async () => {
            setIsLoadingPreview(true)
            setPreviewLoadError(null)
            try {
                let preview
                let hydrated: HydratedFlowGraph | null = null

                if (useRunSnapshot && executionContinuation) {
                    preview = await loadExecutionRunGraphPreview(
                        executionContinuation.sourceRunId,
                        { signal: loadAbort.signal },
                        { expandChildren: expandChildFlows },
                    )
                    if (cancelled) {
                        return
                    }
                    hydrated = buildHydratedFlowGraph(
                        executionContinuation.sourceFlowName || executionContinuation.sourceRunId,
                        preview,
                        uiDefaults,
                        undefined,
                        { expandChildren: expandChildFlows },
                    )
                } else if (executionFlow) {
                    const payload = await loadExecutionFlowPayload(executionFlow, { signal: loadAbort.signal })
                    if (cancelled) {
                        return
                    }

                    const normalizedContent = normalizeLegacyDot(payload.content)
                    preview = await loadExecutionFlowPreview(
                        normalizedContent,
                        { signal: loadAbort.signal },
                        {
                            flowName: executionFlow,
                            expandChildren: expandChildFlows,
                        },
                    )
                    if (cancelled) {
                        return
                    }

                    hydrated = buildHydratedFlowGraph(
                        executionFlow,
                        preview,
                        uiDefaults,
                        normalizedContent,
                        { expandChildren: expandChildFlows },
                    )
                } else {
                    preview = null
                }

                if (cancelled) {
                    return
                }

                if (preview?.diagnostics) {
                    setExecutionDiagnostics(preview.diagnostics)
                } else {
                    clearExecutionDiagnostics()
                }
                setHydratedGraph(hydrated)
                replaceExecutionGraphAttrs(hydrated?.graphAttrs ?? {})
            } catch (error) {
                if (loadAbort.signal.aborted || isAbortError(error)) {
                    return
                }
                console.error(error)
                setHydratedGraph(null)
                replaceExecutionGraphAttrs({})
                clearExecutionDiagnostics()
                setPreviewLoadError(unexpectedPreviewLoadMessage)
            } finally {
                if (!cancelled) {
                    setIsLoadingPreview(false)
                }
            }
        }

        void loadPreview()

        return () => {
            cancelled = true
            loadAbort.abort()
        }
    }, [
        clearExecutionDiagnostics,
        expandChildFlows,
        executionContinuation,
        executionFlow,
        replaceExecutionGraphAttrs,
        setExecutionDiagnostics,
        uiDefaults,
    ])

    return {
        isLoadingPreview,
        previewLoadError,
        hydratedGraph,
    }
}
