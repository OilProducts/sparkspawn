export function ProjectsPanel() {
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
            </div>
        </section>
    )
}
