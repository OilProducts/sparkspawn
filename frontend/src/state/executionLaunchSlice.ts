import { type StateCreator } from 'zustand'

import { buildDiagnosticMaps, normalizeGraphAttrs } from './store-helpers'
import type { AppState, ExecutionLaunchSlice } from './store-types'

export const createExecutionLaunchSlice: StateCreator<AppState, [], [], ExecutionLaunchSlice> = (set) => ({
    executionFlow: null,
    setExecutionFlow: (flow) =>
        set({
            executionFlow: flow,
            executionGraphAttrs: {},
            executionDiagnostics: [],
            executionNodeDiagnostics: {},
            executionEdgeDiagnostics: {},
            executionHasValidationErrors: false,
        }),
    executionContinuation: null,
    setExecutionContinuation: (draft) => set({ executionContinuation: draft }),
    clearExecutionContinuation: () => set({ executionContinuation: null }),
    setExecutionContinuationFlowSourceMode: (mode) =>
        set((state) => ({
            executionContinuation: state.executionContinuation
                ? {
                    ...state.executionContinuation,
                    flowSourceMode: mode,
                    startNodeId: mode === state.executionContinuation.flowSourceMode
                        ? state.executionContinuation.startNodeId
                        : null,
                }
                : null,
        })),
    setExecutionContinuationStartNode: (nodeId) =>
        set((state) => ({
            executionContinuation: state.executionContinuation
                ? {
                    ...state.executionContinuation,
                    startNodeId: nodeId,
                }
                : null,
        })),
    executionGraphAttrs: {},
    replaceExecutionGraphAttrs: (attrs) =>
        set({
            executionGraphAttrs: normalizeGraphAttrs(attrs),
        }),
    executionDiagnostics: [],
    setExecutionDiagnostics: (diagnostics) =>
        set(() => {
            const { nodeDiagnostics, edgeDiagnostics } = buildDiagnosticMaps(diagnostics)
            return {
                executionDiagnostics: diagnostics,
                executionNodeDiagnostics: nodeDiagnostics,
                executionEdgeDiagnostics: edgeDiagnostics,
                executionHasValidationErrors: diagnostics.some((diag) => diag.severity === 'error'),
            }
        }),
    clearExecutionDiagnostics: () =>
        set({
            executionDiagnostics: [],
            executionNodeDiagnostics: {},
            executionEdgeDiagnostics: {},
            executionHasValidationErrors: false,
        }),
    executionNodeDiagnostics: {},
    executionEdgeDiagnostics: {},
    executionHasValidationErrors: false,
})
