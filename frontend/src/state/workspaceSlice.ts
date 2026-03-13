import { type StateCreator } from 'zustand'
import { isAbsoluteProjectPath, normalizeProjectPath } from '@/lib/projectPaths'
import {
    DEFAULT_WORKING_DIRECTORY,
    loadRouteState,
    pushRecentProjectPath,
    resolveProjectScopedWorkspace,
    resolveViewModeForProjectScope,
    saveRouteState,
    selectProjectScopedArtifactState,
} from './store-helpers'
import type {
    AppState,
    ProjectRegistrationResult,
    ProjectScopedWorkspace,
    RegisteredProject,
    WorkspaceSlice,
} from './store-types'

const restoredRouteState = loadRouteState()
const initialProjectRegistry: Record<string, RegisteredProject> = {}
const initialProjectScopedWorkspaces: Record<string, ProjectScopedWorkspace> = restoredRouteState.activeProjectPath
    ? {
        [restoredRouteState.activeProjectPath]: resolveProjectScopedWorkspace(
            {},
            restoredRouteState.activeProjectPath,
        ),
    }
    : {}
const restoredProjectScope = restoredRouteState.activeProjectPath
    ? resolveProjectScopedWorkspace(
        initialProjectScopedWorkspaces[restoredRouteState.activeProjectPath],
        restoredRouteState.activeProjectPath,
    )
    : null

export const initialWorkspaceEditorState = {
    activeFlow: restoredProjectScope ? restoredProjectScope.activeFlow : null,
    workingDir: restoredProjectScope ? restoredProjectScope.workingDir : DEFAULT_WORKING_DIRECTORY,
}

