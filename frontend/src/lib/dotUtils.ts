import type { Edge, Node } from '@xyflow/react'

import type { GraphAttrs } from '@/store'

import {
    buildCanonicalFlowModelFromEditorState,
    generateDotFromCanonicalFlowModel,
    sanitizeGraphId as canonicalSanitizeGraphId,
} from './canonicalFlowModel.js'

export function generateDot(
    flowName: string,
    nodes: Node[],
    edges: Edge[],
    graphAttrs: GraphAttrs = {},
): string {
    const canonicalModel = buildCanonicalFlowModelFromEditorState(flowName, {
        nodes,
        edges,
        graphAttrs,
    })
    return generateDotFromCanonicalFlowModel(flowName, canonicalModel)
}

export function sanitizeGraphId(flowName: string): string {
    return canonicalSanitizeGraphId(flowName)
}
