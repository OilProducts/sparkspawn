import { useCallback } from 'react'

import { updateProjectStateValidated } from '@/lib/workspaceClient'

import { toHydratedProjectRecord } from '../model/projectsHomeState'

type UpsertProjectRegistryEntry = (project: ReturnType<typeof toHydratedProjectRecord>) => void

type PersistProjectStatePatch = {
  last_accessed_at?: string | null
  active_conversation_id?: string | null
  is_favorite?: boolean | null
}

export function usePersistProjectState(upsertProjectRegistryEntry: UpsertProjectRegistryEntry) {
  return useCallback(async (projectPath: string, patch: PersistProjectStatePatch) => {
    try {
      const project = await updateProjectStateValidated({
        project_path: projectPath,
        ...patch,
      })
      upsertProjectRegistryEntry(toHydratedProjectRecord(project))
    } catch {
      // Keep the UI responsive if the background state sync fails.
    }
  }, [upsertProjectRegistryEntry])
}
