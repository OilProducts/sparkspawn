import { resolveModelStylesheetPreview } from '@/lib/modelStylesheetPreview'
import { describe, expect, it } from 'vitest'

describe('modelStylesheetPreview', () => {
  it('accepts xhigh reasoning effort declarations', () => {
    const preview = resolveModelStylesheetPreview(
      '* { reasoning_effort: xhigh; }',
      [{ id: 'plan', shape: 'box' }],
      {},
    )

    expect(preview.nodePreview[0].effective.reasoning_effort).toEqual({
      value: 'xhigh',
      source: 'stylesheet',
    })
  })
})
