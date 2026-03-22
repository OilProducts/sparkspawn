import { type StateCreator } from 'zustand'
import {
    buildDiagnosticMaps,
    DEFAULT_WORKING_DIRECTORY,
    deriveGraphAttrErrors,
    loadUiDefaults,
    normalizeGraphAttrs,
    normalizeGraphAttrValue,
    resolveProjectSessionState,
    saveUiDefaults,
    validateGraphAttrValue,
} from './store-helpers'
import type { AppState, EditorSlice } from './store-types'
import { initialWorkspaceEditorState } from './workspaceSlice'

const graphAttrsEqual = (left: Record<string, unknown>, right: Record<string, unknown>) => {
    const leftKeys = Object.keys(left)
    const rightKeys = Object.keys(right)
    if (leftKeys.length !== rightKeys.length) {
        return false
    }
    return leftKeys.every((key) => left[key] === right[key])
}

const deriveNextGraphAttrState = (
    state: Pick<EditorSlice, 'graphAttrs' | 'graphAttrErrors' | 'graphAttrsUserEditVersion'>,
    attrs: EditorSlice['graphAttrs'],
    markDirty: boolean,
) => {
    const normalizedAttrs = normalizeGraphAttrs(attrs)
    const nextGraphAttrErrors = deriveGraphAttrErrors(normalizedAttrs)
    const attrsUnchanged = graphAttrsEqual(state.graphAttrs as Record<string, unknown>, normalizedAttrs as Record<string, unknown>)
    const errorsUnchanged = graphAttrsEqual(
        state.graphAttrErrors as Record<string, unknown>,
        nextGraphAttrErrors as Record<string, unknown>,
    )
    if (attrsUnchanged && errorsUnchanged) {
        return state
    }
    return {
        graphAttrs: normalizedAttrs,
        graphAttrErrors: nextGraphAttrErrors,
        graphAttrsUserEditVersion: markDirty
            ? state.graphAttrsUserEditVersion + 1
            : state.graphAttrsUserEditVersion,
    }
}

export const createEditorSlice: StateCreator<AppState, [], [], EditorSlice> = (set) => ({
    selectedNodeId: null,
    setSelectedNodeId: (id) => set({ selectedNodeId: id }),
    selectedEdgeId: null,
    setSelectedEdgeId: (id) => set({ selectedEdgeId: id }),
    workingDir: initialWorkspaceEditorState.workingDir || DEFAULT_WORKING_DIRECTORY,
    setWorkingDir: (value) =>
        set((state) => {
            const nextProjectSessionStates = { ...state.projectSessionsByPath }
            if (state.activeProjectPath) {
                const scoped = resolveProjectSessionState(
                    nextProjectSessionStates[state.activeProjectPath],
                    state.activeProjectPath,
                )
                nextProjectSessionStates[state.activeProjectPath] = {
                    ...scoped,
                    workingDir: value,
                }
            }
            return {
                workingDir: value,
                projectSessionsByPath: nextProjectSessionStates,
            }
        }),
    model: '',
    setModel: (value) => set({ model: value }),
    graphAttrs: {},
    graphAttrErrors: {},
    graphAttrsUserEditVersion: 0,
    setGraphAttrs: (attrs) =>
        set((state) => deriveNextGraphAttrState(state, attrs, true)),
    replaceGraphAttrs: (attrs) =>
        set((state) => deriveNextGraphAttrState(state, attrs, false)),
    updateGraphAttr: (key, value) =>
        set((state) => {
            const normalizedValue = normalizeGraphAttrValue(key, value)
            const currentValue = state.graphAttrs[key]
            const currentNormalizedValue = currentValue === undefined || currentValue === null
                ? ''
                : normalizeGraphAttrValue(key, String(currentValue))
            const currentError = state.graphAttrErrors[key] ?? null
            const nextError = validateGraphAttrValue(key, normalizedValue)
            if (currentNormalizedValue === normalizedValue && currentError === nextError) {
                return state
            }
            return deriveNextGraphAttrState(
                state,
                {
                    ...state.graphAttrs,
                    [key]: normalizedValue,
                },
                true,
            )
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
    saveStateVersion: 0,
    saveErrorMessage: null,
    saveErrorKind: null,
    markSaveInFlight: () =>
        set((state) => ({
            saveState: 'saving',
            saveStateVersion: state.saveStateVersion + 1,
            saveErrorMessage: null,
            saveErrorKind: null,
        })),
    markSaveSuccess: () =>
        set((state) => ({
            saveState: 'saved',
            saveStateVersion: state.saveStateVersion + 1,
            saveErrorMessage: null,
            saveErrorKind: null,
        })),
    markSaveConflict: (message) =>
        set((state) => ({
            saveState: 'conflict',
            saveStateVersion: state.saveStateVersion + 1,
            saveErrorMessage: message || 'Flow save conflict detected.',
            saveErrorKind: 'conflict',
        })),
    markSaveFailure: (message, kind = 'unknown') =>
        set((state) => ({
            saveState: 'error',
            saveStateVersion: state.saveStateVersion + 1,
            saveErrorMessage: message || 'Flow save failed.',
            saveErrorKind: kind,
        })),
    resetSaveState: () =>
        set({
            saveState: 'idle',
            saveErrorMessage: null,
            saveErrorKind: null,
        }),
})
