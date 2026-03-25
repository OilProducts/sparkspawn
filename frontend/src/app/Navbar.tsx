import { type KeyboardEvent } from "react"
import { useStore, type ViewMode } from "@/store"
import { useNarrowViewport } from '@/lib/useNarrowViewport'
import { Settings2 } from "lucide-react"
import { Button } from "@/ui"

const NAV_MODE_ORDER: ViewMode[] = ['home', 'editor', 'execution', 'triggers', 'settings', 'runs']
const NAV_MODE_BUTTON_CLASS = 'flex-1 rounded-sm px-3 py-1.5 text-sm'

const NAV_MODE_ITEMS: Array<{
    buttonTestId: string
    label: string
    labelTestId?: string
    mode: ViewMode
}> = [
    {
        buttonTestId: 'nav-mode-projects',
        label: 'Home',
        labelTestId: 'nav-mode-home',
        mode: 'home',
    },
    {
        buttonTestId: 'nav-mode-editor',
        label: 'Editor',
        mode: 'editor',
    },
    {
        buttonTestId: 'nav-mode-execution',
        label: 'Execution',
        mode: 'execution',
    },
    {
        buttonTestId: 'nav-mode-triggers',
        label: 'Triggers',
        mode: 'triggers',
    },
    {
        buttonTestId: 'nav-mode-settings',
        label: 'Settings',
        mode: 'settings',
    },
    {
        buttonTestId: 'nav-mode-runs',
        label: 'Runs',
        mode: 'runs',
    },
]

export function Navbar() {
    const viewMode = useStore((state) => state.viewMode)
    const setViewMode = useStore((state) => state.setViewMode)
    const isNarrowViewport = useNarrowViewport()
    const activeProjectPath = useStore((state) => state.activeProjectPath)

    const resolveNextKeyboardMode = (mode: ViewMode, direction: -1 | 1): ViewMode => {
        const modeCycle: ViewMode[] = NAV_MODE_ORDER
        const currentIndex = modeCycle.indexOf(mode)
        const startIndex = currentIndex >= 0 ? currentIndex : 0
        const nextIndex = (startIndex + direction + modeCycle.length) % modeCycle.length
        return modeCycle[nextIndex]
    }

    const resolveModeButtonTestId = (mode: ViewMode) => (
        NAV_MODE_ITEMS.find((item) => item.mode === mode)?.buttonTestId || `nav-mode-${mode}`
    )

    const focusModeButton = (mode: ViewMode) => {
        document.querySelector<HTMLButtonElement>(`[data-testid="${resolveModeButtonTestId(mode)}"]`)?.focus()
    }

    const onViewModeKeyDown = (event: KeyboardEvent<HTMLButtonElement>, mode: ViewMode) => {
        if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') {
            return
        }
        event.preventDefault()
        const nextMode = resolveNextKeyboardMode(mode, event.key === 'ArrowRight' ? 1 : -1)
        setViewMode(nextMode)
        focusModeButton(nextMode)
    }

    const projectLabel = activeProjectPath || "No active project"

    return (
        <header
            data-testid="top-nav"
            data-responsive-layout={isNarrowViewport ? 'stacked' : 'inline'}
            className={`border-b bg-background shrink-0 z-50 ${isNarrowViewport
                ? 'flex min-h-14 flex-col items-stretch gap-2 px-3 py-2'
                : 'h-14 flex items-center justify-between px-6'
                }`}
        >
            <div className={isNarrowViewport ? 'flex flex-col gap-2' : 'flex items-center gap-8'}>
                <div className="flex items-center gap-2">
                    <Settings2 className="w-5 h-5" />
                    <span className="font-semibold tracking-tight">Spark</span>
                </div>

                <div
                    data-testid="view-mode-tabs"
                    data-responsive-layout={isNarrowViewport ? 'stacked' : 'inline'}
                    className={`inline-flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground ${isNarrowViewport ? 'w-full' : 'w-[480px]'}`}
                >
                    {NAV_MODE_ITEMS.map((item) => {
                        const isActive = item.mode === 'home'
                            ? (viewMode === 'home' || viewMode === 'projects')
                            : viewMode === item.mode
                        return (
                            <Button
                                key={item.mode}
                                type="button"
                                data-testid={item.buttonTestId}
                                aria-current={isActive ? 'page' : undefined}
                                onClick={() => setViewMode(item.mode)}
                                onKeyDown={(event) => onViewModeKeyDown(event, item.mode)}
                                variant={isActive ? 'secondary' : 'ghost'}
                                className={NAV_MODE_BUTTON_CLASS}
                            >
                                {item.labelTestId ? (
                                    <span data-testid={item.labelTestId}>{item.label}</span>
                                ) : item.label}
                            </Button>
                        )
                    })}
                </div>
            </div>
            <div
                data-testid="top-nav-active-project"
                className={`max-w-full truncate rounded border border-border bg-muted/40 px-2 py-1 text-xs text-muted-foreground ${isNarrowViewport ? 'self-start' : 'max-w-80'}`}
            >
                <span className="font-medium text-foreground">Project:</span> {projectLabel}
            </div>
        </header>
    )
}
