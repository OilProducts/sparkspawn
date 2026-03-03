export interface StatusHydrationDecisionInput {
    selectedRunId: string | null
    statusRunId: string | null
    statusRunWorkingDirectory: string
    activeProjectPath: string | null
    statusRuntimeStatus: string | null
}

export interface StatusHydrationDecision {
    nextSelectedRunId: string | null
    nextRuntimeStatus: string | null
}

export interface SelectedRunScopePreflightInput {
    selectedRunWorkingDirectory: string
    activeProjectPath: string | null
    selectedRunStatus: string | null
}

export interface SelectedRunScopePreflightDecision {
    allowStream: boolean
    clearSelectedRun: boolean
    nextRuntimeStatus: string | null
}

const normalizeScopePath = (value: string) => {
    const trimmed = value.trim()
    if (!trimmed) return ''
    const slashNormalized = trimmed.replace(/\\/g, '/').replace(/\/{2,}/g, '/')
    const windowsPrefixMatch = slashNormalized.match(/^[A-Za-z]:\//)
    const prefix = slashNormalized.startsWith('/') ? '/' : windowsPrefixMatch ? windowsPrefixMatch[0] : ''
    const rawBody = prefix ? slashNormalized.slice(prefix.length) : slashNormalized
    const parts = rawBody.split('/').filter((part) => part.length > 0)
    const segments: string[] = []
    for (const part of parts) {
        if (part === '.') {
            continue
        }
        if (part === '..') {
            if (segments.length > 0) {
                segments.pop()
            }
            continue
        }
        segments.push(part)
    }
    const normalizedBody = segments.join('/')
    if (!normalizedBody) {
        if (prefix === '/') {
            return '/'
        }
        return prefix || normalizedBody
    }
    return `${prefix}${normalizedBody}`
}

export const runBelongsToProjectScope = (runWorkingDirectory: string, projectPath: string | null) => {
    if (!projectPath) return false
    const normalizedProjectPath = normalizeScopePath(projectPath)
    if (!normalizedProjectPath) return false

    const normalizedRunWorkingDirectory = normalizeScopePath(runWorkingDirectory)
    if (!normalizedRunWorkingDirectory) return false
    if (normalizedRunWorkingDirectory === normalizedProjectPath) return true
    return normalizedRunWorkingDirectory.startsWith(`${normalizedProjectPath}/`)
}

export const resolveStatusHydrationDecision = ({
    selectedRunId,
    statusRunId,
    statusRunWorkingDirectory,
    activeProjectPath,
    statusRuntimeStatus,
}: StatusHydrationDecisionInput): StatusHydrationDecision => {
    const statusRunInScope = runBelongsToProjectScope(statusRunWorkingDirectory, activeProjectPath)

    if (!selectedRunId && statusRunId && statusRunInScope) {
        return {
            nextSelectedRunId: statusRunId,
            nextRuntimeStatus: statusRuntimeStatus,
        }
    }
    if (!selectedRunId && (!statusRunId || !statusRunInScope)) {
        return {
            nextSelectedRunId: null,
            nextRuntimeStatus: 'idle',
        }
    }
    if (statusRuntimeStatus && ((!selectedRunId && statusRunInScope) || statusRunId === selectedRunId)) {
        return {
            nextSelectedRunId: null,
            nextRuntimeStatus: statusRuntimeStatus,
        }
    }
    return {
        nextSelectedRunId: null,
        nextRuntimeStatus: null,
    }
}

export const resolveSelectedRunScopePreflight = ({
    selectedRunWorkingDirectory,
    activeProjectPath,
    selectedRunStatus,
}: SelectedRunScopePreflightInput): SelectedRunScopePreflightDecision => {
    const selectedRunInScope = runBelongsToProjectScope(selectedRunWorkingDirectory, activeProjectPath)
    if (!selectedRunInScope) {
        return {
            allowStream: false,
            clearSelectedRun: true,
            nextRuntimeStatus: 'idle',
        }
    }
    return {
        allowStream: true,
        clearSelectedRun: false,
        nextRuntimeStatus: selectedRunStatus,
    }
}
