import { useStore } from "@/store"
import { type FormEvent, useEffect, useState } from "react"

const buildProjectScopedArtifactId = (artifactType: "conversation" | "spec" | "plan", projectPath: string) => {
    const normalizedProjectKey = projectPath
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/(^-|-$)/g, "")
    const suffix = normalizedProjectKey || "project"
    return `${artifactType}-${suffix}-${Date.now()}`
}

export function ProjectsPanel() {
    const projectRegistry = useStore((state) => state.projectRegistry)
    const projects = Object.values(projectRegistry)
    const recentProjectPaths = useStore((state) => state.recentProjectPaths)
    const activeProjectPath = useStore((state) => state.activeProjectPath)
    const projectScopedWorkspaces = useStore((state) => state.projectScopedWorkspaces)
    const projectRegistrationError = useStore((state) => state.projectRegistrationError)
    const registerProject = useStore((state) => state.registerProject)
    const updateProjectPath = useStore((state) => state.updateProjectPath)
    const toggleProjectFavorite = useStore((state) => state.toggleProjectFavorite)
    const clearProjectRegistrationError = useStore((state) => state.clearProjectRegistrationError)
    const setActiveProjectPath = useStore((state) => state.setActiveProjectPath)
    const setConversationId = useStore((state) => state.setConversationId)
    const setSpecId = useStore((state) => state.setSpecId)
    const setPlanId = useStore((state) => state.setPlanId)
    const [directoryPathInput, setDirectoryPathInput] = useState("")
    const [editingProjectPath, setEditingProjectPath] = useState<string | null>(null)
    const [editingDirectoryPathInput, setEditingDirectoryPathInput] = useState("")
    const [projectBranches, setProjectBranches] = useState<Record<string, string | null>>({})
    const activeProjectScope = activeProjectPath ? projectScopedWorkspaces[activeProjectPath] : null
    const favoriteProjects = projects.filter((project) => project.isFavorite)
    const recentProjects = recentProjectPaths
        .map((projectPath) => projectRegistry[projectPath])
        .filter((project): project is (typeof projects)[number] => Boolean(project))

    useEffect(() => {
        const projectPathsToFetch = projects
            .map((project) => project.directoryPath)
            .filter((projectPath) => !(projectPath in projectBranches))
        if (projectPathsToFetch.length === 0) {
            return
        }

        let isCancelled = false
        const loadBranches = async () => {
            const entries = await Promise.all(
                projectPathsToFetch.map(async (projectPath) => {
                    try {
                        const response = await fetch(`/api/projects/metadata?directory=${encodeURIComponent(projectPath)}`)
                        if (!response.ok) {
                            return [projectPath, null] as const
                        }
                        const payload = (await response.json()) as { branch?: string | null }
                        return [projectPath, typeof payload.branch === "string" ? payload.branch : null] as const
                    } catch {
                        return [projectPath, null] as const
                    }
                })
            )

            if (isCancelled) {
                return
            }

            setProjectBranches((current) => {
                const next = { ...current }
                entries.forEach(([projectPath, branch]) => {
                    next[projectPath] = branch
                })
                return next
            })
        }

        void loadBranches()
        return () => {
            isCancelled = true
        }
    }, [projects, projectBranches])

    const formatLastActivity = (value: string | null) => {
        if (!value) {
            return "No activity yet"
        }
        const parsed = new Date(value)
        if (Number.isNaN(parsed.getTime())) {
            return "Unknown activity time"
        }
        return parsed.toLocaleString()
    }

    const onRegisterProject = () => {
        const result = registerProject(directoryPathInput)
        if (result.ok) {
            setDirectoryPathInput("")
        }
    }

    const onSubmitProjectRegistration = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault()
        onRegisterProject()
    }

    const onStartProjectPathEdit = (projectPath: string) => {
        setEditingProjectPath(projectPath)
        setEditingDirectoryPathInput(projectPath)
        clearProjectRegistrationError()
    }

    const onCancelProjectPathEdit = () => {
        setEditingProjectPath(null)
        setEditingDirectoryPathInput("")
        clearProjectRegistrationError()
    }

    const onOpenConversation = () => {
        if (!activeProjectPath) {
            return
        }
        setConversationId(activeProjectScope?.conversationId || buildProjectScopedArtifactId("conversation", activeProjectPath))
    }

    const onStartConversation = () => {
        if (!activeProjectPath) {
            return
        }
        setConversationId(buildProjectScopedArtifactId("conversation", activeProjectPath))
    }

    const onContinueConversation = () => {
        if (!activeProjectScope?.conversationId) {
            return
        }
        setConversationId(activeProjectScope.conversationId)
    }

    const onOpenSpec = () => {
        if (!activeProjectPath) {
            return
        }
        setSpecId(activeProjectScope?.specId || buildProjectScopedArtifactId("spec", activeProjectPath))
    }

    const onOpenPlan = () => {
        if (!activeProjectPath) {
            return
        }
        setPlanId(activeProjectScope?.planId || buildProjectScopedArtifactId("plan", activeProjectPath))
    }

    return (
        <section data-testid="projects-panel" className="flex-1 overflow-auto p-6">
            <div className="mx-auto w-full max-w-3xl space-y-6">
                <div className="space-y-1">
                    <h2 className="text-lg font-semibold">Projects</h2>
                    <p className="text-sm text-muted-foreground">
                        Project registration, selection, and workflow scoping live in this workspace.
                    </p>
                </div>
                <div className="rounded-md border border-border bg-card p-4 text-sm text-muted-foreground shadow-sm">
                    Projects workspace is now a first-class navigation area. Project registry and Git gating controls are tracked in the next checklist slices.
                </div>
                <div className="rounded-md border border-border bg-card p-4 shadow-sm">
                    <div className="mb-3 space-y-1">
                        <h3 className="text-sm font-semibold text-foreground">Quick Switch</h3>
                        <p className="text-xs text-muted-foreground">Use favorites and recents to switch project context quickly.</p>
                    </div>
                    <div className="grid gap-4 md:grid-cols-2">
                        <div className="space-y-2">
                            <p className="text-xs font-medium text-foreground">Favorites</p>
                            <ul data-testid="favorite-projects-list" className="space-y-2">
                                {favoriteProjects.length === 0 ? (
                                    <li className="rounded-md border border-dashed border-border px-3 py-2 text-xs text-muted-foreground">
                                        No favorited projects yet.
                                    </li>
                                ) : (
                                    favoriteProjects.map((project) => {
                                        const projectPath = project.directoryPath
                                        return (
                                            <li key={`favorite-${projectPath}`}>
                                                <button
                                                    type="button"
                                                    onClick={() => setActiveProjectPath(projectPath)}
                                                    className="w-full rounded border border-border px-3 py-2 text-left text-xs hover:bg-muted"
                                                >
                                                    {projectPath}
                                                </button>
                                            </li>
                                        )
                                    })
                                )}
                            </ul>
                        </div>
                        <div className="space-y-2">
                            <p className="text-xs font-medium text-foreground">Recent</p>
                            <ul data-testid="recent-projects-list" className="space-y-2">
                                {recentProjects.length === 0 ? (
                                    <li className="rounded-md border border-dashed border-border px-3 py-2 text-xs text-muted-foreground">
                                        No recent project switches yet.
                                    </li>
                                ) : (
                                    recentProjects.map((project) => {
                                        const projectPath = project.directoryPath
                                        return (
                                            <li key={`recent-${projectPath}`}>
                                                <button
                                                    type="button"
                                                    onClick={() => setActiveProjectPath(projectPath)}
                                                    className="w-full rounded border border-border px-3 py-2 text-left text-xs hover:bg-muted"
                                                >
                                                    {projectPath}
                                                </button>
                                            </li>
                                        )
                                    })
                                )}
                            </ul>
                        </div>
                    </div>
                </div>
                <div data-testid="project-scope-entrypoints" className="rounded-md border border-border bg-card p-4 shadow-sm">
                    <div className="mb-3 space-y-1">
                        <h3 className="text-sm font-semibold text-foreground">Project-Scoped Entry Points</h3>
                        <p className="text-xs text-muted-foreground">
                            Conversation, spec, and plan artifacts are scoped to the active project.
                        </p>
                    </div>
                    {!activeProjectPath ? (
                        <p className="rounded-md border border-dashed border-border px-3 py-2 text-sm text-muted-foreground">
                            Select an active project to access conversation, spec, and plan entry points.
                        </p>
                    ) : (
                        <div className="space-y-3">
                            <div data-testid="project-conversation-entrypoint" className="rounded-md border border-border px-3 py-2">
                                <div className="mb-2 flex items-center justify-between gap-3">
                                    <p className="text-sm font-medium text-foreground">Conversation</p>
                                    <button
                                        type="button"
                                        onClick={onOpenConversation}
                                        className="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                                    >
                                        {activeProjectScope?.conversationId ? "Open conversation" : "Start conversation"}
                                    </button>
                                </div>
                                <p className="truncate text-xs text-muted-foreground">
                                    {activeProjectScope?.conversationId || "No conversation artifact selected yet."}
                                </p>
                            </div>
                            <div data-testid="project-spec-entrypoint" className="rounded-md border border-border px-3 py-2">
                                <div className="mb-2 flex items-center justify-between gap-3">
                                    <p className="text-sm font-medium text-foreground">Spec</p>
                                    <button
                                        type="button"
                                        onClick={onOpenSpec}
                                        className="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                                    >
                                        {activeProjectScope?.specId ? "Open spec" : "Create spec"}
                                    </button>
                                </div>
                                <p className="truncate text-xs text-muted-foreground">
                                    {activeProjectScope?.specId || "No spec artifact selected yet."}
                                </p>
                            </div>
                            <div data-testid="project-plan-entrypoint" className="rounded-md border border-border px-3 py-2">
                                <div className="mb-2 flex items-center justify-between gap-3">
                                    <p className="text-sm font-medium text-foreground">Plan</p>
                                    <button
                                        type="button"
                                        onClick={onOpenPlan}
                                        className="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                                    >
                                        {activeProjectScope?.planId ? "Open plan" : "Create plan"}
                                    </button>
                                </div>
                                <p className="truncate text-xs text-muted-foreground">
                                    {activeProjectScope?.planId || "No plan artifact selected yet."}
                                </p>
                            </div>
                        </div>
                    )}
                </div>
                <div data-testid="project-ai-conversation-surface" className="rounded-md border border-border bg-card p-4 shadow-sm">
                    <div className="mb-3 space-y-1">
                        <h3 className="text-sm font-semibold text-foreground">Project-Scoped AI Conversation</h3>
                        <p className="text-xs text-muted-foreground">
                            Start a new project conversation or continue an existing one in the active project scope.
                        </p>
                    </div>
                    {!activeProjectPath ? (
                        <p className="rounded-md border border-dashed border-border px-3 py-2 text-sm text-muted-foreground">
                            Select an active project to start or continue a project-scoped AI conversation.
                        </p>
                    ) : (
                        <div className="space-y-3">
                            <p className="truncate rounded-md border border-border px-3 py-2 text-xs text-muted-foreground">
                                Active conversation artifact: {activeProjectScope?.conversationId || "No project conversation selected yet."}
                            </p>
                            <div className="flex flex-wrap items-center gap-2">
                                <button
                                    data-testid="project-ai-conversation-start-button"
                                    type="button"
                                    onClick={onStartConversation}
                                    className="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                                >
                                    Start conversation
                                </button>
                                <button
                                    data-testid="project-ai-conversation-continue-button"
                                    type="button"
                                    onClick={onContinueConversation}
                                    disabled={!activeProjectScope?.conversationId}
                                    className="rounded border border-border px-2 py-1 text-xs hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                    Continue conversation
                                </button>
                            </div>
                        </div>
                    )}
                </div>
                <div className="rounded-md border border-border bg-card p-4 shadow-sm">
                    <form data-testid="project-register-form" onSubmit={onSubmitProjectRegistration}>
                        <label htmlFor="project-path-input" className="mb-2 block text-xs font-medium text-foreground">
                            Project directory path
                        </label>
                        <div className="mb-3 flex gap-2">
                            <input
                                id="project-path-input"
                                data-testid="project-path-input"
                                type="text"
                                value={directoryPathInput}
                                onChange={(event) => {
                                    setDirectoryPathInput(event.target.value)
                                    clearProjectRegistrationError()
                                }}
                                placeholder="/absolute/path/to/project"
                                className="h-9 flex-1 rounded-md border border-input bg-background px-3 text-sm"
                            />
                            <button
                                data-testid="project-register-button"
                                type="submit"
                                className="inline-flex h-9 items-center justify-center rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:bg-primary/90"
                            >
                                Register
                            </button>
                        </div>
                    </form>
                    {projectRegistrationError ? (
                        <p data-testid="project-registration-error" className="mb-3 text-sm text-destructive">
                            {projectRegistrationError}
                        </p>
                    ) : null}
                    <ul data-testid="project-registry-list" className="space-y-2">
                        {projects.length === 0 ? (
                            <li className="rounded-md border border-dashed border-border px-3 py-2 text-sm text-muted-foreground">
                                No projects registered yet.
                            </li>
                        ) : (
                            projects.map((project) => {
                                const isActive = project.directoryPath === activeProjectPath
                                const isEditing = editingProjectPath === project.directoryPath
                                return (
                                    <li key={project.directoryPath} className="rounded-md border border-border px-3 py-2">
                                        {isEditing ? (
                                            <div className="space-y-2">
                                                <input
                                                    data-testid="project-edit-input"
                                                    type="text"
                                                    value={editingDirectoryPathInput}
                                                    onChange={(event) => {
                                                        setEditingDirectoryPathInput(event.target.value)
                                                        clearProjectRegistrationError()
                                                    }}
                                                    className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                                                />
                                                <div className="flex items-center justify-end gap-2">
                                                    <button
                                                        data-testid="project-edit-cancel-button"
                                                        type="button"
                                                        onClick={onCancelProjectPathEdit}
                                                        className="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                                                    >
                                                        Cancel
                                                    </button>
                                                    <button
                                                        data-testid="project-edit-save-button"
                                                        type="button"
                                                        onClick={() => {
                                                            const result = updateProjectPath(project.directoryPath, editingDirectoryPathInput)
                                                            if (result.ok) {
                                                                setEditingProjectPath(null)
                                                                setEditingDirectoryPathInput("")
                                                            }
                                                        }}
                                                        className="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                                                    >
                                                        Save
                                                    </button>
                                                </div>
                                            </div>
                                        ) : (
                                            <div className="flex items-center justify-between gap-3">
                                                <div className="min-w-0 flex-1 space-y-1">
                                                    {(() => {
                                                        const projectName = project.directoryPath.split('/').filter(Boolean).pop() || project.directoryPath
                                                        const branchLabel = projectBranches[project.directoryPath] || "Unknown branch"
                                                        const lastActivityLabel = formatLastActivity(project.lastAccessedAt)
                                                        return (
                                                            <>
                                                                <p data-testid="project-metadata-name" className="truncate text-sm font-medium text-foreground">
                                                                    Name: {projectName}
                                                                </p>
                                                                <p data-testid="project-metadata-directory" className="truncate text-xs text-muted-foreground">
                                                                    Directory: {project.directoryPath}
                                                                </p>
                                                                <p data-testid="project-metadata-branch" className="truncate text-xs text-muted-foreground">
                                                                    Branch: {branchLabel}
                                                                </p>
                                                                <p data-testid="project-metadata-last-activity" className="truncate text-xs text-muted-foreground">
                                                                    Last activity: {lastActivityLabel}
                                                                </p>
                                                            </>
                                                        )
                                                    })()}
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <button
                                                        data-testid="favorite-toggle-button"
                                                        type="button"
                                                        onClick={() => toggleProjectFavorite(project.directoryPath)}
                                                        className="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                                                    >
                                                        {project.isFavorite ? "Unfavorite" : "Favorite"}
                                                    </button>
                                                    <button
                                                        type="button"
                                                        onClick={() => setActiveProjectPath(project.directoryPath)}
                                                        className="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                                                    >
                                                        {isActive ? "Active" : "Set active"}
                                                    </button>
                                                    <button
                                                        data-testid="project-edit-button"
                                                        type="button"
                                                        onClick={() => onStartProjectPathEdit(project.directoryPath)}
                                                        className="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                                                    >
                                                        Update path
                                                    </button>
                                                </div>
                                            </div>
                                        )}
                                    </li>
                                )
                            })
                        )}
                    </ul>
                </div>
            </div>
        </section>
    )
}
