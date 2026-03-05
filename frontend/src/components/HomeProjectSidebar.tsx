import type { ReactNode } from "react"

interface HomeProjectSidebarProps {
    children: ReactNode
}

export function HomeProjectSidebar({ children }: HomeProjectSidebarProps) {
    return (
        <aside
            data-testid="home-project-sidebar"
            className="flex flex-col gap-4 lg:sticky lg:top-4 lg:max-h-[calc(100vh-7.5rem)] lg:self-start"
        >
            {children}
        </aside>
    )
}
