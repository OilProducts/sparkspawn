import { useCallback, type ChangeEvent, type Dispatch, type MutableRefObject, type SetStateAction } from 'react'

import { useStore } from '@/store'
import {
    ApiHttpError,
    deleteProjectValidated,
    pickProjectDirectoryValidated,
    registerProjectValidated,
} from '@/lib/workspaceClient'
import { useDialogController } from '@/components/app/dialog-controller'
import type { ProjectGitMetadata } from '../model/presentation'
import {
    deriveProjectPathFromDirectorySelection,
    extractApiErrorMessage,
    formatProjectListLabel,
    removeProjectFromCache,
    resolveProjectPathValidation,
    toHydratedProjectRecord,
    type ProjectConversationCacheState,
} from '../model/projectsHomeState'

type ProjectRecord = {
    directoryPath: string
}

type PersistProjectState = (
    projectPath: string,
    patch: {
        last_accessed_at?: string | null
        active_conversation_id?: string | null
        is_favorite?: boolean | null
    },
) => Promise<void>

type UseProjectRegistryActionsArgs = {
    activeProjectPath: string | null
    projectRegistry: Record<string, unknown>
    orderedProjects: ProjectRecord[]
    projectDirectoryPickerInputRef: MutableRefObject<HTMLInputElement | null>
    setPanelError: (value: string | null) => void
    setPendingDeleteProjectPath: (value: string | null) => void
    setProjectRegistrationError: (value: string | null) => void
    clearProjectRegistrationError: () => void
    setProjectGitMetadata: Dispatch<SetStateAction<Record<string, ProjectGitMetadata>>>
    ensureProjectGitRepository: (projectPath: string) => Promise<ProjectGitMetadata | null>
    registerProject: (directoryPath: string) => { ok: boolean; error?: string | null }
    upsertProjectRegistryEntry: (project: ReturnType<typeof toHydratedProjectRecord>) => void
    commitConversationCache: (
        next:
            | ProjectConversationCacheState
            | ((current: ProjectConversationCacheState) => ProjectConversationCacheState),
    ) => void
    removeProject: (directoryPath: string, nextActiveProjectPath?: string | null) => void
    setActiveProjectPath: (projectPath: string | null) => void
    appendLocalProjectEvent: (message: string) => void
    persistProjectState: PersistProjectState
}

