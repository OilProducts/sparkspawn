import { useEffect } from 'react'
import { useStore } from '@/store'

function classifyLog(message: string): 'info' | 'success' | 'error' {
    const lower = message.toLowerCase()
    const isSuccess = lower.includes('success')
    const isError = /fail|error|⚠️/i.test(message)
    if (isSuccess) return 'success'
    if (isError) return 'error'
    return 'info'
}

const normalizeScopePath = (value: string) => {
    const trimmed = value.trim()
    if (!trimmed) return ''
    const slashNormalized = trimmed.replace(/\\/g, '/').replace(/\/{2,}/g, '/')
    const prefix = slashNormalized.startsWith('/') ? '/' : ''
    const rawBody = prefix ? slashNormalized.slice(1) : slashNormalized
    const parts = rawBody.split('/').filter((part) => part.length > 0)
    const segments: string[] = []
    for (const part of parts) {
        if (part === '.') {
            continue
        }
        if (part === '..') {
            segments.pop()
            continue
        }
        segments.push(part)
    }
    const normalizedBody = segments.join('/')
    if (!normalizedBody && prefix) {
        return prefix
    }
    return `${prefix}${normalizedBody}`
}

const runBelongsToProjectScope = (runWorkingDirectory: string, projectPath: string | null) => {
    if (!projectPath) return false
    const normalizedProjectPath = normalizeScopePath(projectPath)
    if (!normalizedProjectPath) return false

    const normalizedRunWorkingDirectory = normalizeScopePath(runWorkingDirectory)
    if (!normalizedRunWorkingDirectory) return false
    if (normalizedRunWorkingDirectory === normalizedProjectPath) return true
    return normalizedRunWorkingDirectory.startsWith(`${normalizedProjectPath}/`)
}

export function RunStream() {
    const addLog = useStore((state) => state.addLog)
    const clearLogs = useStore((state) => state.clearLogs)
    const setNodeStatus = useStore((state) => state.setNodeStatus)
    const setHumanGate = useStore((state) => state.setHumanGate)
    const clearHumanGate = useStore((state) => state.clearHumanGate)
    const resetNodeStatuses = useStore((state) => state.resetNodeStatuses)
    const setRuntimeStatus = useStore((state) => state.setRuntimeStatus)
    const selectedRunId = useStore((state) => state.selectedRunId)
    const setSelectedRunId = useStore((state) => state.setSelectedRunId)
    const activeProjectPath = useStore((state) => state.activeProjectPath)
    const saveState = useStore((state) => state.saveState)
    const saveErrorMessage = useStore((state) => state.saveErrorMessage)
    const saveStateLabel =
        saveState === 'saving'
            ? 'Saving...'
            : saveState === 'saved'
                ? 'Saved'
                : saveState === 'error'
                    ? 'Save Failed'
                    : 'Idle'

    useEffect(() => {
        resetNodeStatuses()
        clearHumanGate()
        clearLogs()
        if (!selectedRunId) {
            setRuntimeStatus('idle')
        }
    }, [selectedRunId, resetNodeStatuses, clearHumanGate, clearLogs, setRuntimeStatus])

    useEffect(() => {
        fetch('/status')
            .then((res) => res.json())
            .then((data) => {
                const runId = typeof data?.last_run_id === 'string' ? data.last_run_id : null
                const lastWorkingDirectory = typeof data?.last_working_directory === 'string' ? data.last_working_directory : ''
                const statusRunInScope = runBelongsToProjectScope(lastWorkingDirectory, activeProjectPath)
                if (!selectedRunId && runId && statusRunInScope) {
                    setSelectedRunId(runId)
                }
                if (!selectedRunId && (!runId || !statusRunInScope)) {
                    setRuntimeStatus('idle')
                    return
                }
                if (data?.status && ((!selectedRunId && statusRunInScope) || runId === selectedRunId)) {
                    setRuntimeStatus(data.status)
                }
            })
            .catch(() => null)
    }, [selectedRunId, activeProjectPath, setRuntimeStatus, setSelectedRunId])

    useEffect(() => {
        if (!selectedRunId) return

        fetch(`/pipelines/${encodeURIComponent(selectedRunId)}`)
            .then((res) => (res.ok ? res.json() : null))
            .then((data) => {
                if (data?.status) {
                    setRuntimeStatus(data.status)
                }
            })
            .catch(() => null)

        const source = new EventSource(`/pipelines/${encodeURIComponent(selectedRunId)}/events`)

        source.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data)
                if (data.type === 'log') {
                    addLog({
                        time: new Date().toLocaleTimeString('en-GB', { hour12: false }),
                        msg: data.msg,
                        type: classifyLog(data.msg),
                    })
                }
                if (data.type === 'state' && data.node && data.status) {
                    setNodeStatus(data.node, data.status)
                    const currentGate = useStore.getState().humanGate
                    if (data.status !== 'waiting' && currentGate?.nodeId === data.node) {
                        clearHumanGate()
                    }
                }
                if (data.type === 'human_gate') {
                    setNodeStatus(data.node_id, 'waiting')
                    setHumanGate({
                        id: data.question_id,
                        runId: selectedRunId,
                        nodeId: data.node_id,
                        prompt: data.prompt,
                        options: data.options || [],
                        flowName: data.flow_name,
                    })
                }
                if (data.type === 'run_meta') {
                    resetNodeStatuses()
                    clearHumanGate()
                    setRuntimeStatus('running')
                }
                if (data.type === 'runtime' && data.status) {
                    setRuntimeStatus(data.status)
                }
            } catch {
                // ignore malformed events
            }
        }

        return () => {
            source.close()
        }
    }, [selectedRunId, addLog, setNodeStatus, clearHumanGate, resetNodeStatuses, setHumanGate, setRuntimeStatus])

    return (
        <div data-testid="execution-runtime-stream-indicator" className="pointer-events-none fixed right-4 top-16 z-[70]">
            <div
                data-testid="global-save-state-indicator"
                className={`rounded-md border px-2 py-1 text-[11px] font-medium shadow-sm ${
                    saveState === 'error'
                        ? 'border-destructive/50 bg-destructive/10 text-destructive'
                        : saveState === 'saved'
                            ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-700'
                            : 'border-border bg-background/95 text-muted-foreground'
                }`}
                title={saveErrorMessage || undefined}
            >
                <span>{saveStateLabel}</span>
                {saveErrorMessage ? <span className="ml-1">- {saveErrorMessage}</span> : null}
            </div>
        </div>
    )
}
