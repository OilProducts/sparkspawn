import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { buildHydratedFlowGraph, layoutWithElk } from '@/features/workflow-canvas/flowCanvasShared'
import { filterAuthoredEdges, filterAuthoredNodes } from '@/features/workflow-canvas/derivedPreview'
import type { PreviewResponsePayload } from '@/lib/attractorClient'
import { generateDot } from '@/lib/dotUtils'
import { describe, expect, it } from 'vitest'

const repoRoot = resolve(process.cwd(), '..')
const previewFixtureCache = new Map<string, PreviewResponsePayload>()

function loadStarterFlowPreview(flowRelativePath: string, expandChildren: boolean): PreviewResponsePayload {
    const cacheKey = `${flowRelativePath}:${expandChildren ? 'expanded' : 'parent-only'}`
    const cached = previewFixtureCache.get(cacheKey)
    if (cached) {
        return cached
    }

    // Pull the real backend preview so layout regressions track the shipped starter flows.
    const payload = JSON.parse(execFileSync(
        'uv',
        [
            'run',
            'python',
            '-c',
            [
                'import json, os',
                'from pathlib import Path',
                'import attractor.api.server as server',
                'repo_root = Path(os.environ["SPARK_REPO_ROOT"])',
                'flow_path = repo_root / os.environ["SPARK_FLOW_RELATIVE_PATH"]',
                'payload = server._preview_payload_from_dot_source(',
                '    flow_path.read_text(encoding="utf-8"),',
                '    expand_children=os.environ.get("SPARK_EXPAND_CHILDREN") == "1",',
                '    flow_source_dir=flow_path.parent.resolve(),',
                ')',
                'print(json.dumps(payload))',
            ].join('\n'),
        ],
        {
            cwd: repoRoot,
            encoding: 'utf-8',
            env: {
                ...process.env,
                SPARK_REPO_ROOT: repoRoot,
                SPARK_FLOW_RELATIVE_PATH: flowRelativePath,
                SPARK_EXPAND_CHILDREN: expandChildren ? '1' : '0',
            },
        },
    )) as PreviewResponsePayload

    previewFixtureCache.set(cacheKey, payload)
    return payload
}

