import { getModelSuggestions } from '@/lib/llmSuggestions'
import { describe, expect, it } from 'vitest'

describe('llm suggestions', () => {
  it('surfaces gpt-5.5 first for OpenAI model suggestions', () => {
    expect(getModelSuggestions('openai').slice(0, 3)).toEqual([
      'gpt-5.5',
      'gpt-5.4',
      'gpt-5.2',
    ])
  })
})
