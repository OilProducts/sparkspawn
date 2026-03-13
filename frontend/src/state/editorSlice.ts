import { type StateCreator } from 'zustand'
import {
    buildDiagnosticMaps,
    DEFAULT_WORKING_DIRECTORY,
    deriveGraphAttrErrors,
    loadUiDefaults,
    normalizeGraphAttrs,
    normalizeGraphAttrValue,
    resolveProjectScopedWorkspace,
    saveUiDefaults,
    validateGraphAttrValue,
} from './store-helpers'
import type { AppState, EditorSlice } from './store-types'
import { initialWorkspaceEditorState } from './workspaceSlice'

export const createEditorSlice: StateCreator<AppState, [], [], EditorSlice> = (set) => ({
    selectedNodeId: null,
    setSelectedNodeId: (id) => set({ selectedNodeId: id }),
    selectedEdgeId: null,
    setSelectedEdgeId: (id) => set({ selectedEdgeId: id }),
    workingDir: initialWorkspaceEditorState.workingDir || DEFAULT_WORKING_DIRECTORY,
    setWorkingDir: (value) =>
        set((state) => {
            const nextProjectScopedWorkspaces = { ...state.projectScopedWorkspaces }
            if (state.activeProjectPath) {
                const scoped = resolveProjectScopedWorkspace(
                    nextProjectScopedWorkspaces[state.activeProjectPath],
                    state.activeProjectPath,
                )
                nextProjectScopedWorkspaces[state.activeProjectPath] = {
                    ...scoped,
                    workingDir: value,
                }
            }
            return {
                workingDir: value,
                projectScopedWorkspaces: nextProjectScopedWorkspaces,
            }
        }),
    model: '',
    setModel: (value) => set({ model: value }),
    graphAttrs: {},
    graphAttrErrors: {},
    setGraphAttrs: (attrs) => {
        const normalizedAttrs = normalizeGraphAttrs(attrs)
        set({
            graphAttrs: normalizedAttrs,
            graphAttrErrors: deriveGraphAttrErrors(normalizedAttrs),
        })
    },
    updateGraphAttr: (key, value) =>
        set((state) => {
            const normalizedValue = normalizeGraphAttrValue(key, value)
            const error = validateGraphAttrValue(key, normalizedValue)
            const graphAttrErrors = {
                ...state.graphAttrErrors,
            }
            if (error) {
                graphAttrErrors[key] = error
            } else {
                delete graphAttrErrors[key]
            }
            return {
                graphAttrs: {
                    ...state.graphAttrs,
                    [key]: normalizedValue,
                },
                graphAttrErrors,
            }
        }),
    diagnostics: [],
    setDiagnostics: (diagnostics) =>
        set(() => {
            const { nodeDiagnostics, edgeDiagnostics } = buildDiagnosticMaps(diagnostics)
            return {
                diagnostics,
                nodeDiagnostics,
                edgeDiagnostics,
                hasValidationErrors: diagnostics.some((diag) => diag.severity === 'error'),
            }
        }),
    clearDiagnostics: () =>
        set(() => ({
            diagnostics: [],
            nodeDiagnostics: {},
            edgeDiagnostics: {},
            hasValidationErrors: false,
        })),
    nodeDiagnostics: {},
    edgeDiagnostics: {},
    hasValidationErrors: false,
    suppressPreview: false,
    setSuppressPreview: (value) => set({ suppressPreview: value }),
    uiDefaults: loadUiDefaults(),
    setUiDefaults: (values) =>
        set((state) => {
            const next = { ...state.uiDefaults, ...values }
            saveUiDefaults(next)
            return { uiDefaults: next }
        }),
    setUiDefault: (key, value) =>
        set((state) => {
            const next = { ...state.uiDefaults, [key]: value }
            saveUiDefaults(next)
            return { uiDefaults: next }
        }),
    saveState: 'idle',
    saveErrorMessage: null,
    saveErrorKind: null,
    markSaveInFlight: () => set({ saveState: 'saving', saveErrorMessage: null, saveErrorKind: null }),
    markSaveSuccess: () => set({ saveState: 'saved', saveErrorMessage: null, saveErrorKind: null }),
    markSaveConflict: (message) =>
        set({
            saveState: 'conflict',
            saveErrorMessage: message || 'Flow save conflict detected.',
            saveErrorKind: 'conflict',
        }),
    markSaveFailure: (message, kind = 'unknown') =>
        set({
            saveState: 'error',
            saveErrorMessage: message || 'Flow save failed.',
            saveErrorKind: kind,
        }),
})
