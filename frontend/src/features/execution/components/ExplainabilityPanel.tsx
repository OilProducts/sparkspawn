import { useStore } from '@/store'
import { useExecutionExplainability } from '../hooks/useExecutionExplainability'

export function ExplainabilityPanel() {
    const viewMode = useStore((state) => state.viewMode)
    const selectedRunId = useStore((state) => state.selectedRunId)
    const { failureDecisions, retryDecisions, routingDecisions } = useExecutionExplainability(viewMode, selectedRunId)

    if (viewMode !== 'execution' || !selectedRunId) return null

    return (
        <div className="border-b bg-muted/20 px-4 py-3">
            <div className="grid gap-3 xl:grid-cols-3">
                <section data-testid="routing-explainability-view" className="rounded-md border border-border bg-background/80 p-3">
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Routing Decisions</h3>
                    <ul className="mt-2 space-y-1 text-xs">
                        {routingDecisions.length === 0 ? (
                            <li className="text-muted-foreground">No routing decisions yet.</li>
                        ) : (
                            routingDecisions.map((decision) => (
                                <li key={decision.id} className="rounded border border-border/80 bg-muted/40 px-2 py-1">
                                    <span className="font-medium">{decision.from}</span> {'->'} <span className="font-medium">{decision.to}</span>
                                    <span className="ml-2 text-muted-foreground">({decision.reason})</span>
                                </li>
                            ))
                        )}
                    </ul>
                </section>

                <section data-testid="retry-explainability-view" className="rounded-md border border-border bg-background/80 p-3">
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Retry Decisions</h3>
                    <ul className="mt-2 space-y-1 text-xs">
                        {retryDecisions.length === 0 ? (
                            <li className="text-muted-foreground">No retry decisions yet.</li>
                        ) : (
                            retryDecisions.map((decision) => (
                                <li key={decision.id} className="rounded border border-border/80 bg-muted/40 px-2 py-1">
                                    <span className="font-medium">{decision.node}</span>
                                    <span className="ml-2 text-muted-foreground">
                                        attempt {decision.attempt}, delay {decision.delayMs}ms
                                    </span>
                                </li>
                            ))
                        )}
                    </ul>
                </section>

                <section data-testid="failure-explainability-view" className="rounded-md border border-border bg-background/80 p-3">
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Failure Decisions</h3>
                    <ul className="mt-2 space-y-1 text-xs">
                        {failureDecisions.length === 0 ? (
                            <li className="text-muted-foreground">No failure decisions yet.</li>
                        ) : (
                            failureDecisions.map((decision) => (
                                <li key={decision.id} className="rounded border border-border/80 bg-muted/40 px-2 py-1">
                                    <span className="font-medium">{decision.node}</span>
                                    <span className="ml-2 text-muted-foreground">{decision.error}</span>
                                    <span className="ml-2 text-muted-foreground">
                                        ({decision.willRetry ? 'retrying' : 'terminal'})
                                    </span>
                                </li>
                            ))
                        )}
                    </ul>
                </section>
            </div>
        </div>
    )
}
