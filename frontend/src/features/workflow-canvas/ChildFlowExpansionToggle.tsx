import { Button } from '@/ui'

export function ChildFlowExpansionToggle({
    expanded,
    onChange,
    disabled = false,
    testId,
}: {
    expanded: boolean
    onChange: (expanded: boolean) => void
    disabled?: boolean
    testId?: string
}) {
    return (
        <div
            data-testid={testId}
            className="flex rounded-md border border-border bg-background/90 p-1 shadow-sm"
        >
            <Button
                type="button"
                size="sm"
                variant={expanded ? 'ghost' : 'default'}
                disabled={disabled}
                className={`px-3 ${expanded ? 'text-muted-foreground hover:text-foreground' : ''}`}
                onClick={() => onChange(false)}
            >
                Parent Only
            </Button>
            <Button
                type="button"
                size="sm"
                variant={expanded ? 'default' : 'ghost'}
                disabled={disabled}
                className={`px-3 ${expanded ? '' : 'text-muted-foreground hover:text-foreground'}`}
                onClick={() => onChange(true)}
            >
                Expanded Child Flow
            </Button>
        </div>
    )
}
