import { useEffect } from 'react'

import { fetchProjectRegistryValidated } from '@/lib/workspaceClient'

import { extractApiErrorMessage, toHydratedProjectRecord } from '../model/projectsHomeState'

type UseProjectRegistryBootstrapArgs = {
    hydrateProjectRegistry: (projects: ReturnType<typeof toHydratedProjectRecord>[]) => void
    enabled?: boolean
    onError?: (message: string | null) => void
}

export function useProjectRegistryBootstrap({
    hydrateProjectRegistry,
    enabled = true,
    onError,
}: UseProjectRegistryBootstrapArgs) {
    useEffect(() => {
        if (!enabled) {
            onError?.(null)
            return
        }

        let canceled = false

        const loadProjectRegistry = async () => {
            try {
                const projects = await fetchProjectRegistryValidated()
                if (!canceled) {
                    hydrateProjectRegistry(projects.map(toHydratedProjectRecord))
                    onError?.(null)
                }
            } catch (error) {
                if (canceled) {
                    return
                }
                const message = extractApiErrorMessage(error, 'Unable to load available projects.')
                if (onError) {
                    onError(message)
                    return
                }
                console.error(error)
            }
        }

        void loadProjectRegistry()
        return () => {
            canceled = true
        }
    }, [enabled, hydrateProjectRegistry, onError])
}