export function useProjectRegistryActions({
    activeProjectPath,
    projectRegistry,
    orderedProjects,
    projectDirectoryPickerInputRef,
    setPanelError,
    setPendingDeleteProjectPath,
    setProjectRegistrationError,
    clearProjectRegistrationError,
    setProjectGitMetadata,
    ensureProjectGitRepository,
    registerProject,
    upsertProjectRegistryEntry,
    commitConversationCache,
    removeProject,
    setActiveProjectPath,
    appendLocalProjectEvent,
    persistProjectState,
}: UseProjectRegistryActionsArgs) {
    const { confirm } = useDialogController()

    const registerProjectFromPath = useCallback(async (rawProjectPath: string) => {
        const validation = resolveProjectPathValidation(rawProjectPath, projectRegistry)
        if (!validation.ok || !validation.normalizedPath) {
            setProjectRegistrationError(validation.error ?? 'Project directory path is required.')
            return
        }
        const normalizedProjectPath = validation.normalizedPath
        const gitMetadata = await ensureProjectGitRepository(normalizedProjectPath)
        if (!gitMetadata) {
            return
        }
        const result = registerProject(normalizedProjectPath)
        if (!result.ok) {
            setProjectRegistrationError(result.error ?? 'Unable to register the project.')
            return
        }
        try {
            const projectRecord = await registerProjectValidated(normalizedProjectPath)
            upsertProjectRegistryEntry(toHydratedProjectRecord(projectRecord))
        } catch (error) {
            useStore.setState((state) => {
                const nextProjectRegistry = { ...state.projectRegistry }
                const nextProjectSessionStates = { ...state.projectSessionsByPath }
                delete nextProjectRegistry[normalizedProjectPath]
                delete nextProjectSessionStates[normalizedProjectPath]
                const nextActiveProjectPath = state.activeProjectPath === normalizedProjectPath ? null : state.activeProjectPath
                return {
                    projectRegistry: nextProjectRegistry,
                    projectSessionsByPath: nextProjectSessionStates,
                    activeProjectPath: nextActiveProjectPath,
                    activeFlow: state.activeFlow,
                    selectedRunId: nextActiveProjectPath ? state.selectedRunId : null,
                    workingDir: nextActiveProjectPath ? state.workingDir : './test-app',
                }
            })
            setProjectRegistrationError(extractApiErrorMessage(error, 'Unable to register the project.'))
            return
        }
        setProjectRegistrationError(null)
    }, [
        ensureProjectGitRepository,
        projectRegistry,
        registerProject,
        setProjectRegistrationError,
        upsertProjectRegistryEntry,
    ])

    const onOpenProjectDirectoryChooser = useCallback(async () => {
        clearProjectRegistrationError()
        try {
            const selection = await pickProjectDirectoryValidated()
            if (selection.status === 'canceled') {
                return
            }
            await registerProjectFromPath(selection.directory_path)
            return
        } catch (error) {
            const canUseBrowserFallback = error instanceof ApiHttpError
                && [404, 405, 501, 503].includes(error.status)
                && projectDirectoryPickerInputRef.current
            if (!canUseBrowserFallback) {
                setProjectRegistrationError(extractApiErrorMessage(error, 'Directory picker is unavailable.'))
                return
            }
        }
        if (!projectDirectoryPickerInputRef.current) {
            setProjectRegistrationError('Directory picker is unavailable.')
            return
        }
        projectDirectoryPickerInputRef.current.value = ''
        projectDirectoryPickerInputRef.current.click()
    }, [
        clearProjectRegistrationError,
        projectDirectoryPickerInputRef,
        registerProjectFromPath,
        setProjectRegistrationError,
    ])

    const onProjectDirectorySelected = useCallback((event: ChangeEvent<HTMLInputElement>) => {
        const files = event.target.files
        const selectedProjectPath = deriveProjectPathFromDirectorySelection(files)
        event.target.value = ''
        if (!selectedProjectPath) {
            setProjectRegistrationError(
                'Unable to resolve an absolute project path from the selected directory.',
            )
            return
        }
        void registerProjectFromPath(selectedProjectPath)
    }, [registerProjectFromPath, setProjectRegistrationError])

    const onActivateProject = useCallback(async (projectPath: string) => {
        if (!projectPath) {
            return
        }
        if (projectPath === activeProjectPath) {
            setActiveProjectPath(projectPath)
            return
        }
        const gitMetadata = await ensureProjectGitRepository(projectPath)
        if (!gitMetadata) {
            return
        }
        setProjectRegistrationError(null)
        setActiveProjectPath(projectPath)
        void persistProjectState(projectPath, {
            last_accessed_at: new Date().toISOString(),
        })
    }, [
        activeProjectPath,
        ensureProjectGitRepository,
        persistProjectState,
        setActiveProjectPath,
        setProjectRegistrationError,
    ])

    const onDeleteProject = useCallback(async (projectPath: string) => {
        const projectLabel = formatProjectListLabel(projectPath)
        const confirmed = await confirm({
            title: 'Remove project?',
            description: `Remove project "${projectLabel}" from Spark? This deletes its local threads, workflow history, and runs, but does not delete the project files.`,
            confirmLabel: 'Remove project',
            cancelLabel: 'Keep project',
            confirmVariant: 'destructive',
        })
        if (!confirmed) {
            return
        }

        setPanelError(null)
        setPendingDeleteProjectPath(projectPath)
        try {
            await deleteProjectValidated(projectPath)

            setProjectGitMetadata((current) => {
                const next = { ...current }
                delete next[projectPath]
                return next
            })
            commitConversationCache((current) => removeProjectFromCache(current, projectPath))

            const fallbackProjectPath = activeProjectPath === projectPath
                ? orderedProjects.find((project) => project.directoryPath !== projectPath)?.directoryPath || null
                : null
            removeProject(projectPath, fallbackProjectPath)
        } catch (error) {
            const message = extractApiErrorMessage(error, 'Unable to remove the project.')
            setPanelError(message)
            appendLocalProjectEvent(`Project removal failed: ${message}`)
        } finally {
            setPendingDeleteProjectPath(null)
        }
    }, [
        activeProjectPath,
        appendLocalProjectEvent,
        commitConversationCache,
        confirm,
        orderedProjects,
        removeProject,
        setPanelError,
        setPendingDeleteProjectPath,
        setProjectGitMetadata,
    ])

    return {
        onActivateProject,
        onDeleteProject,
        onOpenProjectDirectoryChooser,
        onProjectDirectorySelected,
        registerProjectFromPath,
    }
}
