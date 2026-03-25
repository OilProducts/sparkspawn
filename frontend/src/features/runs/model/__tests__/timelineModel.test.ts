import {
  buildGroupedPendingInterviewGates,
  buildPendingInterviewGates,
  filterTimelineEvents,
  toTimelineEvent,
} from '@/features/runs/model/timelineModel'

describe('timelineModel', () => {
  it('summarizes completed failure outcomes without classifying them as runtime errors', () => {
    const event = toTimelineEvent({
      type: 'PipelineCompleted',
      node_id: 'done',
      outcome: 'failure',
      outcome_reason_message: 'Goal gate not satisfied',
    }, 3)

    expect(event).toMatchObject({
      type: 'PipelineCompleted',
      severity: 'warning',
      summary: 'Pipeline completed at done (failure: Goal gate not satisfied)',
    })
  })

  it('derives pending interview gates from live events and fallback question snapshots', () => {
    const timeoutEvent = toTimelineEvent({
      type: 'human_gate',
      node_id: 'review',
      prompt: 'Need approval?',
      question_type: 'YES_NO',
    }, 1)

    const pendingGates = buildPendingInterviewGates(
      [timeoutEvent].filter(Boolean),
      [
        {
          questionId: 'q-2',
          nodeId: 'review',
          prompt: 'Provide extra detail',
          questionType: 'FREEFORM',
          options: [],
        },
      ],
    )

    expect(pendingGates).toHaveLength(2)
    expect(pendingGates[0]).toMatchObject({
      nodeId: 'review',
      questionType: 'YES_NO',
      options: [
        { label: 'Yes', value: 'YES', key: 'Y', description: null },
        { label: 'No', value: 'NO', key: 'N', description: null },
      ],
    })
    expect(pendingGates[1]).toMatchObject({
      questionId: 'q-2',
      prompt: 'Provide extra detail',
    })

    const grouped = buildGroupedPendingInterviewGates(pendingGates)
    expect(grouped).toHaveLength(1)
    expect(grouped[0]?.heading).toBe('review')
  })

  it('filters timeline events by severity and node/stage text', () => {
    const events = [
      toTimelineEvent({ type: 'StageStarted', node_id: 'plan', index: 1 }, 1),
      toTimelineEvent({ type: 'StageFailed', node_id: 'apply', index: 2, error: 'boom' }, 2),
    ].filter(Boolean)

    const filtered = filterTimelineEvents(events, {
      timelineTypeFilter: 'all',
      timelineCategoryFilter: 'all',
      timelineSeverityFilter: 'error',
      timelineNodeStageFilter: 'apply',
    })

    expect(filtered).toHaveLength(1)
    expect(filtered[0]?.nodeId).toBe('apply')
  })
})
