import { type StateCreator } from 'zustand'
import type { AppState, RunInspectorSlice } from './store-types'

export const createRunInspectorSlice: StateCreator<AppState, [], [], RunInspectorSlice> = (set) => ({
    executionFlow: null,
    setExecutionFlow: (flow) => set({ executionFlow: flow }),
    selectedRunId: null,
    setSelectedRunId: (id) => set({ selectedRunId: id }),
    logs: [],
    addLog: (entry) => set((state) => ({ logs: [...state.logs, entry] })),
    clearLogs: () => set({ logs: [] }),
    runtimeStatus: 'idle',
    setRuntimeStatus: (status) => set({ runtimeStatus: status }),
    nodeStatuses: {},
    setNodeStatus: (nodeId, status) =>
        set((state) => ({ nodeStatuses: { ...state.nodeStatuses, [nodeId]: status } })),
    resetNodeStatuses: () => set({ nodeStatuses: {} }),
    humanGate: null,
    setHumanGate: (gate) => set({ humanGate: gate }),
    clearHumanGate: () => set({ humanGate: null }),
})
