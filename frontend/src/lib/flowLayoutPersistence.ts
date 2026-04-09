import type { CanvasViewportState } from '@/state/store-types'

import type { EdgeRoute, RouteSide } from './edgeRouting'

export type FlowCanvasKind = 'editor-parent-only' | 'editor-expanded-preview' | 'execution' | 'runs'

export type SavedFlowLayoutEdgeV1 = {
    sourceSide: RouteSide
    targetSide: RouteSide
    sourceSlot: number
    targetSlot: number
    route: EdgeRoute
}

export type SavedFlowLayoutV1 = {
    version: 1
    topologyStamp: string
    nodePositions: Record<string, { x: number; y: number }>
    edgeLayouts: Record<string, SavedFlowLayoutEdgeV1>
    viewport?: CanvasViewportState | null
}

const SAVED_FLOW_LAYOUT_STORAGE_PREFIX = 'spark.saved_flow_layout.v1:'

function isRouteSide(value: unknown): value is RouteSide {
    return value === 'top' || value === 'right' || value === 'bottom' || value === 'left'
}

function isFiniteCoordinate(value: unknown): value is number {
    return Number.isFinite(value)
}

function normalizeEdgeRoute(route: unknown): EdgeRoute | null {
    if (!Array.isArray(route)) {
        return null
    }

    const normalized = route
        .map((point) => {
            if (
                !point
                || typeof point !== 'object'
                || !isFiniteCoordinate((point as { x?: unknown }).x)
                || !isFiniteCoordinate((point as { y?: unknown }).y)
            ) {
                return null
            }

            return {
                x: (point as { x: number }).x,
                y: (point as { y: number }).y,
            }
        })
        .filter((point): point is EdgeRoute[number] => point !== null)

    return normalized.length >= 2 ? normalized : null
}

function normalizeSavedLayout(raw: unknown): SavedFlowLayoutV1 | null {
    if (!raw || typeof raw !== 'object') {
        return null
    }

    const record = raw as Record<string, unknown>
    if (record.version !== 1 || typeof record.topologyStamp !== 'string') {
        return null
    }

    const nodePositionsRecord = record.nodePositions
    const edgeLayoutsRecord = record.edgeLayouts
    const viewportRecord = record.viewport

    const nodePositions = Object.fromEntries(
        Object.entries(nodePositionsRecord && typeof nodePositionsRecord === 'object'
            ? nodePositionsRecord as Record<string, unknown>
            : {})
            .flatMap(([nodeId, positionValue]) => {
                if (!positionValue || typeof positionValue !== 'object') {
                    return []
                }
                const position = positionValue as { x?: unknown; y?: unknown }
                if (!isFiniteCoordinate(position.x) || !isFiniteCoordinate(position.y)) {
                    return []
                }
                return [[nodeId, { x: position.x, y: position.y }] as const]
            }),
    )

    const edgeLayouts = Object.fromEntries(
        Object.entries(edgeLayoutsRecord && typeof edgeLayoutsRecord === 'object'
            ? edgeLayoutsRecord as Record<string, unknown>
            : {})
            .flatMap(([layoutKey, layoutValue]) => {
                if (!layoutValue || typeof layoutValue !== 'object') {
                    return []
                }
                const layout = layoutValue as Record<string, unknown>
                const route = normalizeEdgeRoute(layout.route)
                if (
                    !isRouteSide(layout.sourceSide)
                    || !isRouteSide(layout.targetSide)
                    || !isFiniteCoordinate(layout.sourceSlot)
                    || !isFiniteCoordinate(layout.targetSlot)
                    || !route
                ) {
                    return []
                }

                return [[layoutKey, {
                    sourceSide: layout.sourceSide,
                    targetSide: layout.targetSide,
                    sourceSlot: Math.max(0, Math.floor(layout.sourceSlot)),
                    targetSlot: Math.max(0, Math.floor(layout.targetSlot)),
                    route,
                } satisfies SavedFlowLayoutEdgeV1] as const]
            }),
    )

    const viewport = viewportRecord && typeof viewportRecord === 'object'
        && isFiniteCoordinate((viewportRecord as { x?: unknown }).x)
        && isFiniteCoordinate((viewportRecord as { y?: unknown }).y)
        && isFiniteCoordinate((viewportRecord as { zoom?: unknown }).zoom)
        ? {
            x: (viewportRecord as { x: number }).x,
            y: (viewportRecord as { y: number }).y,
            zoom: (viewportRecord as { zoom: number }).zoom,
        }
        : undefined

    return {
        version: 1,
        topologyStamp: record.topologyStamp,
        nodePositions,
        edgeLayouts,
        viewport,
    }
}

export function buildSavedFlowLayoutStorageKey(
    projectPath: string | null,
    flowName: string,
    canvasKind: FlowCanvasKind,
): string {
    const normalizedProjectPath = (projectPath ?? '__workspace__').trim() || '__workspace__'
    return `${SAVED_FLOW_LAYOUT_STORAGE_PREFIX}${normalizedProjectPath}:${flowName}:${canvasKind}`
}

export function loadSavedFlowLayout(
    projectPath: string | null,
    flowName: string,
    canvasKind: FlowCanvasKind,
): SavedFlowLayoutV1 | null {
    if (typeof window === 'undefined') {
        return null
    }

    try {
        const raw = window.localStorage.getItem(buildSavedFlowLayoutStorageKey(projectPath, flowName, canvasKind))
        if (!raw) {
            return null
        }
        return normalizeSavedLayout(JSON.parse(raw))
    } catch {
        return null
    }
}

export function saveSavedFlowLayout(
    projectPath: string | null,
    flowName: string,
    canvasKind: FlowCanvasKind,
    layout: SavedFlowLayoutV1,
): void {
    if (typeof window === 'undefined') {
        return
    }

    try {
        window.localStorage.setItem(
            buildSavedFlowLayoutStorageKey(projectPath, flowName, canvasKind),
            JSON.stringify(layout),
        )
    } catch {
        // Ignore storage failures.
    }
}

export function clearSavedFlowLayout(
    projectPath: string | null,
    flowName: string,
    canvasKind: FlowCanvasKind,
): void {
    if (typeof window === 'undefined') {
        return
    }

    try {
        window.localStorage.removeItem(buildSavedFlowLayoutStorageKey(projectPath, flowName, canvasKind))
    } catch {
        // Ignore storage failures.
    }
}
