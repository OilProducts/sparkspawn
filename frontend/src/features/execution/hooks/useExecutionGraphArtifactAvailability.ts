import { useEffect, useState } from 'react'

import { ApiHttpError, fetchPipelineGraphValidated } from '@/lib/attractorClient'

type GraphArtifactAvailability = 'idle' | 'checking' | 'available' | 'missing' | 'error'

const ACTIVE_RUNTIME_STATUSES = new Set(['running', 'cancel_requested', 'abort_requested'])

export function useExecutionGraphArtifactAvailability(selectedRunId: string | null, runtimeStatus: string) {
    const [graphArtifactAvailability, setGraphArtifactAvailability] = useState<GraphArtifactAvailability>('idle')

    useEffect(() => {
        if (!selectedRunId) {
            setGraphArtifactAvailability('idle')
            return
        }

        let isCancelled = false
        const probeGraphArtifact = async () => {
            setGraphArtifactAvailability((current) => (current === 'available' ? current : 'checking'))
            try {
                if (isCancelled) {
                    return
                }
                await fetchPipelineGraphValidated(selectedRunId)
                setGraphArtifactAvailability('available')
            } catch (error) {
                if (error instanceof ApiHttpError && error.status === 404) {
                    setGraphArtifactAvailability('missing')
                    return
                }
                if (!isCancelled) {
                    setGraphArtifactAvailability('error')
                }
            }
        }

        void probeGraphArtifact()
        if (!ACTIVE_RUNTIME_STATUSES.has(runtimeStatus)) {
            return () => {
                isCancelled = true
            }
        }

        const interval = window.setInterval(() => {
            void probeGraphArtifact()
        }, 5000)

        return () => {
            isCancelled = true
            window.clearInterval(interval)
        }
    }, [runtimeStatus, selectedRunId])

    return graphArtifactAvailability
}
