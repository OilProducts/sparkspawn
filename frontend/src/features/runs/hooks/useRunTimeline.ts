import { useCallback, useEffect, useMemo, useState } from 'react'
import { ApiHttpError, fetchPipelineAnswerValidated } from '@/lib/attractorClient'
import type {
    PendingInterviewGate,
    PendingQuestionSnapshot,
    TimelineEventCategory,
    TimelineSeverity,
} from '../model/shared'
import {
    buildGroupedPendingInterviewGates,
    buildGroupedTimelineEntries,
    buildPendingInterviewGates,
    buildRetryCorrelationEntityKeys,
    buildTimelineTypeOptions,
    filterAnsweredPendingInterviewGates,
    filterTimelineEvents,
    logUnexpectedRunError,
} from '../model/timelineModel'
import { useRunTimelineStream } from './useRunTimelineStream'

type UseRunTimelineArgs = {
    pendingQuestionSnapshots: PendingQuestionSnapshot[]
    selectedRunTimelineId: string | null
    viewMode: string
}

export function useRunTimeline({
    pendingQuestionSnapshots,
    selectedRunTimelineId,
    viewMode,
}: UseRunTimelineArgs) {
    const [timelineTypeFilter, setTimelineTypeFilter] = useState('all')
    const [timelineNodeStageFilter, setTimelineNodeStageFilter] = useState('')
    const [timelineCategoryFilter, setTimelineCategoryFilter] = useState<'all' | TimelineEventCategory>('all')
    const [timelineSeverityFilter, setTimelineSeverityFilter] = useState<'all' | TimelineSeverity>('all')
    const [pendingGateActionError, setPendingGateActionError] = useState<string | null>(null)
    const [submittingGateIds, setSubmittingGateIds] = useState<Record<string, boolean>>({})
    const [answeredGateIds, setAnsweredGateIds] = useState<Record<string, boolean>>({})
    const [freeformAnswersByGateId, setFreeformAnswersByGateId] = useState<Record<string, string>>({})
    const {
        isTimelineLive,
        timelineDroppedCount,
        timelineError,
        timelineEvents,
    } = useRunTimelineStream({
        selectedRunTimelineId,
        viewMode,
    })

    useEffect(() => {
        setPendingGateActionError(null)
        setSubmittingGateIds({})
        setAnsweredGateIds({})
        setFreeformAnswersByGateId({})
    }, [selectedRunTimelineId])

    useEffect(() => {
        if (viewMode !== 'runs' || !selectedRunTimelineId) {
            setTimelineTypeFilter('all')
            setTimelineNodeStageFilter('')
            setTimelineCategoryFilter('all')
            setTimelineSeverityFilter('all')
            return
        }
        setTimelineTypeFilter('all')
        setTimelineNodeStageFilter('')
        setTimelineCategoryFilter('all')
        setTimelineSeverityFilter('all')
    }, [selectedRunTimelineId, viewMode])

    const timelineTypeOptions = useMemo(
        () => buildTimelineTypeOptions(timelineEvents),
        [timelineEvents],
    )
    const filteredTimelineEvents = useMemo(() => {
        return filterTimelineEvents(timelineEvents, {
            timelineTypeFilter,
            timelineCategoryFilter,
            timelineSeverityFilter,
            timelineNodeStageFilter,
        })
    }, [timelineCategoryFilter, timelineEvents, timelineNodeStageFilter, timelineSeverityFilter, timelineTypeFilter])
    const retryCorrelationEntityKeys = useMemo(() => {
        return buildRetryCorrelationEntityKeys(timelineEvents)
    }, [timelineEvents])
    const groupedTimelineEntries = useMemo(() => {
        return buildGroupedTimelineEntries(filteredTimelineEvents, retryCorrelationEntityKeys)
    }, [filteredTimelineEvents, retryCorrelationEntityKeys])

    const pendingInterviewGates = useMemo(() => {
        return buildPendingInterviewGates(timelineEvents, pendingQuestionSnapshots)
    }, [pendingQuestionSnapshots, timelineEvents])
    const visiblePendingInterviewGates = useMemo(
        () => filterAnsweredPendingInterviewGates(pendingInterviewGates, answeredGateIds),
        [answeredGateIds, pendingInterviewGates],
    )
    const groupedPendingInterviewGates = useMemo(() => {
        return buildGroupedPendingInterviewGates(visiblePendingInterviewGates)
    }, [visiblePendingInterviewGates])

    const submitPendingGateAnswer = useCallback(async (gate: PendingInterviewGate, selectedValue: string) => {
        if (!selectedRunTimelineId || !gate.questionId || !selectedValue.trim()) {
            return
        }
        setPendingGateActionError(null)
        setSubmittingGateIds((previous) => ({
            ...previous,
            [gate.questionId!]: true,
        }))
        try {
            await fetchPipelineAnswerValidated(selectedRunTimelineId, gate.questionId, selectedValue)
            setAnsweredGateIds((previous) => ({
                ...previous,
                [gate.questionId!]: true,
            }))
            setFreeformAnswersByGateId((previous) => {
                const next = { ...previous }
                delete next[gate.questionId!]
                return next
            })
        } catch (err) {
            logUnexpectedRunError(err)
            if (err instanceof ApiHttpError) {
                const detailSuffix = err.detail ? `: ${err.detail}` : ''
                setPendingGateActionError(`Unable to submit answer (HTTP ${err.status})${detailSuffix}.`)
            } else {
                setPendingGateActionError('Unable to submit answer. Check connection/backend and retry.')
            }
        } finally {
            setSubmittingGateIds((previous) => {
                const next = { ...previous }
                delete next[gate.questionId!]
                return next
            })
        }
    }, [selectedRunTimelineId])

    return {
        filteredTimelineEvents,
        freeformAnswersByGateId,
        groupedPendingInterviewGates,
        groupedTimelineEntries,
        isTimelineLive,
        pendingGateActionError,
        setFreeformAnswersByGateId,
        setTimelineCategoryFilter,
        setTimelineNodeStageFilter,
        setTimelineSeverityFilter,
        setTimelineTypeFilter,
        submittingGateIds,
        submitPendingGateAnswer,
        timelineCategoryFilter,
        timelineDroppedCount,
        timelineError,
        timelineEvents,
        timelineNodeStageFilter,
        timelineSeverityFilter,
        timelineTypeFilter,
        timelineTypeOptions,
        visiblePendingInterviewGates,
    }
}
