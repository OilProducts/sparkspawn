import { useMemo } from 'react'
import { OctagonX } from 'lucide-react'
import { useStore } from '@/store'

const STATUS_LABELS: Record<string, string> = {
    running: 'Running',
    abort_requested: 'Canceling…',
    cancel_requested: 'Canceling…',
    aborted: 'Canceled',
    canceled: 'Canceled',
    failed: 'Failed',
    validation_error: 'Validation Error',
    success: 'Complete',
    idle: 'Idle',
}

const CANCEL_ACTION_LABELS: Record<string, string> = {
    running: 'Cancel',
    abort_requested: 'Canceling…',
    cancel_requested: 'Canceling…',
    aborted: 'Canceled',
    canceled: 'Canceled',
    failed: 'Cancel',
    validation_error: 'Cancel',
    success: 'Cancel',
    idle: 'Cancel',
}

const TRANSITION_HINTS: Record<string, string> = {
    abort_requested: 'Cancel requested. Waiting for active node to finish.',
    cancel_requested: 'Cancel requested. Waiting for active node to finish.',
    aborted: 'Run canceled.',
    canceled: 'Run canceled.',
}

export function ExecutionControls() {
    const viewMode = useStore((state) => state.viewMode)
    const runtimeStatus = useStore((state) => state.runtimeStatus)
    const setRuntimeStatus = useStore((state) => state.setRuntimeStatus)
    const selectedRunId = useStore((state) => state.selectedRunId)

    const canCancel = runtimeStatus === 'running'
    const statusLabel = useMemo(
        () => STATUS_LABELS[runtimeStatus] || runtimeStatus,
        [runtimeStatus]
    )
    const cancelActionLabel = CANCEL_ACTION_LABELS[runtimeStatus] || 'Cancel'
    const transitionHint = TRANSITION_HINTS[runtimeStatus] || null

    if (viewMode !== 'execution' || !selectedRunId) return null

    const requestCancel = async () => {
        if (!window.confirm('Cancel this run? It will stop after the active node finishes.')) {
            return
        }
        setRuntimeStatus('cancel_requested')
        try {
            const response = await fetch(`/pipelines/${encodeURIComponent(selectedRunId)}/cancel`, { method: 'POST' })
            if (!response.ok) {
                throw new Error(`cancel failed with HTTP ${response.status}`)
            }
        } catch (error) {
            console.error(error)
            setRuntimeStatus('running')
            window.alert('Failed to request cancel. Check backend logs for details.')
        }
    }

    return (
        <div className="absolute bottom-4 left-1/2 z-20 flex -translate-x-1/2 items-center gap-3 rounded-md border border-border bg-background/90 px-3 py-2 shadow-lg">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {statusLabel}
            </span>
            <div className="h-4 w-px bg-border" />
            {transitionHint && (
                <span className="text-xs text-muted-foreground">{transitionHint}</span>
            )}
            <button
                onClick={requestCancel}
                disabled={!canCancel}
                title={canCancel ? undefined : transitionHint || 'Cancel is only available while the run is active.'}
                className="inline-flex h-8 items-center gap-2 rounded-md bg-destructive px-2 text-xs font-semibold uppercase tracking-wide text-destructive-foreground transition-colors hover:bg-destructive/90 disabled:pointer-events-none disabled:opacity-50"
            >
                <OctagonX className="h-3.5 w-3.5" />
                {cancelActionLabel}
            </button>
        </div>
    )
}
