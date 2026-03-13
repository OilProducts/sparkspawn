import { useEffect, useState } from 'react'
import { pipelineEventsUrl } from '@/lib/attractorClient'
import { useStore } from '@/store'

interface RoutingDecision {
    id: string
    from: string
    to: string
    reason: string
}

interface RetryDecision {
    id: string
    node: string
    attempt: number
    delayMs: number
}

interface FailureDecision {
    id: string
    node: string
    error: string
    willRetry: boolean
}

const MAX_ITEMS = 6
function prependLimited<T extends { id: string }>(items: T[], next: T): T[] {
    const deduped = items.filter((item) => item.id !== next.id)
    return [next, ...deduped].slice(0, MAX_ITEMS)
}

function eventNodeId(data: Record<string, unknown>): string {
    const candidate = data.node_id ?? data.node ?? data.name
    return typeof candidate === 'string' ? candidate : ''
}

export function ExplainabilityPanel() {
    const viewMode = useStore((state) => state.viewMode)
    const selectedRunId = useStore((state) => state.selectedRunId)
    const [routingDecisions, setRoutingDecisions] = useState<RoutingDecision[]>([])
    const [retryDecisions, setRetryDecisions] = useState<RetryDecision[]>([])
    const [failureDecisions, setFailureDecisions] = useState<FailureDecision[]>([])

    useEffect(() => {
        if (viewMode !== 'execution' || !selectedRunId) {
            setRoutingDecisions([])
            setRetryDecisions([])
            setFailureDecisions([])
            return
        }

        setRoutingDecisions([])
        setRetryDecisions([])
        setFailureDecisions([])
        const stageOutcomes = new Map<string, string>()
        let previousStartedNode = ''
        let sequence = 0
        const source = new EventSource(pipelineEventsUrl(selectedRunId))

        source.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data) as Record<string, unknown>

                if (data.type === 'StageCompleted') {
                    const node = eventNodeId(data)
                    if (node) {
                        stageOutcomes.set(node, String(data.outcome || 'success'))
                    }
                }

                if (data.type === 'StageRetrying') {
                    const node = eventNodeId(data)
                    const attempt = Number(data.attempt || 0)
                    const delayMs = Number(data.delay || 0)
                    if (node) {
                        const id = `${node}-retry-${attempt}-${sequence++}`
                        setRetryDecisions((current) =>
                            prependLimited(current, { id, node, attempt, delayMs })
                        )
                    }
                }

                if (data.type === 'StageFailed') {
                    const node = eventNodeId(data)
                    const error = String(data.error || 'stage_failed')
                    const willRetry = Boolean(data.will_retry)
                    if (node) {
                        stageOutcomes.set(node, 'fail')
                        const id = `${node}-failure-${sequence++}`
                        setFailureDecisions((current) =>
                            prependLimited(current, { id, node, error, willRetry })
                        )
                    }
                }

                if (data.type === 'StageStarted') {
                    const node = eventNodeId(data)
                    if (previousStartedNode && node && previousStartedNode !== node) {
                        const priorOutcome = stageOutcomes.get(previousStartedNode) || 'unknown'
                        const id = `${previousStartedNode}->${node}-${sequence++}`
                        setRoutingDecisions((current) =>
                            prependLimited(current, {
                                id,
                                from: previousStartedNode,
                                to: node,
                                reason: `prior outcome: ${priorOutcome}`,
                            })
                        )
                    }
                    if (node) {
                        previousStartedNode = node
                    }
                }

                if (data.type === 'PipelineRestarted') {
                    const fromNode = typeof data.from_node === 'string' ? data.from_node : ''
                    const restartNode = typeof data.restart_node === 'string' ? data.restart_node : ''
                    if (fromNode && restartNode) {
                        const id = `${fromNode}->${restartNode}-restart-${sequence++}`
                        setRoutingDecisions((current) =>
                            prependLimited(current, {
                                id,
                                from: fromNode,
                                to: restartNode,
                                reason: 'loop restart',
                            })
                        )
                    }
                }
            } catch {
                // Ignore malformed events.
            }
        }

        return () => {
            source.close()
        }
    }, [selectedRunId, viewMode])

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
