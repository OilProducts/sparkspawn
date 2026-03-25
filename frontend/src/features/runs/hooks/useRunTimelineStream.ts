import { useEffect, useState } from 'react'

import { pipelineEventsUrl } from '@/lib/attractorClient'

import type { TimelineEventEntry } from '../model/shared'
import {
    TIMELINE_MAX_ITEMS,
    toTimelineEvent,
} from '../model/timelineModel'

type UseRunTimelineStreamArgs = {
    selectedRunTimelineId: string | null
    viewMode: string
}

export function useRunTimelineStream({
    selectedRunTimelineId,
    viewMode,
}: UseRunTimelineStreamArgs) {
    const [timelineEvents, setTimelineEvents] = useState<TimelineEventEntry[]>([])
    const [timelineError, setTimelineError] = useState<string | null>(null)
    const [isTimelineLive, setIsTimelineLive] = useState(false)
    const [timelineSequence, setTimelineSequence] = useState(0)

    useEffect(() => {
        if (viewMode !== 'runs' || !selectedRunTimelineId) {
            setTimelineSequence(0)
            setTimelineEvents([])
            setTimelineError(null)
            setIsTimelineLive(false)
            return
        }

        setTimelineSequence(0)
        setTimelineEvents([])
        setTimelineError(null)
        setIsTimelineLive(false)

        const source = new EventSource(pipelineEventsUrl(selectedRunTimelineId))
        source.onopen = () => {
            setTimelineError(null)
            setIsTimelineLive(true)
        }
        source.onmessage = (event) => {
            try {
                const payload = JSON.parse(event.data) as unknown
                setTimelineSequence((current) => {
                    const timelineEvent = toTimelineEvent(payload, current)
                    if (!timelineEvent) {
                        return current
                    }
                    setTimelineEvents((timelineEntries) => [timelineEvent, ...timelineEntries].slice(0, TIMELINE_MAX_ITEMS))
                    return current + 1
                })
            } catch {
                // Ignore malformed events.
            }
        }
        source.onerror = () => {
            setIsTimelineLive(false)
            setTimelineError((current) => current || 'Event timeline stream unavailable. Reopen this run to retry.')
        }

        return () => {
            source.close()
            setIsTimelineLive(false)
        }
    }, [selectedRunTimelineId, viewMode])

    return {
        isTimelineLive,
        timelineDroppedCount: Math.max(0, timelineSequence - timelineEvents.length),
        timelineError,
        timelineEvents,
    }
}
