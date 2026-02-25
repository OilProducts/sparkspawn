export type ViewMode = 'editor' | 'execution' | 'settings' | 'runs';

export interface AttractorState {
    viewMode: ViewMode;
    setViewMode: (mode: ViewMode) => void;
    activeFlow: string | null;
    setActiveFlow: (flow: string | null) => void;
    selectedNodeId: string | null;
    setSelectedNodeId: (id: string | null) => void;
}
