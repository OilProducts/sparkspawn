import {
  resolveEdgeFieldDiagnostics,
  resolveGraphFieldDiagnostics,
  resolveNodeFieldDiagnostics,
} from '@/lib/inspectorFieldDiagnostics'
import { getHandlerType, getNodeFieldVisibility } from '@/lib/nodeVisibility'
import { describe, expect, it } from 'vitest'

describe('Inspector and node authoring behavior', () => {
  it('resolves handler types and field visibility for manager-loop authoring', () => {
    expect(getHandlerType('house', '')).toBe('stack.manager_loop')
    expect(getHandlerType('box', 'wait.human')).toBe('wait.human')

    const managerVisibility = getNodeFieldVisibility('stack.manager_loop')
    expect(managerVisibility.showManagerOptions).toBe(true)
    expect(managerVisibility.showTypeOverride).toBe(true)
    expect(managerVisibility.showPrompt).toBe(false)
    expect(managerVisibility.showLlmSettings).toBe(false)

    const codergenVisibility = getNodeFieldVisibility('codergen')
    expect(codergenVisibility.showPrompt).toBe(true)
    expect(codergenVisibility.showLlmSettings).toBe(true)
    expect(codergenVisibility.showAdvanced).toBe(true)
  })

  it('maps node diagnostics to actionable inspector fields', () => {
    const nodeDiagnostics = resolveNodeFieldDiagnostics(
      [
        {
          rule_id: 'goal_gate_has_retry',
          severity: 'error',
          message: 'goal_gate requires retry_target or fallback_retry_target.',
          node_id: 'node_a',
        },
        {
          rule_id: 'retry_target_exists',
          severity: 'error',
          message: 'fallback_retry_target references missing node.',
          node_id: 'node_a',
        },
        {
          rule_id: 'prompt_on_llm_nodes',
          severity: 'warning',
          message: 'Prompt is recommended for llm nodes.',
          node_id: 'node_a',
        },
      ],
      'node_a',
    )

    expect(nodeDiagnostics.goal_gate).toHaveLength(1)
    expect(nodeDiagnostics.retry_target).toHaveLength(1)
    expect(nodeDiagnostics.fallback_retry_target).toHaveLength(2)
    expect(nodeDiagnostics.prompt).toHaveLength(1)
    expect(nodeDiagnostics.label).toHaveLength(1)
  })

  it('maps edge and graph diagnostics to condition/fidelity/stylesheet fields', () => {
    const diagnostics = [
      {
        rule_id: 'condition_syntax',
        severity: 'error' as const,
        message: 'Condition parser failed near token.',
        edge: ['start', 'review'] as [string, string],
      },
      {
        rule_id: 'fidelity_valid',
        severity: 'warning' as const,
        message: 'Edge fidelity value is not recognized.',
        edge: ['start', 'review'] as [string, string],
      },
      {
        rule_id: 'stylesheet_syntax',
        severity: 'error' as const,
        message: 'Invalid stylesheet selector syntax.',
      },
      {
        rule_id: 'fidelity_valid',
        severity: 'error' as const,
        message: 'Graph fidelity must be one of supported values.',
      },
    ]

    const edgeDiagnostics = resolveEdgeFieldDiagnostics(diagnostics, 'start', 'review')
    expect(edgeDiagnostics.condition).toHaveLength(1)
    expect(edgeDiagnostics.fidelity).toHaveLength(1)

    const graphDiagnostics = resolveGraphFieldDiagnostics(diagnostics)
    expect(graphDiagnostics.model_stylesheet).toHaveLength(1)
    expect(graphDiagnostics.default_fidelity).toHaveLength(1)
  })
})
