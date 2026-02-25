import { useMemo } from 'react'
import { Pause, OctagonX } from 'lucide-react'
import { useStore } from '@/store'

const STATUS_LABELS: Record<string, string> = {
    running: 'Running',
    paused: 'Paused',
    pause_requested: 'Pausing…',
    abort_requested: 'Aborting…',
    aborted: 'Aborted',
    failed: 'Failed',
    validation_error: 'Validation Error',
    success: 'Complete',
    idle: 'Idle',
}

export function ExecutionControls() {
    const viewMode = useStore((state) => state.viewMode)
    const runtimeStatus = useStore((state) => state.runtimeStatus)

    const canPause = runtimeStatus === 'running'
    const canAbort = runtimeStatus === 'running' || runtimeStatus === 'pause_requested'
    const statusLabel = useMemo(
        () => STATUS_LABELS[runtimeStatus] || runtimeStatus,
        [runtimeStatus]
    )

    if (viewMode !== 'execution') return null

    const requestPause = async () => {
        try {
            await fetch('/pause', { method: 'POST' })
        } catch (error) {
            console.error(error)
            window.alert('Failed to request pause. Check backend logs for details.')
        }
    }

    const requestAbort = async () => {
        if (!window.confirm('Abort the current run? This will stop after the active node finishes.')) {
            return
        }
        try {
            await fetch('/abort', { method: 'POST' })
        } catch (error) {
            console.error(error)
            window.alert('Failed to request abort. Check backend logs for details.')
        }
    }

    return (
        <div className="absolute bottom-4 left-1/2 z-20 flex -translate-x-1/2 items-center gap-3 rounded-md border border-border bg-background/90 px-3 py-2 shadow-lg">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {statusLabel}
            </span>
            <div className="h-4 w-px bg-border" />
            <button
                onClick={requestPause}
                disabled={!canPause}
                className="inline-flex h-8 items-center gap-2 rounded-md border border-border bg-background px-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground transition-colors hover:text-foreground disabled:pointer-events-none disabled:opacity-50"
            >
                <Pause className="h-3.5 w-3.5" />
                Pause
            </button>
            <button
                onClick={requestAbort}
                disabled={!canAbort}
                className="inline-flex h-8 items-center gap-2 rounded-md bg-destructive px-2 text-xs font-semibold uppercase tracking-wide text-destructive-foreground transition-colors hover:bg-destructive/90 disabled:pointer-events-none disabled:opacity-50"
            >
                <OctagonX className="h-3.5 w-3.5" />
                Abort
            </button>
        </div>
    )
}
