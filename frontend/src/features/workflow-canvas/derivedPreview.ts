import type { Edge, Node } from '@xyflow/react'

export const DERIVED_PREVIEW_DATA_KEY = '__derived_preview__'

export type DerivedPreviewNodeKind = 'child-cluster' | 'child-node'
export type DerivedPreviewEdgeKind = 'child-edge' | 'child-link' | 'layout-anchor'

export type DerivedPreviewMeta = {
    kind: DerivedPreviewNodeKind | DerivedPreviewEdgeKind
    managerNodeId: string
    originalNodeId?: string
    readOnly: boolean
}

function asRecord(value: unknown): Record<string, unknown> | null {
    if (!value || typeof value !== 'object') {
        return null
    }
    return value as Record<string, unknown>
}

export function attachDerivedPreviewMeta(
    data: Record<string, unknown> | undefined,
    meta: DerivedPreviewMeta,
): Record<string, unknown> {
    return {
        ...(data ?? {}),
        [DERIVED_PREVIEW_DATA_KEY]: meta,
    }
}

export function getDerivedPreviewMeta(value: unknown): DerivedPreviewMeta | null {
    const record = asRecord(value)
    if (!record) {
        return null
    }
    const metaRecord = asRecord(record[DERIVED_PREVIEW_DATA_KEY])
    if (!metaRecord) {
        return null
    }
    const kind = metaRecord.kind
    const managerNodeId = metaRecord.managerNodeId
    const originalNodeId = metaRecord.originalNodeId
    const readOnly = metaRecord.readOnly
    if (
        (kind !== 'child-cluster'
            && kind !== 'child-node'
            && kind !== 'child-edge'
            && kind !== 'child-link'
            && kind !== 'layout-anchor')
        || typeof managerNodeId !== 'string'
        || readOnly !== true
    ) {
        return null
    }
    return {
        kind,
        managerNodeId,
        originalNodeId: typeof originalNodeId === 'string' ? originalNodeId : undefined,
        readOnly: true,
    }
}

export function isDerivedPreviewNode(node: Node | { data?: unknown }): boolean {
    return getDerivedPreviewMeta(node.data)?.kind === 'child-cluster'
        || getDerivedPreviewMeta(node.data)?.kind === 'child-node'
}

export function isDerivedPreviewEdge(edge: Edge | { data?: unknown }): boolean {
    const kind = getDerivedPreviewMeta(edge.data)?.kind
    return kind === 'child-edge' || kind === 'child-link' || kind === 'layout-anchor'
}

export function filterAuthoredNodes(nodes: Node[]): Node[] {
    return nodes.filter((node) => !isDerivedPreviewNode(node))
}

export function filterAuthoredEdges(edges: Edge[]): Edge[] {
    return edges.filter((edge) => !isDerivedPreviewEdge(edge))
}
