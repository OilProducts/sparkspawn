import { create } from 'zustand'
import { createEditorSlice } from './state/editorSlice'
import { createRunInspectorSlice } from './state/runInspectorSlice'
import type { AppState } from './state/store-types'
import { createWorkspaceSlice } from './state/workspaceSlice'

export * from './state/store-types'

export const useStore = create<AppState>()((...args) => ({
    ...createWorkspaceSlice(...args),
    ...createRunInspectorSlice(...args),
    ...createEditorSlice(...args),
}))
