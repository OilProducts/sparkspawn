import type { ProjectSessionState } from '@/store'
import type { ConversationSnapshotResponse, ConversationSummaryResponse } from '@/lib/workspaceClient'

import type { OptimisticSendState } from './conversationState'
import { buildConversationTimelineEntries } from './conversationTimeline'
import type { ProjectGitMetadata } from './presentation'
import {
    EMPTY_PROJECT_GIT_METADATA,
    formatProjectListLabel,
    type ProjectConversationCacheState,
} from './projectsHomeState'
import type {
    ConversationTimelineEntry,
    ProjectExecutionCard,
    ProjectFlowLaunch,
    ProjectFlowRunRequest,
    ProjectSpecEditProposal,
} from './types'

type BuildProjectsHomeViewModelArgs = {
    activeConversationId: string | null
    activeConversationSnapshot: ConversationSnapshotResponse | null
    activeProjectPath: string | null
    activeProjectScope: ProjectSessionState | null
    conversationCache: ProjectConversationCacheState
    optimisticSend: OptimisticSendState | null
    projectGitMetadata: Record<string, ProjectGitMetadata>
}

export type ProjectsHomeViewModel = {
    activeConversationHistory: ConversationTimelineEntry[]
    activeExecutionCardsById: Map<string, ProjectExecutionCard>
    activeFlowLaunchesById: Map<string, ProjectFlowLaunch>
    activeFlowRunRequestsById: Map<string, ProjectFlowRunRequest>
    activeProjectConversationSummaries: ConversationSummaryResponse[]
    activeProjectEventLog: ProjectSessionState['projectEventLog']
    activeProjectGitMetadata: ProjectGitMetadata
    activeProjectLabel: string | null
    activeSpecEditProposalsById: Map<string, ProjectSpecEditProposal>
    chatSendButtonLabel: string
    hasActiveAssistantTurn: boolean
    hasRenderableConversationHistory: boolean
    isChatInputDisabled: boolean
    latestExecutionCardId: string | null
    latestFlowLaunchId: string | null
    latestFlowRunRequestId: string | null
    latestSpecEditProposalId: string | null
}

function buildIdMap<T extends { id: string }>(items: T[]) {
    return new Map(items.map((item) => [item.id, item]))
}

function getLatestArtifactId<T extends { id: string }>(items: T[]) {
    return items.length > 0 ? items[items.length - 1]?.id || null : null
}

export function buildProjectsHomeViewModel({
    activeConversationId,
    activeConversationSnapshot,
    activeProjectPath,
    activeProjectScope,
    conversationCache,
    optimisticSend,
    projectGitMetadata,
}: BuildProjectsHomeViewModelArgs): ProjectsHomeViewModel {
    const activeConversationHistory = buildConversationTimelineEntries(
        activeConversationSnapshot,
        optimisticSend && optimisticSend.conversationId === activeConversationId ? optimisticSend : null,
    )
    const activeSpecEditProposals = activeConversationSnapshot?.spec_edit_proposals || []
    const activeFlowRunRequests = activeConversationSnapshot?.flow_run_requests || []
    const activeFlowLaunches = activeConversationSnapshot?.flow_launches || []
    const activeExecutionCards = activeConversationSnapshot?.execution_cards || []
    const hasRenderableConversationHistory = activeConversationHistory.some((entry) => (
        entry.kind === 'spec_edit_proposal'
        || entry.kind === 'flow_run_request'
        || entry.kind === 'flow_launch'
        || entry.kind === 'execution_card'
        || entry.kind === 'tool_call'
        || entry.role === 'user'
        || entry.role === 'assistant'
    ))
    const hasActiveAssistantTurn = (activeConversationSnapshot?.turns || []).some((turn) => (
        turn.role === 'assistant' && (turn.status === 'pending' || turn.status === 'streaming')
    ))

    return {
        activeConversationHistory,
        activeExecutionCardsById: buildIdMap(activeExecutionCards),
        activeFlowLaunchesById: buildIdMap(activeFlowLaunches),
        activeFlowRunRequestsById: buildIdMap(activeFlowRunRequests),
        activeProjectConversationSummaries: activeProjectPath
            ? conversationCache.summariesByProjectPath[activeProjectPath] || []
            : [],
        activeProjectEventLog: activeProjectScope?.projectEventLog || [],
        activeProjectGitMetadata: activeProjectPath
            ? projectGitMetadata[activeProjectPath] || EMPTY_PROJECT_GIT_METADATA
            : EMPTY_PROJECT_GIT_METADATA,
        activeProjectLabel: activeProjectPath ? formatProjectListLabel(activeProjectPath) : null,
        activeSpecEditProposalsById: buildIdMap(activeSpecEditProposals),
        chatSendButtonLabel: hasActiveAssistantTurn ? 'Thinking...' : 'Send',
        hasActiveAssistantTurn,
        hasRenderableConversationHistory,
        isChatInputDisabled: hasActiveAssistantTurn,
        latestExecutionCardId: getLatestArtifactId(activeExecutionCards),
        latestFlowLaunchId: getLatestArtifactId(activeFlowLaunches),
        latestFlowRunRequestId: getLatestArtifactId(activeFlowRunRequests),
        latestSpecEditProposalId: getLatestArtifactId(activeSpecEditProposals),
    }
}
