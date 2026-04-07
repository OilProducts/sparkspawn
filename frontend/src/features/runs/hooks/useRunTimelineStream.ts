import { useMemo } from 'react'

import { useStore } from '@/store'
import type { TimelineEventEntry } from '../model/shared'

type UseRunTimelineStreamArgs = {
    selectedRunTimelineId: string | null
}

const DEFAULT_TIMELINE_SESSION = {
    timelineEvents: [] as TimelineEventEntry[],
    timelineError: null as string | null,
    isTimelineLive: false,
    timelineSequence: 0,
}

export function useRunTimelineStream({
    selectedRunTimelineId,
}: UseRunTimelineStreamArgs) {
    const runDetailSessionsByRunId = useStore((state) => state.runDetailSessionsByRunId)
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

    return {
        isTimelineLive: session.isTimelineLive,
        timelineDroppedCount: Math.max(0, session.timelineSequence - session.timelineEvents.length),
        timelineError: session.timelineError,
        timelineEvents: session.timelineEvents,
    }
}
