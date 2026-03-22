import type { LaunchInputDefinition, LaunchInputType } from '@/lib/flowContracts'

const LAUNCH_INPUT_TYPE_OPTIONS: Array<{ value: LaunchInputType; label: string }> = [
    { value: 'string', label: 'String' },
    { value: 'string[]', label: 'String List' },
    { value: 'boolean', label: 'Boolean' },
    { value: 'number', label: 'Number' },
    { value: 'json', label: 'JSON' },
]

interface LaunchInputsEditorProps {
    entries: LaunchInputDefinition[]
    error: string | null
    onChange: (entries: LaunchInputDefinition[]) => void
}

export function LaunchInputsEditor({ entries, error, onChange }: LaunchInputsEditorProps) {
    const updateEntry = (index: number, patch: Partial<LaunchInputDefinition>) => {
        onChange(entries.map((entry, entryIndex) => (
            entryIndex === index ? { ...entry, ...patch } : entry
        )))
    }

    const removeEntry = (index: number) => {
        onChange(entries.filter((_, entryIndex) => entryIndex !== index))
    }

    const addEntry = () => {
        onChange([
            ...entries,
            {
                key: 'context.request.',
                label: '',
                type: 'string',
                description: '',
                required: false,
            },
        ])
    }

    return (
        <div
            data-testid="graph-launch-inputs-editor"
            className="space-y-3 rounded-md border border-border/80 bg-background/40 p-3"
        >
            <div className="space-y-1">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Launch Inputs
                </p>
                <p className="text-[11px] text-muted-foreground">
                    Define the `context.*` values Spark should collect before launching this flow.
                </p>
            </div>
            {entries.length === 0 ? (
                <div className="rounded-md border border-dashed border-border/80 bg-muted/10 px-3 py-2 text-[11px] text-muted-foreground">
                    No launch inputs declared yet.
                </div>
            ) : null}
            {entries.map((entry, index) => (
                <div
                    key={`launch-input-${index}`}
                    data-testid={`graph-launch-input-row-${index}`}
                    className="space-y-3 rounded-md border border-border/80 bg-background px-3 py-3"
                >
                    <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1">
                            <label className="text-xs font-medium text-foreground">Label</label>
                            <input
                                data-testid={`graph-launch-input-label-${index}`}
                                value={entry.label}
                                onChange={(event) => updateEntry(index, { label: event.target.value })}
                                className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                placeholder="Request Summary"
                            />
                        </div>
                        <div className="space-y-1">
                            <label className="text-xs font-medium text-foreground">Type</label>
                            <select
                                data-testid={`graph-launch-input-type-${index}`}
                                value={entry.type}
                                onChange={(event) => updateEntry(index, { type: event.target.value as LaunchInputType })}
                                className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                            >
                                {LAUNCH_INPUT_TYPE_OPTIONS.map((option) => (
                                    <option key={option.value} value={option.value}>
                                        {option.label}
                                    </option>
                                ))}
                            </select>
                        </div>
                    </div>
                    <div className="space-y-1">
                        <label className="text-xs font-medium text-foreground">Context Key</label>
                        <input
                            data-testid={`graph-launch-input-key-${index}`}
                            value={entry.key}
                            onChange={(event) => updateEntry(index, { key: event.target.value })}
                            className="h-8 w-full rounded-md border border-input bg-background px-2 font-mono text-xs shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                            placeholder="context.request.summary"
                        />
                    </div>
                    <div className="space-y-1">
                        <label className="text-xs font-medium text-foreground">Description</label>
                        <textarea
                            data-testid={`graph-launch-input-description-${index}`}
                            value={entry.description}
                            onChange={(event) => updateEntry(index, { description: event.target.value })}
                            rows={2}
                            className="min-h-16 w-full rounded-md border border-input bg-background px-2 py-1 text-xs shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                            placeholder="Short explanation shown in the launch form."
                        />
                    </div>
                    <div className="flex items-center justify-between gap-3">
                        <label className="inline-flex items-center gap-2 text-xs font-medium text-foreground">
                            <input
                                data-testid={`graph-launch-input-required-${index}`}
                                type="checkbox"
                                checked={entry.required}
                                onChange={(event) => updateEntry(index, { required: event.target.checked })}
                                className="h-4 w-4 rounded border border-input"
                            />
                            Required at launch
                        </label>
                        <button
                            type="button"
                            data-testid={`graph-launch-input-remove-${index}`}
                            onClick={() => removeEntry(index)}
                            className="rounded border border-border px-2 py-1 text-[11px] font-medium text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                        >
                            Remove
                        </button>
                    </div>
                </div>
            ))}
            <div className="flex items-center justify-between gap-3">
                <button
                    type="button"
                    data-testid="graph-launch-input-add"
                    onClick={addEntry}
                    className="h-8 rounded-md border border-border px-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                >
                    Add Launch Input
                </button>
                {error ? (
                    <p data-testid="graph-launch-inputs-error" className="text-[11px] text-destructive">
                        {error}
                    </p>
                ) : (
                    <p className="text-[11px] text-muted-foreground">
                        Keys must use the `context.*` namespace.
                    </p>
                )}
            </div>
        </div>
    )
}
