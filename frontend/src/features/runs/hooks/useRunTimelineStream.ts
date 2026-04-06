import { useEffect, useMemo } from 'react'

import { pipelineEventsUrl } from '@/lib/attractorClient'
import { useStore } from '@/store'
import type { TimelineEventEntry } from '../model/shared'

import {
    TIMELINE_MAX_ITEMS,
    toTimelineEvent,
} from '../model/timelineModel'

type UseRunTimelineStreamArgs = {
    selectedRunTimelineId: string | null
    manageSync?: boolean
}

const DEFAULT_TIMELINE_SESSION = {
    timelineEvents: [] as TimelineEventEntry[],
    timelineError: null as string | null,
    isTimelineLive: false,
    timelineSequence: 0,
    timelineSeenServerSequences: {} as Record<string, true>,
}

const mergeTimelineEvent = (currentEvents: TimelineEventEntry[], timelineEvent: TimelineEventEntry) => {
    return [...currentEvents, timelineEvent]
        .sort((left, right) => right.sequence - left.sequence)
        .slice(0, TIMELINE_MAX_ITEMS)
}

export function useRunTimelineStream({
    selectedRunTimelineId,
    manageSync = true,
}: UseRunTimelineStreamArgs) {
    const runDetailSessionsByRunId = useStore((state) => state.runDetailSessionsByRunId)
    const updateRunDetailSession = useStore((state) => state.updateRunDetailSession)
    const session = useMemo(() => {
        if (!selectedRunTimelineId) {
            return DEFAULT_TIMELINE_SESSION
        }
        const current = runDetailSessionsByRunId[selectedRunTimelineId]
        return {
            ...DEFAULT_TIMELINE_SESSION,
            ...(current ?? {}),
        }
    }, [runDetailSessionsByRunId, selectedRunTimelineId])

    useEffect(() => {
        if (!manageSync || !selectedRunTimelineId) {
            return
        }

        const source = new EventSource(pipelineEventsUrl(selectedRunTimelineId))
        source.onopen = () => {
            updateRunDetailSession(selectedRunTimelineId, {
                timelineError: null,
                isTimelineLive: true,
            })
        }
        source.onmessage = (event) => {
            try {
                const payload = JSON.parse(event.data) as unknown
                const currentSession = useStore.getState().runDetailSessionsByRunId[selectedRunTimelineId]
                const currentSequence = currentSession?.timelineSequence ?? 0
                const currentSeenServerSequences = currentSession?.timelineSeenServerSequences ?? {}
                const currentEvents = currentSession?.timelineEvents ?? []
                const timelineEvent = toTimelineEvent(payload)
                if (!timelineEvent) {
                    return
                }
                const sequenceKey = String(timelineEvent.sequence)
                if (currentSeenServerSequences[sequenceKey]) {
                    return
                }
                updateRunDetailSession(selectedRunTimelineId, {
                    timelineError: null,
                    isTimelineLive: true,
                    timelineEvents: mergeTimelineEvent(currentEvents, timelineEvent),
                    timelineSequence: currentSequence + 1,
                    timelineSeenServerSequences: {
                        ...currentSeenServerSequences,
                        [sequenceKey]: true,
                    },
                })
            } catch {
                // Ignore malformed events.
            }
        }
        source.onerror = () => {
            updateRunDetailSession(selectedRunTimelineId, {
                isTimelineLive: false,
                timelineError: 'Event timeline stream unavailable. Reopen this run to retry.',
            })
        }

        return () => {
            source.close()
            updateRunDetailSession(selectedRunTimelineId, {
                isTimelineLive: false,
            })
        }
    }, [manageSync, selectedRunTimelineId, updateRunDetailSession])

    return {
        isTimelineLive: session.isTimelineLive,
        timelineDroppedCount: Math.max(0, session.timelineSequence - session.timelineEvents.length),
        timelineError: session.timelineError,
        timelineEvents: session.timelineEvents,
    }
}
