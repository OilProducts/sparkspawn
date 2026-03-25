import type {
    ConversationSummaryResponse,
    ConversationTurnResponse,
    ExecutionCardResponse,
    FlowLaunchResponse,
    FlowRunRequestResponse,
    SpecEditProposalResponse,
} from '@/lib/workspaceClient'

export type ProjectConversationSummary = ConversationSummaryResponse
export type ProjectExecutionCard = ExecutionCardResponse
export type ProjectFlowLaunch = FlowLaunchResponse
export type ProjectFlowRunRequest = FlowRunRequestResponse
export type ProjectSpecEditProposal = SpecEditProposalResponse
export type ConversationTurnStatus = ConversationTurnResponse['status']

export interface ConversationTimelineToolCall {
    id: string
    kind: 'command_execution' | 'file_change' | 'dynamic_tool'
    status: 'running' | 'completed' | 'failed'
    title: string
    command?: string | null
    output?: string | null
    filePaths: string[]
}

export type ConversationTimelineEntry =
    | {
        id: string
        kind: 'message'
        role: 'user' | 'assistant'
        content: string
        timestamp: string
        status: ConversationTurnStatus
        error?: string | null
        presentation?: 'default' | 'thinking'
    }
    | {
        id: string
        kind: 'tool_call'
        role: 'system'
        timestamp: string
        toolCall: ConversationTimelineToolCall
    }
    | {
        id: string
        kind: 'final_separator'
        role: 'system'
        timestamp: string
        label: string
    }
    | {
    id: string
    kind: 'spec_edit_proposal' | 'flow_run_request' | 'flow_launch' | 'execution_card'
    role: 'system'
    artifactId: string
    timestamp: string
}
