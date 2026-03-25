import type { GraphvizErrorState } from '../model/shared'
import { Button, EmptyState, InlineNotice, Panel, PanelContent, PanelHeader, SectionHeader } from '@/ui'

interface RunGraphvizCardProps {
    isGraphvizLoading: boolean
    graphvizError: GraphvizErrorState | null
    graphvizViewerSrc: string | null
    runId: string
    onRefresh: () => void
}

export function RunGraphvizCard({
    isGraphvizLoading,
    graphvizError,
    graphvizViewerSrc,
    runId,
    onRefresh,
}: RunGraphvizCardProps) {
    return (
        <Panel data-testid="run-graphviz-panel">
            <PanelHeader>
                <SectionHeader
                    title="Graphviz Render"
                    description="Rendered pipeline graph captured for this run."
                    action={(
                        <Button
                            onClick={onRefresh}
                            data-testid="run-graphviz-refresh-button"
                            variant="outline"
                            size="xs"
                            className="h-7 text-[11px] text-muted-foreground hover:text-foreground"
                        >
                            {isGraphvizLoading ? 'Refreshing…' : 'Refresh'}
                        </Button>
                    )}
                />
            </PanelHeader>
            <PanelContent>
                <div data-testid="run-graphviz-viewer" className="rounded-md border border-border/80 bg-muted/30 p-3">
                    {isGraphvizLoading && (
                        <div data-testid="run-graphviz-viewer-loading" className="text-xs text-muted-foreground">
                            Loading graph visualization...
                        </div>
                    )}
                    {!isGraphvizLoading && graphvizError && (
                        <InlineNotice tone="error" className="space-y-1">
                            <div data-testid="run-graphviz-viewer-error">{graphvizError.message}</div>
                            <div data-testid="run-graphviz-viewer-error-help" className="text-xs text-destructive/90">
                                {graphvizError.help}
                            </div>
                        </InlineNotice>
                    )}
                    {!isGraphvizLoading && !graphvizError && graphvizViewerSrc && (
                        <img
                            data-testid="run-graphviz-viewer-image"
                            src={graphvizViewerSrc}
                            alt={`Graphviz render for run ${runId}`}
                            className="w-full rounded-md border border-border/70 bg-background"
                        />
                    )}
                    {!isGraphvizLoading && !graphvizError && !graphvizViewerSrc && (
                        <EmptyState description="No graph visualization is available for this run yet." />
                    )}
                </div>
            </PanelContent>
        </Panel>
    )
}
