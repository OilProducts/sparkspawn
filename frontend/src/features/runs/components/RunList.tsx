import { Eye, OctagonX } from 'lucide-react'
import { Button, EmptyState, Panel, PanelContent, PanelHeader, SectionHeader } from '@/ui'
import type { RunRecord } from '../model/shared'
import {
    RUN_HISTORY_GRID_TEMPLATE,
    STATUS_LABELS,
    STATUS_STYLES,
    formatDuration,
    formatOutcomeLabel,
    formatTimestamp,
} from '../model/shared'

interface RunListProps {
    activeProjectPath: string | null
    now: number
    onOpenRun: (run: RunRecord) => void
    onOpenRunArtifact: (run: RunRecord, artifactType: 'spec' | 'plan') => void
    onRequestCancel: (runId: string, currentStatus: string) => void
    runs: RunRecord[]
    selectedRunId: string | null
}

export function RunList({
    activeProjectPath,
    now,
    onOpenRun,
    onOpenRunArtifact,
    onRequestCancel,
    runs,
    selectedRunId,
}: RunListProps) {
    return (
        <Panel>
            <PanelHeader>
                <SectionHeader
                    title="Runs"
                    description={activeProjectPath ? 'Run history for the active project.' : 'Select a project to inspect its runs.'}
                />
            </PanelHeader>
            <PanelContent className="px-0">
                {runs.length === 0 ? (
                    <EmptyState
                        className="mx-4 mb-4"
                        description={activeProjectPath ? 'No runs for the active project yet.' : 'No runs yet.'}
                    />
                ) : (
                    <div className="overflow-x-auto">
                        <div className="min-w-[1320px]">
                            <div className={`grid ${RUN_HISTORY_GRID_TEMPLATE} gap-3 border-b bg-muted/20 px-4 py-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground`}>
                                <span className="min-w-0">Status</span>
                                <span className="min-w-0">Outcome</span>
                                <span className="min-w-0">Flow</span>
                                <span className="min-w-0">Started</span>
                                <span className="min-w-0">Ended</span>
                                <span className="min-w-0">Duration</span>
                                <span className="min-w-0">Tokens</span>
                                <span className="min-w-0 text-right">Actions</span>
                            </div>
                            <div className="divide-y">
                                {runs.map((run) => {
                                    const canCancel = run.status === 'running'
                                    const cancelActionLabel = canCancel ? 'Cancel' : (
                                        run.status === 'cancel_requested' || run.status === 'abort_requested'
                                            ? 'Canceling…'
                                            : run.status === 'canceled' || run.status === 'aborted'
                                                ? 'Canceled'
                                                : 'Cancel'
                                    )
                                    const cancelDisabledReason =
                                        run.status === 'cancel_requested' || run.status === 'abort_requested'
                                            ? 'Cancel already requested for this run.'
                                            : run.status === 'canceled' || run.status === 'aborted'
                                                ? 'This run is already canceled.'
                                                : 'Cancel is only available while the run is active.'

                                    return (
                                        <div
                                            key={run.run_id}
                                            className={`grid ${RUN_HISTORY_GRID_TEMPLATE} items-start gap-3 px-4 py-3 text-sm ${
                                                selectedRunId === run.run_id ? 'bg-muted/40' : ''
                                            }`}
                                        >
                                            <span
                                                className={`inline-flex h-6 min-w-0 items-center justify-center rounded-md px-2 text-[11px] font-semibold uppercase tracking-wide ${
                                                    STATUS_STYLES[run.status] || 'bg-muted text-muted-foreground'
                                                }`}
                                            >
                                                {STATUS_LABELS[run.status] || run.status}
                                            </span>
                                            <span
                                                className="min-w-0 truncate pt-1 text-xs text-muted-foreground"
                                                title={run.outcome_reason_message || run.outcome || undefined}
                                            >
                                                {formatOutcomeLabel(run.outcome)}
                                            </span>
                                            <div className="min-w-0 space-y-1">
                                                <div className="truncate font-medium text-foreground" title={run.flow_name || 'Untitled'}>
                                                    {run.flow_name || 'Untitled'}
                                                </div>
                                                <div className="truncate text-[11px] text-muted-foreground" title={`${run.model || 'default model'} · ${run.run_id}`}>
                                                    {run.model || 'default model'} · {run.run_id}
                                                </div>
                                                <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
                                                    {run.spec_id && (
                                                        <Button
                                                            type="button"
                                                            data-testid="run-history-row-spec-artifact-link"
                                                            onClick={() => onOpenRunArtifact(run, 'spec')}
                                                            variant="link"
                                                            size="xs"
                                                            className="h-auto truncate px-0 py-0 font-mono"
                                                            title={run.spec_id}
                                                        >
                                                            Spec {run.spec_id}
                                                        </Button>
                                                    )}
                                                    {run.plan_id && (
                                                        <Button
                                                            type="button"
                                                            data-testid="run-history-row-plan-artifact-link"
                                                            onClick={() => onOpenRunArtifact(run, 'plan')}
                                                            variant="link"
                                                            size="xs"
                                                            className="h-auto truncate px-0 py-0 font-mono"
                                                            title={run.plan_id}
                                                        >
                                                            Plan {run.plan_id}
                                                        </Button>
                                                    )}
                                                </div>
                                            </div>
                                            <span className="min-w-0 pt-1 text-xs text-muted-foreground">
                                                {formatTimestamp(run.started_at)}
                                            </span>
                                            <span className="min-w-0 pt-1 text-xs text-muted-foreground">
                                                {formatTimestamp(run.ended_at)}
                                            </span>
                                            <span className="min-w-0 pt-1 text-xs text-muted-foreground">
                                                {formatDuration(run.started_at, run.ended_at, run.status, now)}
                                            </span>
                                            <span className="min-w-0 pt-1 text-xs text-muted-foreground">
                                                {typeof run.token_usage === 'number' ? run.token_usage.toLocaleString() : '—'}
                                            </span>
                                            <div className="flex justify-end">
                                                <div className="inline-flex items-center gap-1 rounded-md border border-border/80 bg-background/90 p-1 shadow-sm">
                                                    <Button
                                                        onClick={() => onOpenRun(run)}
                                                        variant="outline"
                                                        size="xs"
                                                        className="h-7 gap-1.5 border-border bg-card text-[11px] text-muted-foreground hover:text-foreground"
                                                    >
                                                        <Eye className="h-3.5 w-3.5" />
                                                        Open
                                                    </Button>
                                                    <Button
                                                        onClick={() => onRequestCancel(run.run_id, run.status)}
                                                        disabled={!canCancel}
                                                        title={canCancel ? undefined : cancelDisabledReason}
                                                        size="xs"
                                                        className="h-7 gap-1.5 bg-destructive px-2 text-[11px] font-semibold text-destructive-foreground hover:bg-destructive/90"
                                                    >
                                                        <OctagonX className="h-3.5 w-3.5" />
                                                        {cancelActionLabel}
                                                    </Button>
                                                </div>
                                            </div>
                                        </div>
                                    )
                                })}
                            </div>
                        </div>
                    </div>
                )}
            </PanelContent>
        </Panel>
    )
}