export const createWorkspaceSlice: StateCreator<AppState, [], [], WorkspaceSlice> = (set, get) => ({
    viewMode: restoredRouteState.viewMode,
    setViewMode: (mode) =>
        set((state) => {
            const nextViewMode = resolveViewModeForProjectScope(mode, state.activeProjectPath)
            saveRouteState({
                viewMode: nextViewMode,
                activeProjectPath: state.activeProjectPath,
            })
            return { viewMode: nextViewMode }
        }),
    activeProjectPath: restoredRouteState.activeProjectPath,
    projectRegistry: initialProjectRegistry,
    recentProjectPaths: restoredRouteState.activeProjectPath ? [restoredRouteState.activeProjectPath] : [],
    projectScopedWorkspaces: initialProjectScopedWorkspaces,
    hydrateProjectRegistry: (projects) =>
        set((state) => {
            const nextProjectRegistry: Record<string, RegisteredProject> = {}
            const nextProjectScopedWorkspaces = { ...state.projectScopedWorkspaces }
            projects.forEach((project) => {
                const normalizedPath = normalizeProjectPath(project.directoryPath)
                if (!normalizedPath || !isAbsoluteProjectPath(normalizedPath)) {
                    return
                }
                nextProjectRegistry[normalizedPath] = {
                    directoryPath: normalizedPath,
                    isFavorite: project.isFavorite === true,
                    lastAccessedAt: typeof project.lastAccessedAt === 'string' ? project.lastAccessedAt : null,
                    flowBindings: { ...(project.flowBindings ?? {}) },
                }
                nextProjectScopedWorkspaces[normalizedPath] = resolveProjectScopedWorkspace(
                    {
                        ...nextProjectScopedWorkspaces[normalizedPath],
                        conversationId: typeof project.activeConversationId === 'string'
                            ? project.activeConversationId
                            : nextProjectScopedWorkspaces[normalizedPath]?.conversationId ?? null,
                    },
                    normalizedPath,
                )
            })
            const nextActiveProjectPath = state.activeProjectPath && nextProjectRegistry[state.activeProjectPath]
                ? state.activeProjectPath
                : null
            const nextActiveProjectScope = nextActiveProjectPath
                ? resolveProjectScopedWorkspace(nextProjectScopedWorkspaces[nextActiveProjectPath], nextActiveProjectPath)
                : null
            saveRouteState({
                viewMode: resolveViewModeForProjectScope(state.viewMode, nextActiveProjectPath),
                activeProjectPath: nextActiveProjectPath,
            })
            return {
                projectRegistry: nextProjectRegistry,
                projectScopedWorkspaces: nextProjectScopedWorkspaces,
                activeProjectPath: nextActiveProjectPath,
                viewMode: resolveViewModeForProjectScope(state.viewMode, nextActiveProjectPath),
                activeFlow: nextActiveProjectPath ? nextActiveProjectScope?.activeFlow || null : null,
                executionFlow: null,
                selectedRunId: null,
                workingDir: nextActiveProjectPath ? nextActiveProjectScope?.workingDir || DEFAULT_WORKING_DIRECTORY : DEFAULT_WORKING_DIRECTORY,
                recentProjectPaths: nextActiveProjectPath ? pushRecentProjectPath(state.recentProjectPaths, nextActiveProjectPath) : state.recentProjectPaths,
            }
        }),
    upsertProjectRegistryEntry: (project) =>
        set((state) => {
            const normalizedPath = normalizeProjectPath(project.directoryPath)
            if (!normalizedPath || !isAbsoluteProjectPath(normalizedPath)) {
                return state
            }
            const nextProjectRegistry = {
                ...state.projectRegistry,
                [normalizedPath]: {
                    directoryPath: normalizedPath,
                    isFavorite: project.isFavorite === true,
                    lastAccessedAt: typeof project.lastAccessedAt === 'string' ? project.lastAccessedAt : null,
                    flowBindings: { ...(project.flowBindings ?? {}) },
                },
            }
            const nextProjectScopedWorkspaces = {
                ...state.projectScopedWorkspaces,
                [normalizedPath]: resolveProjectScopedWorkspace(
                    {
                        ...state.projectScopedWorkspaces[normalizedPath],
                        conversationId: typeof project.activeConversationId === 'string'
                            ? project.activeConversationId
                            : state.projectScopedWorkspaces[normalizedPath]?.conversationId ?? null,
                    },
                    normalizedPath,
                ),
            }
            return {
                projectRegistry: nextProjectRegistry,
                projectScopedWorkspaces: nextProjectScopedWorkspaces,
                recentProjectPaths: pushRecentProjectPath(state.recentProjectPaths, normalizedPath),
            }
        }),
    removeProject: (directoryPath, nextActiveProjectPath = null) =>
        set((state) => {
            const normalizedPath = normalizeProjectPath(directoryPath)
            if (!normalizedPath || !state.projectRegistry[normalizedPath]) {
                return state
            }

            const nextProjectRegistry = { ...state.projectRegistry }
            delete nextProjectRegistry[normalizedPath]

            const nextProjectScopedWorkspaces = { ...state.projectScopedWorkspaces }
            delete nextProjectScopedWorkspaces[normalizedPath]

            const normalizedFallbackPath = nextActiveProjectPath ? normalizeProjectPath(nextActiveProjectPath) : null
            const derivedFallbackPath = normalizedFallbackPath && nextProjectRegistry[normalizedFallbackPath]
                ? normalizedFallbackPath
                : state.recentProjectPaths.find((path) => path !== normalizedPath && Boolean(nextProjectRegistry[path]))
                    || Object.keys(nextProjectRegistry)[0]
                    || null
            const nextActiveProjectPathResolved = state.activeProjectPath === normalizedPath
                ? derivedFallbackPath
                : state.activeProjectPath
            const nextActiveProjectScope = nextActiveProjectPathResolved
                ? resolveProjectScopedWorkspace(nextProjectScopedWorkspaces[nextActiveProjectPathResolved], nextActiveProjectPathResolved)
                : null
            const nextViewMode = resolveViewModeForProjectScope(state.viewMode, nextActiveProjectPathResolved)

            saveRouteState({
                viewMode: nextViewMode,
                activeProjectPath: nextActiveProjectPathResolved,
            })

            return {
                projectRegistry: nextProjectRegistry,
                projectScopedWorkspaces: nextProjectScopedWorkspaces,
                recentProjectPaths: state.recentProjectPaths.filter((path) => path !== normalizedPath),
                activeProjectPath: nextActiveProjectPathResolved,
                viewMode: nextViewMode,
                activeFlow: nextActiveProjectPathResolved ? nextActiveProjectScope?.activeFlow || null : null,
                executionFlow: state.activeProjectPath === normalizedPath ? null : state.executionFlow,
                selectedRunId: state.activeProjectPath === normalizedPath ? null : state.selectedRunId,
                workingDir: nextActiveProjectPathResolved ? nextActiveProjectScope?.workingDir || DEFAULT_WORKING_DIRECTORY : DEFAULT_WORKING_DIRECTORY,
            }
        }),
    setActiveProjectPath: (projectPath) =>
        set((state) => {
            const normalizedProjectPath =
                typeof projectPath === 'string' ? normalizeProjectPath(projectPath) : null
            if (projectPath !== null && (!normalizedProjectPath || !isAbsoluteProjectPath(normalizedProjectPath))) {
                return state
            }
            const nextProjectPath = normalizedProjectPath
            const isProjectSwitch = nextProjectPath !== state.activeProjectPath
            const nextProjectScopedWorkspaces = { ...state.projectScopedWorkspaces }
            const nextProjectRegistry = { ...state.projectRegistry }
            const currentScope = state.activeProjectPath
            if (currentScope) {
                const existingScope = resolveProjectScopedWorkspace(nextProjectScopedWorkspaces[currentScope], currentScope)
                nextProjectScopedWorkspaces[currentScope] = {
                    ...existingScope,
                    activeFlow: state.activeFlow,
                    workingDir: state.workingDir,
                }
            }
            const nextProjectScope = nextProjectPath
                ? resolveProjectScopedWorkspace(nextProjectScopedWorkspaces[nextProjectPath], nextProjectPath)
                : null
            if (nextProjectPath && nextProjectScope) {
                nextProjectScopedWorkspaces[nextProjectPath] = nextProjectScope
            }
            if (nextProjectPath && nextProjectRegistry[nextProjectPath]) {
                nextProjectRegistry[nextProjectPath] = {
                    ...nextProjectRegistry[nextProjectPath],
                    lastAccessedAt: new Date().toISOString(),
                }
            }
            const nextViewMode = resolveViewModeForProjectScope(state.viewMode, nextProjectPath)
            saveRouteState({
                viewMode: nextViewMode,
                activeProjectPath: nextProjectPath,
            })
            return {
                activeProjectPath: nextProjectPath,
                viewMode: nextViewMode,
                projectRegistry: nextProjectRegistry,
                projectScopedWorkspaces: nextProjectScopedWorkspaces,
                recentProjectPaths: pushRecentProjectPath(state.recentProjectPaths, nextProjectPath),
                activeFlow: nextProjectPath && nextProjectScope ? nextProjectScope.activeFlow : null,
                executionFlow: isProjectSwitch ? null : state.executionFlow,
                selectedRunId: isProjectSwitch ? null : state.selectedRunId,
                workingDir: nextProjectPath && nextProjectScope ? nextProjectScope.workingDir : DEFAULT_WORKING_DIRECTORY,
                runtimeStatus: isProjectSwitch ? 'idle' : state.runtimeStatus,
                nodeStatuses: isProjectSwitch ? {} : state.nodeStatuses,
                humanGate: isProjectSwitch ? null : state.humanGate,
                logs: isProjectSwitch ? [] : state.logs,
                selectedNodeId: isProjectSwitch ? null : state.selectedNodeId,
                selectedEdgeId: isProjectSwitch ? null : state.selectedEdgeId,
                graphAttrs: isProjectSwitch ? {} : state.graphAttrs,
                graphAttrErrors: isProjectSwitch ? {} : state.graphAttrErrors,
                diagnostics: isProjectSwitch ? [] : state.diagnostics,
                nodeDiagnostics: isProjectSwitch ? {} : state.nodeDiagnostics,
                edgeDiagnostics: isProjectSwitch ? {} : state.edgeDiagnostics,
                hasValidationErrors: isProjectSwitch ? false : state.hasValidationErrors,
                saveState: isProjectSwitch ? 'idle' : state.saveState,
                saveErrorMessage: isProjectSwitch ? null : state.saveErrorMessage,
                saveErrorKind: isProjectSwitch ? null : state.saveErrorKind,
            }
        }),
    projectRegistrationError: null,
    registerProject: (directoryPath) => {
        let result: ProjectRegistrationResult = {
            ok: false,
            error: 'Project directory path is required.',
        }
        set((state) => {
            const normalizedPath = normalizeProjectPath(directoryPath)
            if (!normalizedPath) {
                result = {
                    ok: false,
                    error: 'Project directory path is required.',
                }
                return { projectRegistrationError: result.error }
            }
            if (!isAbsoluteProjectPath(normalizedPath)) {
                result = {
                    ok: false,
                    normalizedPath,
                    error: 'Project directory path must be absolute.',
                }
                return { projectRegistrationError: result.error }
            }

            const duplicate = Boolean(state.projectRegistry[normalizedPath])
            if (duplicate) {
                result = {
                    ok: false,
                    normalizedPath,
                    error: `Project already registered: ${normalizedPath}`,
                }
                return { projectRegistrationError: result.error }
            }

            const nextActiveProjectPath = state.activeProjectPath ?? normalizedPath
            const shouldActivateNewProject = !state.activeProjectPath
            const nowIso = shouldActivateNewProject ? new Date().toISOString() : null
            const nextProjectScopedWorkspaces = { ...state.projectScopedWorkspaces }
            const nextProjectRegistry = {
                ...state.projectRegistry,
                [normalizedPath]: {
                    directoryPath: normalizedPath,
                    isFavorite: false,
                    lastAccessedAt: nowIso,
                    flowBindings: {},
                },
            }
            nextProjectScopedWorkspaces[normalizedPath] = resolveProjectScopedWorkspace(
                nextProjectScopedWorkspaces[normalizedPath],
                normalizedPath,
            )
            const nextActiveProjectScope = resolveProjectScopedWorkspace(
                nextProjectScopedWorkspaces[nextActiveProjectPath],
                nextActiveProjectPath,
            )
            saveRouteState({
                viewMode: state.viewMode,
                activeProjectPath: nextActiveProjectPath,
            })
            result = {
                ok: true,
                normalizedPath,
            }
            return {
                projectRegistry: nextProjectRegistry,
                recentProjectPaths: shouldActivateNewProject
                    ? pushRecentProjectPath(state.recentProjectPaths, normalizedPath)
                    : state.recentProjectPaths,
                projectRegistrationError: null,
                activeProjectPath: nextActiveProjectPath,
                projectScopedWorkspaces: nextProjectScopedWorkspaces,
                activeFlow: state.activeProjectPath ? state.activeFlow : nextActiveProjectScope.activeFlow,
                executionFlow: state.activeProjectPath ? state.executionFlow : null,
                selectedRunId: state.activeProjectPath ? state.selectedRunId : null,
                workingDir: state.activeProjectPath ? state.workingDir : nextActiveProjectScope.workingDir,
            }
        })
        return result
    },
    updateProjectPath: (currentDirectoryPath, nextDirectoryPath) => {
        let result: ProjectRegistrationResult = {
            ok: false,
            error: 'Project directory path is required.',
        }
        set((state) => {
            const normalizedCurrentPath = normalizeProjectPath(currentDirectoryPath)
            const normalizedNextPath = normalizeProjectPath(nextDirectoryPath)

            if (!normalizedCurrentPath || !state.projectRegistry[normalizedCurrentPath]) {
                result = {
                    ok: false,
                    error: 'Project must already be registered before updating path.',
                }
                return { projectRegistrationError: result.error }
            }
            if (!normalizedNextPath) {
                result = {
                    ok: false,
                    error: 'Project directory path is required.',
                }
                return { projectRegistrationError: result.error }
            }
            if (!isAbsoluteProjectPath(normalizedNextPath)) {
                result = {
                    ok: false,
                    normalizedPath: normalizedNextPath,
                    error: 'Project directory path must be absolute.',
                }
                return { projectRegistrationError: result.error }
            }
            const duplicate = normalizedNextPath !== normalizedCurrentPath && Boolean(state.projectRegistry[normalizedNextPath])
            if (duplicate) {
                result = {
                    ok: false,
                    normalizedPath: normalizedNextPath,
                    error: `Project already registered: ${normalizedNextPath}`,
                }
                return { projectRegistrationError: result.error }
            }
            if (normalizedNextPath === normalizedCurrentPath) {
                result = {
                    ok: true,
                    normalizedPath: normalizedCurrentPath,
                }
                return { projectRegistrationError: null }
            }

            const nextProjectScopedWorkspaces = { ...state.projectScopedWorkspaces }
            const currentWorkspace = resolveProjectScopedWorkspace(
                nextProjectScopedWorkspaces[normalizedCurrentPath],
                normalizedCurrentPath,
            )
            delete nextProjectScopedWorkspaces[normalizedCurrentPath]
            nextProjectScopedWorkspaces[normalizedNextPath] = {
                ...currentWorkspace,
                workingDir: currentWorkspace.workingDir === normalizedCurrentPath
                    ? normalizedNextPath
                    : currentWorkspace.workingDir,
            }

            const nextProjectRegistry = { ...state.projectRegistry }
            delete nextProjectRegistry[normalizedCurrentPath]
            nextProjectRegistry[normalizedNextPath] = {
                ...state.projectRegistry[normalizedCurrentPath],
                directoryPath: normalizedNextPath,
            }
            const activeProjectWasUpdated = state.activeProjectPath === normalizedCurrentPath
            const nextActiveProjectPath = activeProjectWasUpdated ? normalizedNextPath : state.activeProjectPath
            const nextWorkingDir = activeProjectWasUpdated && state.workingDir === normalizedCurrentPath
                ? normalizedNextPath
                : state.workingDir
            const nextRecentProjectPaths = state.recentProjectPaths.map((path) =>
                path === normalizedCurrentPath ? normalizedNextPath : path,
            )

            saveRouteState({
                viewMode: state.viewMode,
                activeProjectPath: nextActiveProjectPath,
            })
            result = {
                ok: true,
                normalizedPath: normalizedNextPath,
            }
            return {
                projectRegistry: nextProjectRegistry,
                projectScopedWorkspaces: nextProjectScopedWorkspaces,
                activeProjectPath: nextActiveProjectPath,
                workingDir: nextWorkingDir,
                recentProjectPaths: nextRecentProjectPaths,
                projectRegistrationError: null,
            }
        })
        return result
    },
    toggleProjectFavorite: (projectPath) =>
        set((state) => {
            const normalizedPath = normalizeProjectPath(projectPath)
            const project = state.projectRegistry[normalizedPath]
            if (!project) {
                return state
            }
            const nextProjectRegistry = {
                ...state.projectRegistry,
                [normalizedPath]: {
                    ...project,
                    isFavorite: !project.isFavorite,
                },
            }
            return {
                projectRegistry: nextProjectRegistry,
            }
        }),
    setProjectRegistrationError: (error) => set({ projectRegistrationError: error }),
    clearProjectRegistrationError: () => set({ projectRegistrationError: null }),
    activeFlow: restoredProjectScope ? restoredProjectScope.activeFlow : null,
    setActiveFlow: (flow) =>
        set((state) => {
            if (!state.activeProjectPath) {
                return { activeFlow: null }
            }
            const nextProjectScopedWorkspaces = { ...state.projectScopedWorkspaces }
            const scoped = resolveProjectScopedWorkspace(nextProjectScopedWorkspaces[state.activeProjectPath], state.activeProjectPath)
            nextProjectScopedWorkspaces[state.activeProjectPath] = {
                ...scoped,
                activeFlow: flow,
            }
            return {
                activeFlow: flow,
                projectScopedWorkspaces: nextProjectScopedWorkspaces,
            }
        }),
    setConversationId: (id) =>
        set((state) => {
            if (!state.activeProjectPath) {
                return {}
            }
            const nextProjectScopedWorkspaces = { ...state.projectScopedWorkspaces }
            const scoped = resolveProjectScopedWorkspace(nextProjectScopedWorkspaces[state.activeProjectPath], state.activeProjectPath)
            nextProjectScopedWorkspaces[state.activeProjectPath] = {
                ...scoped,
                conversationId: id,
            }
            return {
                projectScopedWorkspaces: nextProjectScopedWorkspaces,
            }
        }),
    appendProjectEventEntry: (entry) =>
        set((state) => {
            if (!state.activeProjectPath) {
                return {}
            }
            const nextProjectScopedWorkspaces = { ...state.projectScopedWorkspaces }
            const scoped = resolveProjectScopedWorkspace(nextProjectScopedWorkspaces[state.activeProjectPath], state.activeProjectPath)
            nextProjectScopedWorkspaces[state.activeProjectPath] = {
                ...scoped,
                projectEventLog: [...scoped.projectEventLog, entry],
            }
            return {
                projectScopedWorkspaces: nextProjectScopedWorkspaces,
            }
        }),
    updateProjectScopedWorkspace: (projectPath, patch) =>
        set((state) => {
            const normalizedProjectPath = normalizeProjectPath(projectPath)
            if (!normalizedProjectPath || !isAbsoluteProjectPath(normalizedProjectPath)) {
                return {}
            }
            const nextProjectScopedWorkspaces = { ...state.projectScopedWorkspaces }
            const scoped = resolveProjectScopedWorkspace(nextProjectScopedWorkspaces[normalizedProjectPath], normalizedProjectPath)
            const nextScopedWorkspace = {
                ...scoped,
                ...patch,
            }
            nextProjectScopedWorkspaces[normalizedProjectPath] = nextScopedWorkspace
            const isActiveScope = state.activeProjectPath === normalizedProjectPath
            if (!isActiveScope) {
                return {
                    projectScopedWorkspaces: nextProjectScopedWorkspaces,
                }
            }
            saveRouteState({
                viewMode: state.viewMode,
                activeProjectPath: state.activeProjectPath,
            })
            return {
                projectScopedWorkspaces: nextProjectScopedWorkspaces,
                activeFlow: nextScopedWorkspace.activeFlow,
                workingDir: nextScopedWorkspace.workingDir,
            }
        }),
    setSpecId: (id) =>
        set((state) => updateArtifactField(state, 'specId', id)),
    setSpecStatus: (status) =>
        set((state) => updateArtifactField(state, 'specStatus', status)),
    setSpecProvenance: (provenance) =>
        set((state) => updateArtifactField(state, 'specProvenance', provenance)),
    setPlanId: (id) =>
        set((state) => updateArtifactField(state, 'planId', id)),
    setPlanStatus: (status) =>
        set((state) => updateArtifactField(state, 'planStatus', status)),
    setPlanProvenance: (provenance) =>
        set((state) => updateArtifactField(state, 'planProvenance', provenance)),
    getProjectScopedArtifactState: (projectPath) =>
        selectProjectScopedArtifactState(get().projectScopedWorkspaces, projectPath),
})

const updateArtifactField = <
    Key extends keyof Pick<
        ProjectScopedWorkspace,
        'specId' | 'specStatus' | 'specProvenance' | 'planId' | 'planStatus' | 'planProvenance'
    >,
>(
    state: AppState,
    key: Key,
    value: ProjectScopedWorkspace[Key],
) => {
    if (!state.activeProjectPath) {
        return {}
    }
    const nextProjectScopedWorkspaces = { ...state.projectScopedWorkspaces }
    const scoped = resolveProjectScopedWorkspace(nextProjectScopedWorkspaces[state.activeProjectPath], state.activeProjectPath)
    nextProjectScopedWorkspaces[state.activeProjectPath] = {
        ...scoped,
        [key]: value,
    }
    return {
        projectScopedWorkspaces: nextProjectScopedWorkspaces,
    }
}
