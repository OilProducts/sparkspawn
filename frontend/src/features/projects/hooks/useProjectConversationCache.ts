import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from 'react'

import type {
    ConversationSegmentUpsertEventResponse,
    ConversationSnapshotResponse,
    ConversationSummaryResponse,
    ConversationTurnUpsertEventResponse,
} from '@/lib/workspaceClient'
import { fetchProjectConversationListValidated } from '@/lib/workspaceClient'
import type { ProjectGitMetadata } from '../model/presentation'
import {
    applyConversationSnapshotToCache,
    applyConversationStreamEventToCache,
    derivePlanStatusFromExecutionCard,
    EMPTY_PROJECT_CONVERSATION_CACHE_STATE,
    setProjectConversationSummaryList,
    type ConversationStreamEvent,
    type ProjectConversationCacheState,
} from '../model/projectsHomeState'
import { debugProjectChat, summarizeConversationTurnsForDebug } from '../model/projectChatDebug'

type PersistProjectState = (
    projectPath: string,
    patch: {
        last_accessed_at?: string | null
        active_conversation_id?: string | null
        is_favorite?: boolean | null
    },
) => Promise<void>

type UpdateProjectSessionState = (
    projectPath: string,
    patch: Record<string, unknown>,
) => void

type UseProjectConversationCacheArgs = {
    persistProjectState: PersistProjectState
    projectSessionsByPath: Record<string, { conversationId: string | null }>
    setProjectGitMetadata: Dispatch<SetStateAction<Record<string, ProjectGitMetadata>>>
    updateProjectSessionState: UpdateProjectSessionState
}

export function useProjectConversationCache({
    persistProjectState,
    projectSessionsByPath,
    setProjectGitMetadata,
    updateProjectSessionState,
}: UseProjectConversationCacheArgs) {
    const [conversationCache, setConversationCache] = useState<ProjectConversationCacheState>(
        EMPTY_PROJECT_CONVERSATION_CACHE_STATE,
    )
    const conversationCacheRef = useRef(conversationCache)
    const projectSessionsRef = useRef(projectSessionsByPath)

    useEffect(() => {
        conversationCacheRef.current = conversationCache
    }, [conversationCache])

    useEffect(() => {
        projectSessionsRef.current = projectSessionsByPath
    }, [projectSessionsByPath])

    const commitConversationCache = useCallback((
        next:
            | ProjectConversationCacheState
            | ((current: ProjectConversationCacheState) => ProjectConversationCacheState),
    ) => {
        const resolved = typeof next === 'function'
            ? next(conversationCacheRef.current)
            : next
        conversationCacheRef.current = resolved
        setConversationCache(resolved)
    }, [])

    const setConversationSummaryList = useCallback((
        projectPath: string,
        summaries: ConversationSummaryResponse[],
    ) => {
        commitConversationCache((current) => setProjectConversationSummaryList(current, projectPath, summaries))
    }, [commitConversationCache])

    const loadProjectConversationSummaries = async (projectPath: string) => {
        try {
            const summaries = await fetchProjectConversationListValidated(projectPath)
            setConversationSummaryList(projectPath, summaries)
            return summaries
        } catch {
            return conversationCacheRef.current.summariesByProjectPath[projectPath] || []
        }
    }

    const applyConversationSnapshot = (
        projectPath: string,
        snapshot: ConversationSnapshotResponse,
        source = 'unknown',
        options?: {
            forceWorkspaceSync?: boolean
        },
    ) => {
        const latestProjectScope = projectSessionsRef.current[projectPath]
        const shouldSyncActiveWorkspace = options?.forceWorkspaceSync === true
            || latestProjectScope?.conversationId === snapshot.conversation_id
        const { applied, cache, latestApprovedProposal, latestExecutionCard } = applyConversationSnapshotToCache(
            conversationCacheRef.current,
            projectPath,
            snapshot,
        )
        if (!applied) {
            debugProjectChat('skip stale conversation snapshot', {
                source,
                projectPath,
                conversationId: snapshot.conversation_id,
                snapshotUpdatedAt: snapshot.updated_at,
            })
            return
        }
        debugProjectChat('apply conversation snapshot', {
            source,
            projectPath,
            snapshotProjectPath: snapshot.project_path,
            conversationId: snapshot.conversation_id,
            shouldSyncActiveWorkspace,
            turnCount: snapshot.turns.length,
            turns: summarizeConversationTurnsForDebug(snapshot.turns),
        })
        commitConversationCache(cache)

        if (shouldSyncActiveWorkspace) {
            updateProjectSessionState(projectPath, {
                conversationId: snapshot.conversation_id,
                projectEventLog: snapshot.event_log.map((entry) => ({
                    message: entry.message,
                    timestamp: entry.timestamp,
                })),
                specId: latestApprovedProposal?.canonical_spec_edit_id ?? null,
                specStatus: latestApprovedProposal ? 'approved' : 'draft',
                specProvenance: latestApprovedProposal
                    ? {
                        source: 'spec-edit-proposal',
                        referenceId: latestApprovedProposal.id,
                        capturedAt: latestApprovedProposal.approved_at || latestApprovedProposal.created_at,
                        runId: null,
                        gitBranch: latestApprovedProposal.git_branch ?? null,
                        gitCommit: latestApprovedProposal.git_commit ?? null,
                    }
                    : null,
                planId: latestExecutionCard?.id ?? null,
                planStatus: derivePlanStatusFromExecutionCard(latestExecutionCard),
                planProvenance: latestExecutionCard
                    ? {
                        source: 'execution-card',
                        referenceId: latestExecutionCard.id,
                        capturedAt: latestExecutionCard.updated_at,
                        runId: latestExecutionCard.source_workflow_run_id,
                        gitBranch: latestApprovedProposal?.git_branch ?? null,
                        gitCommit: latestApprovedProposal?.git_commit ?? null,
                    }
                    : null,
            })
            if (latestProjectScope?.conversationId !== snapshot.conversation_id) {
                void persistProjectState(projectPath, {
                    active_conversation_id: snapshot.conversation_id,
                    last_accessed_at: new Date().toISOString(),
                })
            }
        }

        if (latestApprovedProposal?.git_branch || latestApprovedProposal?.git_commit) {
            setProjectGitMetadata((current) => ({
                ...current,
                [projectPath]: {
                    branch: latestApprovedProposal.git_branch ?? current[projectPath]?.branch ?? null,
                    commit: latestApprovedProposal.git_commit ?? current[projectPath]?.commit ?? null,
                },
            }))
        }
    }

    const applyConversationStreamEvent = (
        projectPath: string,
        event: ConversationTurnUpsertEventResponse | ConversationSegmentUpsertEventResponse,
        source = 'unknown',
    ) => {
        debugProjectChat('apply conversation stream event', {
            source,
            projectPath,
            eventType: event.type,
            conversationId: event.conversation_id,
        })
        const { cache, snapshot } = applyConversationStreamEventToCache(
            conversationCacheRef.current,
            projectPath,
            event as ConversationStreamEvent,
        )
        commitConversationCache(cache)
        if (snapshot) {
            debugProjectChat('apply merged stream snapshot', {
                source,
                projectPath,
                conversationId: snapshot.conversation_id,
                turnCount: snapshot.turns.length,
            })
        }
    }

    return {
        applyConversationSnapshot,
        applyConversationStreamEvent,
        commitConversationCache,
        conversationCache,
        conversationCacheRef,
        loadProjectConversationSummaries,
        setConversationSummaryList,
    }
}