function summarizeLaidOutGraph(graph: Awaited<ReturnType<typeof layoutWithElk>>) {
    const round = (value: number) => Math.round(value * 100) / 100
    return {
        nodes: [...graph.nodes]
            .sort((left, right) => left.id.localeCompare(right.id))
            .map((node) => ({
                id: node.id,
                x: round(node.position.x),
                y: round(node.position.y),
            })),
        edges: [...graph.edges]
            .sort((left, right) => left.id.localeCompare(right.id))
            .map((edge) => ({
                id: edge.id,
                source: edge.source,
                target: edge.target,
                route: ((edge.data as { layoutRoute?: Array<{ x: number; y: number }> } | undefined)?.layoutRoute ?? [])
                    .map((point) => [round(point.x), round(point.y)]),
            })),
    }
}

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

    it('routes reciprocal back-edges onto a distinct detour lane', async () => {
        const preview: PreviewResponsePayload = {
            status: 'ok',
            graph: {
                graph_attrs: {},
                nodes: [
                    { id: 'implement', label: 'Implement', shape: 'box' },
                    { id: 'evaluate', label: 'Evaluate', shape: 'box' },
                ],
                edges: [
                    { from: 'implement', to: 'evaluate' },
                    { from: 'evaluate', to: 'implement', label: 'Fix' },
                ],
            },
        }

        const hydrated = buildHydratedFlowGraph('implement-from-plan.dot', preview, {
            llm_model: '',
            llm_provider: '',
            reasoning_effort: '',
        })

        expect(hydrated).not.toBeNull()
        const layoutGraph = await layoutWithElk(hydrated?.nodes ?? [], hydrated?.edges ?? [])
        const forwardEdge = layoutGraph.edges.find((edge) => edge.source === 'implement' && edge.target === 'evaluate')
        const backEdge = layoutGraph.edges.find((edge) => edge.source === 'evaluate' && edge.target === 'implement')

        expect(forwardEdge).toBeDefined()
        expect(backEdge).toBeDefined()

        const forwardRoute = (forwardEdge?.data as { layoutRoute?: Array<{ x: number; y: number }> } | undefined)?.layoutRoute ?? []
        const backRoute = (backEdge?.data as { layoutRoute?: Array<{ x: number; y: number }> } | undefined)?.layoutRoute ?? []

        expect(backRoute.length).toBeGreaterThanOrEqual(4)
        expect(backRoute).not.toEqual(forwardRoute)
        expect(Math.min(...backRoute.map((point) => point.x))).toBeLessThan(backRoute[0]?.x ?? Number.POSITIVE_INFINITY)
    })

    it('builds a namespaced one-level child preview cluster when expansion is enabled', () => {
        const preview: PreviewResponsePayload = {
            status: 'ok',
            graph: {
                graph_attrs: {},
                nodes: [
                    { id: 'start', label: 'Start', shape: 'Mdiamond' },
                    { id: 'manager', label: 'Manager', shape: 'house', type: 'stack.manager_loop' },
                ],
                edges: [
                    { from: 'start', to: 'manager' },
                ],
                child_previews: {
                    manager: {
                        flow_name: 'child-worker.dot',
                        flow_path: '/tmp/child-worker.dot',
                        flow_label: 'Child Worker',
                        read_only: true,
                        provenance: 'derived_child_preview',
                        graph: {
                            graph_attrs: {},
                            nodes: [
                                { id: 'child_start', label: 'Child Start', shape: 'Mdiamond' },
                                { id: 'nested_manager', label: 'Nested Manager', shape: 'house', type: 'stack.manager_loop' },
                            ],
                            edges: [
                                { from: 'child_start', to: 'nested_manager' },
                            ],
                            child_previews: {
                                nested_manager: {
                                    flow_name: 'grandchild.dot',
                                    flow_path: '/tmp/grandchild.dot',
                                    flow_label: 'Grandchild',
                                    graph: {
                                        graph_attrs: {},
                                        nodes: [
                                            { id: 'grandchild_start', label: 'Grandchild Start', shape: 'Mdiamond' },
                                        ],
                                        edges: [],
                                    },
                                },
                            },
                        },
                    },
                },
            },
        }

        const hydrated = buildHydratedFlowGraph('parent.dot', preview, {
            llm_model: '',
            llm_provider: '',
            reasoning_effort: '',
        }, undefined, {
            expandChildren: true,
        })

        expect(hydrated).not.toBeNull()
        expect(hydrated?.nodes.map((node) => node.id)).toEqual(expect.arrayContaining([
            'start',
            'manager',
            '__child_preview_cluster__manager',
            '__child_preview__manager__child_start',
            '__child_preview__manager__nested_manager',
        ]))
        expect(hydrated?.nodes.find((node) => node.id === '__child_preview__manager__child_start')?.selectable).toBe(false)
        expect(hydrated?.nodes.find((node) => node.id === '__child_preview_cluster__manager')?.data).toMatchObject({
            label: 'Child Flow Preview: Child Worker',
        })
        expect(hydrated?.nodes.some((node) => node.id.includes('grandchild'))).toBe(false)
        expect(hydrated?.edges.find((edge) => edge.id === 'e-manager-child-preview-link')).toMatchObject({
            source: 'manager',
            target: '__child_preview__manager__child_start',
        })
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

    it.each([
        {
            flowName: 'implement-spec.dot',
            flowRelativePath: 'src/spark/starter_flows/spec-implementation/implement-spec.dot',
            expandChildren: false,
            expectedDerivedNodeId: null,
        },
        {
            flowName: 'implement-spec.dot',
            flowRelativePath: 'src/spark/starter_flows/spec-implementation/implement-spec.dot',
            expandChildren: true,
            expectedDerivedNodeId: '__child_preview_cluster__run_milestone',
        },
        {
            flowName: 'implement-milestone.dot',
            flowRelativePath: 'src/spark/starter_flows/spec-implementation/implement-milestone.dot',
            expandChildren: false,
            expectedDerivedNodeId: null,
        },
        {
            flowName: 'implement-milestone.dot',
            flowRelativePath: 'src/spark/starter_flows/spec-implementation/implement-milestone.dot',
            expandChildren: true,
            expectedDerivedNodeId: null,
        },
    ])('keeps ELK layout stable for $flowName ($expandChildren)', async ({
        flowName,
        flowRelativePath,
        expandChildren,
        expectedDerivedNodeId,
    }) => {
        const sourceDot = readFileSync(resolve(repoRoot, flowRelativePath), 'utf-8')
        const preview = loadStarterFlowPreview(flowRelativePath, expandChildren)

        expect(preview.status).toBe('ok')
        const hydrated = buildHydratedFlowGraph(
            flowName,
            preview,
            {
                llm_model: '',
                llm_provider: '',
                reasoning_effort: '',
            },
            sourceDot,
            { expandChildren },
        )

        expect(hydrated).not.toBeNull()
        expect(
            hydrated?.nodes.every((node) =>
                Number.isFinite(node.position.x) && Number.isFinite(node.position.y)),
        ).toBe(true)
        if (expectedDerivedNodeId) {
            expect(hydrated?.nodes.some((node) => node.id === expectedDerivedNodeId)).toBe(true)
        } else {
            expect(hydrated?.nodes.some((node) => node.id.startsWith('__child_preview_'))).toBe(false)
        }

        const firstLayout = await layoutWithElk(hydrated?.nodes ?? [], hydrated?.edges ?? [])
        const secondLayout = await layoutWithElk(hydrated?.nodes ?? [], hydrated?.edges ?? [])

        expect(
            firstLayout.nodes.every((node) =>
                Number.isFinite(node.position.x) && Number.isFinite(node.position.y)),
        ).toBe(true)
        expect(
            firstLayout.edges.every((edge) =>
                Array.isArray((edge.data as { layoutRoute?: unknown[] } | undefined)?.layoutRoute)),
        ).toBe(true)
        expect(summarizeLaidOutGraph(secondLayout)).toEqual(summarizeLaidOutGraph(firstLayout))
    })

    it('filters derived child preview nodes and edges out of DOT serialization', () => {
        const preview: PreviewResponsePayload = {
            status: 'ok',
            graph: {
                graph_attrs: {},
                nodes: [
                    { id: 'manager', label: 'Manager', shape: 'house', type: 'stack.manager_loop' },
                ],
                edges: [],
                child_previews: {
                    manager: {
                        flow_name: 'child.dot',
                        flow_path: '/tmp/child.dot',
                        flow_label: 'Child',
                        graph: {
                            graph_attrs: {},
                            nodes: [
                                { id: 'child_task', label: 'Child Task', shape: 'box' },
                            ],
                            edges: [],
                        },
                    },
                },
            },
        }

        const hydrated = buildHydratedFlowGraph('parent.dot', preview, {
            llm_model: '',
            llm_provider: '',
            reasoning_effort: '',
        }, undefined, {
            expandChildren: true,
        })

        expect(hydrated).not.toBeNull()
        const dot = generateDot(
            'parent.dot',
            filterAuthoredNodes(hydrated?.nodes ?? []),
            filterAuthoredEdges(hydrated?.edges ?? []),
            hydrated?.graphAttrs ?? {},
        )

        expect(dot).toContain('manager')
        expect(dot).not.toContain('__child_preview__manager__child_task')
        expect(dot).not.toContain('Child Flow Preview')
    })
})
