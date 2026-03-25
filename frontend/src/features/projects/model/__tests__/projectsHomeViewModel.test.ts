import type { ProjectSessionState } from '@/store'

import { buildProjectsHomeViewModel } from '@/features/projects/model/projectsHomeViewModel'
import type { ConversationSnapshotResponse } from '@/lib/workspaceClient'

const snapshot: ConversationSnapshotResponse = {
  schema_version: 4,
  conversation_id: 'conversation-1',
  conversation_handle: 'thread-1',
  project_path: '/tmp/project-alpha',
  title: 'Conversation',
  created_at: '2026-03-24T18:00:00Z',
  updated_at: '2026-03-24T18:01:00Z',
  turns: [
    {
      id: 'turn-user',
      role: 'user',
      content: 'Start planning.',
      timestamp: '2026-03-24T18:00:00Z',
      kind: 'message',
      status: 'complete',
      artifact_id: null,
    },
    {
      id: 'turn-assistant',
      role: 'assistant',
      content: '',
      timestamp: '2026-03-24T18:00:10Z',
      kind: 'message',
      status: 'pending',
      artifact_id: null,
    },
  ],
  segments: [],
  event_log: [],
  spec_edit_proposals: [
    {
      id: 'proposal-1',
      created_at: '2026-03-24T18:00:20Z',
      summary: 'Adjust approval copy.',
      status: 'pending',
      changes: [],
      canonical_spec_edit_id: null,
      approved_at: null,
      git_branch: null,
      git_commit: null,
    },
  ],
  flow_run_requests: [
    {
      id: 'request-1',
      status: 'approved',
      created_at: '2026-03-24T18:00:30Z',
      updated_at: '2026-03-24T18:00:31Z',
      flow_name: 'implement-spec.dot',
      title: 'Run implement-spec',
      summary: 'Launch the implementation flow.',
      run_id: 'run-7',
      prompt: 'Launch it',
      launch_context: null,
      decision_reason: null,
      flow_source: 'implement-spec.dot',
      approved_at: '2026-03-24T18:00:31Z',
      rejected_at: null,
      launched_at: null,
      launch_error: null,
      launch_warning: null,
    },
  ],
  flow_launches: [
    {
      id: 'launch-1',
      status: 'launched',
      created_at: '2026-03-24T18:00:40Z',
      updated_at: '2026-03-24T18:00:41Z',
      flow_name: 'implement-spec.dot',
      title: 'Launch started',
      summary: 'Launch created a run.',
      run_id: 'run-7',
      flow_source: 'implement-spec.dot',
      launch_error: null,
      launched_at: '2026-03-24T18:00:41Z',
    },
  ],
  execution_cards: [
    {
      id: 'execution-1',
      status: 'draft',
      created_at: '2026-03-24T18:00:50Z',
      updated_at: '2026-03-24T18:00:51Z',
      title: 'Execution draft',
      summary: 'Draft execution plan.',
      plan_markdown: 'Plan body',
      approval_notes: null,
      review_notes: null,
      approved_at: null,
      rejected_at: null,
      source_workflow_run_id: null,
      canonical_plan_id: null,
    },
  ],
  execution_workflow: null,
}

const activeProjectScope: ProjectSessionState = {
  workingDir: '/tmp/project-alpha',
  conversationId: 'conversation-1',
  projectEventLog: [
    {
      message: 'Conversation resumed.',
      timestamp: '2026-03-24T18:01:00Z',
    },
  ],
  specId: null,
  specStatus: 'draft',
  specProvenance: null,
  planId: null,
  planStatus: 'draft',
  planProvenance: null,
}

describe('buildProjectsHomeViewModel', () => {
  it('derives conversation, artifact, and surface state for the home controller', () => {
    const viewModel = buildProjectsHomeViewModel({
      activeConversationId: 'conversation-1',
      activeConversationSnapshot: snapshot,
      activeProjectPath: '/tmp/project-alpha',
      activeProjectScope,
      conversationCache: {
        snapshotsByConversationId: {
          'conversation-1': snapshot,
        },
        summariesByProjectPath: {
          '/tmp/project-alpha': [
            {
              conversation_id: 'conversation-1',
              conversation_handle: 'thread-1',
              project_path: '/tmp/project-alpha',
              title: 'Conversation',
              created_at: '2026-03-24T18:00:00Z',
              updated_at: '2026-03-24T18:01:00Z',
              last_message_preview: 'Start planning.',
            },
          ],
        },
      },
      optimisticSend: {
        conversationId: 'conversation-1',
        createdAt: '2026-03-24T18:01:10Z',
        message: 'Continue',
      },
      projectGitMetadata: {
        '/tmp/project-alpha': {
          branch: 'main',
          commit: 'abc123',
        },
      },
    })

    expect(viewModel.activeProjectLabel).toBe('project-alpha')
    expect(viewModel.activeProjectGitMetadata).toEqual({
      branch: 'main',
      commit: 'abc123',
    })
    expect(viewModel.activeProjectConversationSummaries).toHaveLength(1)
    expect(viewModel.activeProjectEventLog).toEqual(activeProjectScope.projectEventLog)
    expect(viewModel.latestSpecEditProposalId).toBe('proposal-1')
    expect(viewModel.latestFlowRunRequestId).toBe('request-1')
    expect(viewModel.latestFlowLaunchId).toBe('launch-1')
    expect(viewModel.latestExecutionCardId).toBe('execution-1')
    expect(viewModel.activeSpecEditProposalsById.get('proposal-1')?.summary).toBe('Adjust approval copy.')
    expect(viewModel.activeFlowRunRequestsById.get('request-1')?.run_id).toBe('run-7')
    expect(viewModel.activeFlowLaunchesById.get('launch-1')?.status).toBe('launched')
    expect(viewModel.activeExecutionCardsById.get('execution-1')?.title).toBe('Execution draft')
    expect(viewModel.isChatInputDisabled).toBe(true)
    expect(viewModel.chatSendButtonLabel).toBe('Thinking...')
    expect(viewModel.hasRenderableConversationHistory).toBe(true)
    expect(viewModel.activeConversationHistory.at(-1)).toMatchObject({
      role: 'user',
      content: 'Continue',
    })
  })
})
