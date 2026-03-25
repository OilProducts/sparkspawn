import { useCallback, useEffect, useState } from 'react'

import type { OptimisticSendState } from '../model/conversationState'

type UseProjectsHomeInteractionStateArgs = {
    activeConversationId: string | null
    activeProjectPath: string | null
    latestSpecEditProposalId: string | null
}

export function useProjectsHomeInteractionState({
    activeConversationId,
    activeProjectPath,
    latestSpecEditProposalId,
}: UseProjectsHomeInteractionStateArgs) {
    const [chatDraft, setChatDraft] = useState('')
    const [panelError, setPanelError] = useState<string | null>(null)
    const [optimisticSend, setOptimisticSend] = useState<OptimisticSendState | null>(null)
    const [pendingDeleteConversationId, setPendingDeleteConversationId] = useState<string | null>(null)
    const [expandedProposalChanges, setExpandedProposalChanges] = useState<Record<string, boolean>>({})
    const [expandedToolCalls, setExpandedToolCalls] = useState<Record<string, boolean>>({})
    const [expandedThinkingEntries, setExpandedThinkingEntries] = useState<Record<string, boolean>>({})

    useEffect(() => {
        setPanelError(null)
    }, [activeProjectPath])

    useEffect(() => {
        setExpandedProposalChanges({})
    }, [activeProjectPath, latestSpecEditProposalId])

    useEffect(() => {
        setExpandedToolCalls({})
    }, [activeConversationId, activeProjectPath])

    useEffect(() => {
        setExpandedThinkingEntries({})
    }, [activeConversationId, activeProjectPath])

    const toggleProposalChangeExpanded = useCallback((changeKey: string) => {
        setExpandedProposalChanges((current) => ({
            ...current,
            [changeKey]: !current[changeKey],
        }))
    }, [])

    const toggleToolCallExpanded = useCallback((toolCallId: string) => {
        setExpandedToolCalls((current) => ({
            ...current,
            [toolCallId]: !current[toolCallId],
        }))
    }, [])

    const toggleThinkingEntryExpanded = useCallback((entryId: string) => {
        setExpandedThinkingEntries((current) => ({
            ...current,
            [entryId]: !current[entryId],
        }))
    }, [])

    return {
        chatDraft,
        expandedProposalChanges,
        expandedThinkingEntries,
        expandedToolCalls,
        optimisticSend,
        panelError,
        pendingDeleteConversationId,
        setChatDraft,
        setOptimisticSend,
        setPanelError,
        setPendingDeleteConversationId,
        toggleProposalChangeExpanded,
        toggleThinkingEntryExpanded,
        toggleToolCallExpanded,
    }
}
