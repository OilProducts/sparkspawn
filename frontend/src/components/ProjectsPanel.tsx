import { useStore } from "@/store"
import { useState } from "react"

export function ProjectsPanel() {
    const projectRegistry = useStore((state) => state.projectRegistry)
    const projects = Object.values(projectRegistry)
    const activeProjectPath = useStore((state) => state.activeProjectPath)
    const projectRegistrationError = useStore((state) => state.projectRegistrationError)
    const registerProject = useStore((state) => state.registerProject)
    const clearProjectRegistrationError = useStore((state) => state.clearProjectRegistrationError)
    const setActiveProjectPath = useStore((state) => state.setActiveProjectPath)
    const [directoryPathInput, setDirectoryPathInput] = useState("")

    const onRegisterProject = () => {
        const result = registerProject(directoryPathInput)
        if (result.ok) {
            setDirectoryPathInput("")
        }
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
                    <div className="mb-3 flex gap-2">
                        <input
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
                            type="button"
                            onClick={onRegisterProject}
                            className="inline-flex h-9 items-center justify-center rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground hover:bg-primary/90"
                        >
                            Register
                        </button>
                    </div>
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
                                return (
                                    <li key={project.directoryPath} className="flex items-center justify-between rounded-md border border-border px-3 py-2">
                                        <span className="truncate text-sm">{project.directoryPath}</span>
                                        <button
                                            type="button"
                                            onClick={() => setActiveProjectPath(project.directoryPath)}
                                            className="ml-3 rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                                        >
                                            {isActive ? "Active" : "Set active"}
                                        </button>
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
