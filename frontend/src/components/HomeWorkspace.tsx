import type { ReactNode } from "react"

interface HomeWorkspaceProps {
    children: ReactNode
}

export function HomeWorkspace({ children }: HomeWorkspaceProps) {
    return (
        <div data-testid="home-workspace" className="space-y-4">
            {children}
        </div>
    )
}
