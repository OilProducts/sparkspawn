import { Badge } from './badge'
import { normalizeProjectPath } from '@/lib/projectPaths'

const formatProjectLabel = (projectPath: string | null) => {
    if (!projectPath) {
        return 'No active project'
    }
    const normalizedPath = normalizeProjectPath(projectPath)
    const segments = normalizedPath.split('/').filter(Boolean)
    return segments[segments.length - 1] || normalizedPath
}

interface ProjectContextChipProps {
    projectPath: string | null
    prefix?: string
    emptyLabel?: string
    className?: string
    testId?: string
}

export function ProjectContextChip({
    projectPath,
    prefix = 'Project',
    emptyLabel = 'No active project',
    className,
    testId,
}: ProjectContextChipProps) {
    const label = projectPath ? formatProjectLabel(projectPath) : emptyLabel

    return (
        <Badge
            data-testid={testId}
            variant="outline"
            className={className}
            title={projectPath || emptyLabel}
        >
            <span className="text-muted-foreground">{prefix}:</span>
            <span className="max-w-40 truncate">{label}</span>
        </Badge>
    )
}
