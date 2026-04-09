import type { CSSProperties } from 'react'
import { BaseEdge, EdgeLabelRenderer, type EdgeProps } from '@xyflow/react'

import {
    buildRoundedPolylinePath,
    getRouteMidpoint,
    normalizeRoute,
    type EdgeRoute,
} from '@/lib/edgeRouting'
import { EDGE_RENDER_ROUTE_KEY } from '@/lib/flowLayout'
import { useStore as useAppStore } from '@/store'

import { useCanvasSessionMode } from './canvasSessionContext'
import { getDerivedPreviewMeta } from './derivedPreview'

const WARNING_STROKE = 'hsl(38 92% 50%)'

function readRenderRoute(value: unknown): EdgeRoute | null {
    if (!Array.isArray(value)) {
        return null
    }

    const route = value
        .map((point) => {
            if (
                !point
                || typeof point !== 'object'
                || !Number.isFinite((point as { x?: unknown }).x)
                || !Number.isFinite((point as { y?: unknown }).y)
            ) {
                return null
            }

            return {
                x: (point as { x: number }).x,
                y: (point as { y: number }).y,
            }
        })
        .filter((point): point is EdgeRoute[number] => point !== null)

    return route.length >= 2 ? route : null
}

function buildFallbackRoute(sourceX: number, sourceY: number, targetX: number, targetY: number): EdgeRoute {
    return normalizeRoute([
        { x: sourceX, y: sourceY },
        { x: targetX, y: targetY },
    ])
}

export function ValidationEdge({
    id,
    source,
    target,
    data,
    markerStart,
    markerEnd,
    style,
    selected,
    sourceX,
    sourceY,
    targetX,
    targetY,
}: EdgeProps) {
    const canvasMode = useCanvasSessionMode()
    const edgeDiagnostics = useAppStore((state) =>
        canvasMode === 'editor'
            ? state.edgeDiagnostics
            : canvasMode === 'runs'
                ? state.runEdgeDiagnostics
                : state.executionEdgeDiagnostics,
    )
    const diagnosticsForEdge = edgeDiagnostics[`${source}->${target}`] || []
    const hasError = diagnosticsForEdge.some((diag) => diag.severity === 'error')
    const hasWarning = diagnosticsForEdge.some((diag) => diag.severity === 'warning')
    const hasInfo = diagnosticsForEdge.some((diag) => diag.severity === 'info')
    const renderRoute = readRenderRoute((data as Record<string, unknown> | undefined)?.[EDGE_RENDER_ROUTE_KEY])
        ?? buildFallbackRoute(sourceX, sourceY, targetX, targetY)
    const edgePath = buildRoundedPolylinePath(renderRoute)
    const labelPoint = getRouteMidpoint(renderRoute)
    const derivedPreviewMeta = getDerivedPreviewMeta(data)
    const isDerivedChildEdge = derivedPreviewMeta?.kind === 'child-edge'
    const isDerivedLinkEdge = derivedPreviewMeta?.kind === 'child-link'

    const edgeStyle: CSSProperties = {
        strokeLinecap: 'round',
        strokeLinejoin: 'round',
        strokeWidth: 2,
        ...style,
    }

    if (hasError) {
        edgeStyle.stroke = 'hsl(var(--destructive))'
        edgeStyle.strokeWidth = selected ? 4 : 3
        edgeStyle.opacity = 1
    } else if (hasWarning) {
        edgeStyle.stroke = WARNING_STROKE
        edgeStyle.strokeWidth = selected ? 4 : 3
        edgeStyle.opacity = 0.95
    } else if (isDerivedLinkEdge) {
        edgeStyle.stroke = 'hsl(var(--muted-foreground) / 0.6)'
        edgeStyle.strokeDasharray = '6 6'
        edgeStyle.strokeWidth = 2
        edgeStyle.opacity = 0.8
    } else if (isDerivedChildEdge) {
        edgeStyle.stroke = 'hsl(var(--muted-foreground) / 0.45)'
        edgeStyle.strokeWidth = 2
        edgeStyle.opacity = 0.62
    } else if (selected) {
        edgeStyle.stroke = 'hsl(var(--primary))'
        edgeStyle.strokeWidth = 4
        edgeStyle.opacity = 1
    }

    if (selected) {
        const shadowColor = hasError
            ? 'hsl(var(--destructive) / 0.55)'
            : hasWarning
                ? 'hsl(38 92% 50% / 0.4)'
                : 'hsl(var(--primary) / 0.6)'
        edgeStyle.filter = `drop-shadow(0 0 7px ${shadowColor})`
    }

    const badgeClass = hasError
        ? 'bg-destructive/15 text-destructive'
        : hasWarning
            ? 'bg-amber-500/15 text-amber-800'
            : 'bg-sky-500/15 text-sky-700'

    return (
        <>
            <BaseEdge
                id={id}
                path={edgePath}
                markerStart={markerStart}
                markerEnd={markerEnd}
                style={edgeStyle}
                interactionWidth={16}
            />
            {diagnosticsForEdge.length > 0 && (
                <EdgeLabelRenderer>
                    <div
                        className="nodrag nopan"
                        style={{
                            transform: `translate(-50%, -50%) translate(${labelPoint.x}px, ${labelPoint.y}px)`,
                        }}
                    >
                        <div
                            data-testid="edge-diagnostic-badge"
                            className={`rounded-full border border-border bg-background/95 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${badgeClass}`}
                            title={diagnosticsForEdge.map((diag) => diag.message).join('\n')}
                        >
                            {diagnosticsForEdge.length} {hasError ? 'Error' : hasWarning ? 'Warn' : hasInfo ? 'Info' : 'Issue'}
                        </div>
                    </div>
                </EdgeLabelRenderer>
            )}
        </>
    )
}
