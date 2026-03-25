import { GraphSettings } from '../GraphSettings'

export function GraphInspectorPanel() {
    return (
        <div data-testid="graph-inspector-panel" className="flex-1 overflow-y-auto px-5 pb-5 pt-3">
            <GraphSettings inline />
        </div>
    )
}
