import { buildHydratedFlowGraph, layoutWithElk } from '@/features/workflow-canvas/flowCanvasShared'
import type { PreviewResponsePayload } from '@/lib/attractorClient'
import { generateDot } from '@/lib/dotUtils'
import { describe, expect, it } from 'vitest'

describe('flowCanvasShared', () => {
    it('hydrates mixed-shape graphs with shape-specific node types and dimensions', () => {
        const preview: PreviewResponsePayload = {
            status: 'ok',
            graph: {
                graph_attrs: {},
                nodes: [
                    { id: 'start', label: 'Start', shape: 'Mdiamond' },
                    { id: 'human', label: 'Human', shape: 'hexagon' },
                    { id: 'manager', label: 'Manager', shape: 'house' },
                    { id: 'custom', label: 'Custom', shape: 'ellipse' },
                ],
                edges: [],
            },
        }

        const hydrated = buildHydratedFlowGraph('shape-canvas.dot', preview, {
            llm_model: '',
            llm_provider: '',
            reasoning_effort: '',
        })

        expect(hydrated).not.toBeNull()
        expect(hydrated?.nodes).toMatchObject([
            {
                id: 'start',
                type: 'startNode',
                style: { width: 168, height: 96 },
                data: { shape: 'Mdiamond' },
            },
            {
                id: 'human',
                type: 'humanGateNode',
                style: { width: 228, height: 116 },
                data: { shape: 'hexagon' },
            },
            {
                id: 'manager',
                type: 'managerNode',
                style: { width: 236, height: 124 },
                data: { shape: 'house' },
            },
            {
                id: 'custom',
                type: 'taskNode',
                style: { width: 220, height: 110 },
                data: { shape: 'ellipse' },
            },
        ])
    })

    it('attaches ELK route geometry to hydrated edges during layout', async () => {
        const preview: PreviewResponsePayload = {
            status: 'ok',
            graph: {
                graph_attrs: {},
                nodes: [
                    { id: 'start', label: 'Start', shape: 'Mdiamond' },
                    { id: 'left', label: 'Left', shape: 'box' },
                    { id: 'right', label: 'Right', shape: 'box' },
                    { id: 'join', label: 'Join', shape: 'tripleoctagon' },
                ],
                edges: [
                    { from: 'start', to: 'left' },
                    { from: 'start', to: 'right' },
                    { from: 'left', to: 'join' },
                    { from: 'right', to: 'join' },
                ],
            },
        }

        const hydrated = buildHydratedFlowGraph('routing-canvas.dot', preview, {
            llm_model: '',
            llm_provider: '',
            reasoning_effort: '',
        })

        expect(hydrated).not.toBeNull()
        const layoutGraph = await layoutWithElk(hydrated?.nodes ?? [], hydrated?.edges ?? [])

        expect(layoutGraph.nodes).toHaveLength(4)
        expect(layoutGraph.edges).toHaveLength(4)
        expect(
            layoutGraph.edges.every((edge) => Array.isArray((edge.data as { layoutRoute?: unknown[] } | undefined)?.layoutRoute)),
        ).toBe(true)
        expect(
            layoutGraph.edges.every((edge) => {
                const data = edge.data as {
                    layoutSourceSide?: unknown
                    layoutTargetSide?: unknown
                } | undefined
                return typeof data?.layoutSourceSide === 'string' && typeof data?.layoutTargetSide === 'string'
            }),
        ).toBe(true)
    })

    it('does not materialize implicit node or graph defaults when saving after apply-to-nodes style edits', () => {
        const sourceDot = `
            digraph implement_spec_program {
                graph [label="Implement Spec Program"]
                start [shape=Mdiamond, label="Start"]
                extract_requirements [shape=box, label="Extract Requirements", prompt="Read spec"]
                start -> extract_requirements
            }
        `
        const preview: PreviewResponsePayload = {
            status: 'ok',
            graph: {
                graph_attrs: {
                    label: 'Implement Spec Program',
                },
                nodes: [
                    { id: 'start', label: 'Start', shape: 'Mdiamond' },
                    { id: 'extract_requirements', label: 'Extract Requirements', shape: 'box', prompt: 'Read spec' },
                ],
                edges: [
                    { from: 'start', to: 'extract_requirements' },
                ],
            },
        }

        const hydrated = buildHydratedFlowGraph('implement-spec.dot', preview, {
            llm_model: 'gpt-5.4',
            llm_provider: 'openai',
            reasoning_effort: 'high',
        }, sourceDot)

        expect(hydrated).not.toBeNull()
        expect(hydrated?.graphAttrs.ui_default_llm_model).toBeUndefined()
        expect(hydrated?.nodes[1]?.data).not.toHaveProperty('error_policy')
        expect(hydrated?.nodes[1]?.data).not.toHaveProperty('goal_gate')
        expect(hydrated?.nodes[1]?.data).not.toHaveProperty('auto_status')
        expect(hydrated?.nodes[1]?.data).not.toHaveProperty('allow_partial')

        const updatedNodes = (hydrated?.nodes ?? []).map((node) => ({
            ...node,
            data: {
                ...node.data,
                llm_model: 'gpt-5.4',
                llm_provider: 'openai',
                reasoning_effort: 'high',
            },
        }))
        const dot = generateDot('implement-spec.dot', updatedNodes, hydrated?.edges ?? [], hydrated?.graphAttrs ?? {})

        expect(dot).toContain('llm_model="gpt-5.4"')
        expect(dot).toContain('llm_provider=openai')
        expect(dot).toContain('reasoning_effort=high')
        expect(dot).not.toContain('error_policy=continue')
        expect(dot).not.toContain('goal_gate=false')
        expect(dot).not.toContain('auto_status=false')
        expect(dot).not.toContain('allow_partial=false')
        expect(dot).not.toContain('ui_default_llm_model=')
        expect(dot).not.toContain('ui_default_llm_provider=')
        expect(dot).not.toContain('ui_default_reasoning_effort=')
    })
})
