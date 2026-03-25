import type {
    CheckpointErrorState,
    CheckpointResponse,
} from '../model/shared'
import { Button, InlineNotice, Panel, PanelContent, PanelHeader, SectionHeader } from '@/ui'

interface RunCheckpointCardProps {
    isLoading: boolean
    checkpointError: CheckpointErrorState | null
    checkpointData: CheckpointResponse['checkpoint'] | null
    checkpointCurrentNode: string
    checkpointCompletedNodes: string
    checkpointRetryCounters: string
    onRefresh: () => void
}

export function RunCheckpointCard({
    isLoading,
    checkpointError,
    checkpointData,
    checkpointCurrentNode,
    checkpointCompletedNodes,
    checkpointRetryCounters,
    onRefresh,
}: RunCheckpointCardProps) {
    return (
        <Panel data-testid="run-checkpoint-panel">
            <PanelHeader>
                <SectionHeader
                    title="Checkpoint"
                    description="Latest persisted runtime position and retry counters."
                    action={(
                        <Button
                            onClick={onRefresh}
                            data-testid="run-checkpoint-refresh-button"
                            variant="outline"
                            size="xs"
                            className="h-7 text-[11px] text-muted-foreground hover:text-foreground"
                        >
                            {isLoading ? 'Refreshing…' : 'Refresh'}
                        </Button>
                    )}
                />
            </PanelHeader>
            <PanelContent className="space-y-3">
            {checkpointError && (
                <InlineNotice tone="error" className="space-y-1">
                    <div data-testid="run-checkpoint-error">{checkpointError.message}</div>
                    <div data-testid="run-checkpoint-error-help" className="text-xs text-destructive/90">
                        {checkpointError.help}
                    </div>
                </InlineNotice>
            )}
            {!checkpointError && checkpointData && (
                <div className="space-y-3">
                    <div className="grid gap-x-6 gap-y-2 text-sm md:grid-cols-3">
                        <div data-testid="run-checkpoint-current-node">
                            <span className="font-medium">Current Node:</span> {checkpointCurrentNode}
                        </div>
                        <div data-testid="run-checkpoint-completed-nodes">
                            <span className="font-medium">Completed Nodes:</span> {checkpointCompletedNodes}
                        </div>
                        <div data-testid="run-checkpoint-retry-counters">
                            <span className="font-medium">Retry Counters:</span> {checkpointRetryCounters}
                        </div>
                    </div>
                    <pre
                        data-testid="run-checkpoint-payload"
                        className="max-h-60 overflow-auto rounded-md border border-border/80 bg-muted/40 p-3 text-xs text-foreground"
                    >
                        {JSON.stringify(checkpointData, null, 2)}
                    </pre>
                </div>
            )}
            </PanelContent>
        </Panel>
    )
}
