import { Eye, OctagonX } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button, EmptyState, Panel, PanelContent, PanelHeader, SectionHeader } from '@/ui'
import type { RunRecord } from '../model/shared'
import {
    STATUS_LABELS,
    STATUS_STYLES,
    formatDuration,
    formatOutcomeLabel,
    formatTimestamp,
} from '../model/shared'

interface RunListProps {
    activeProjectPath: string | null
    scopeMode: 'active' | 'all'
    now: number
    onOpenRun: (run: RunRecord) => void
    onOpenRunArtifact: (run: RunRecord, artifactType: 'spec' | 'plan') => void
    onRequestCancel: (runId: string, currentStatus: string) => void
    runs: RunRecord[]
    selectedRunId: string | null
}

export function RunList({
    activeProjectPath,
    scopeMode,
    now,
    onOpenRun,
    onOpenRunArtifact,
    onRequestCancel,
    runs,
    selectedRunId,
}: RunListProps) {
    return (
        <Panel data-testid="run-list-panel" className="self-start">
            <PanelHeader>
                <SectionHeader
                    title="Runs"
                    description={scopeMode === 'all'
                        ? 'Run history across all projects.'
                        : activeProjectPath
                            ? 'Run history for the active project.'
                            : 'Choose an active project or switch to all projects.'}
                />
            </PanelHeader>
            <PanelContent className="px-0">
                {runs.length === 0 ? (
                    <EmptyState
                        className="mx-4 mb-4"
                        description={scopeMode === 'all'
                            ? 'No runs yet.'
                            : activeProjectPath
                                ? 'No runs for the active project yet.'
                                : 'Choose an active project or switch to all projects.'}
                    />
                ) : (
                    <div
                        data-testid="run-list-scroll-region"
                        className="max-h-[28rem] overflow-y-auto px-4 pb-4"
                    >
                        <div className="space-y-3">
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
                                    <article
                                        key={run.run_id}
                                        data-testid="run-history-row"
                                        className={cn(
                                            'rounded-lg border border-border/80 bg-card/80 p-3 shadow-sm',
                                            selectedRunId === run.run_id && 'border-primary/50 bg-muted/30 ring-1 ring-primary/20',
                                        )}
                                    >
                                        <div className="space-y-3">
                                            <div className="space-y-2">
                                                <div className="flex flex-wrap items-center gap-2">
                                                    <span
                                                        className={`inline-flex h-6 items-center justify-center rounded-md px-2 text-[11px] font-semibold uppercase tracking-wide ${
                                                            STATUS_STYLES[run.status] || 'bg-muted text-muted-foreground'
                                                        }`}
                                                    >
                                                        {STATUS_LABELS[run.status] || run.status}
                                                    </span>
                                                    <span
                                                        className="text-xs text-muted-foreground"
                                                        title={run.outcome_reason_message || run.outcome || undefined}
                                                    >
                                                        {formatOutcomeLabel(run.outcome)}
                                                    </span>
                                                </div>
                                                <div className="space-y-1">
                                                    <div className="truncate font-medium text-foreground" title={run.flow_name || 'Untitled'}>
                                                        {run.flow_name || 'Untitled'}
                                                    </div>
                                                    <div className="truncate font-mono text-[11px] text-muted-foreground" title={run.run_id}>
                                                        {run.run_id}
                                                    </div>
                                                    <div className="truncate text-[11px] text-muted-foreground" title={run.model || 'default model'}>
                                                        {run.model || 'default model'}
                                                    </div>
                                                    {scopeMode === 'all' && run.project_path && (
                                                        <div className="truncate text-[11px] text-muted-foreground" title={run.project_path}>
                                                            {run.project_path}
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                            <dl className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
                                                <div className="min-w-0">
                                                    <dt className="font-medium text-foreground">Started</dt>
                                                    <dd className="truncate">{formatTimestamp(run.started_at)}</dd>
                                                </div>
                                                <div className="min-w-0">
                                                    <dt className="font-medium text-foreground">Ended</dt>
                                                    <dd className="truncate">{formatTimestamp(run.ended_at)}</dd>
                                                </div>
                                                <div className="min-w-0">
                                                    <dt className="font-medium text-foreground">Duration</dt>
                                                    <dd>{formatDuration(run.started_at, run.ended_at, run.status, now)}</dd>
                                                </div>
                                                <div className="min-w-0">
                                                    <dt className="font-medium text-foreground">Tokens</dt>
                                                    <dd>{typeof run.token_usage === 'number' ? run.token_usage.toLocaleString() : '—'}</dd>
                                                </div>
                                            </dl>
                                            <div className="flex flex-wrap items-center justify-between gap-3">
                                                <div className="flex min-w-0 flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
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
                                                <div className="flex shrink-0 flex-wrap items-center gap-2">
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
                                    </article>
                                )
                            })}
                        </div>
                    </div>
                )}
            </PanelContent>
        </Panel>
    )
}
