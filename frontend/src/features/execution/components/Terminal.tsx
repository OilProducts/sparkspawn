import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { TerminalSquare } from 'lucide-react'

import { useStore } from '@/store'
import { Button } from '@/ui'

import { useExecutionGraphArtifactAvailability } from '../hooks/useExecutionGraphArtifactAvailability'
import { ExplainabilityPanel } from './ExplainabilityPanel'

const ATTRACTOR_BASE_PREFIX = '/attractor'
const DEFAULT_TERMINAL_HEIGHT = 288
const MIN_TERMINAL_HEIGHT = 224
const MAX_TERMINAL_HEIGHT_FALLBACK = 720
const RESIZE_STEP_PX = 32
const TERMINAL_HEIGHT_STORAGE_KEY = 'spark.execution.terminalHeight'

const clampTerminalHeight = (value: number) => {
    const maxHeight = typeof window === 'undefined'
        ? MAX_TERMINAL_HEIGHT_FALLBACK
        : Math.max(MIN_TERMINAL_HEIGHT, Math.floor(window.innerHeight * 0.8))
    return Math.min(Math.max(value, MIN_TERMINAL_HEIGHT), maxHeight)
}

export function Terminal() {
    const viewMode = useStore((state) => state.viewMode)
    const selectedRunId = useStore((state) => state.selectedRunId)
    const runtimeStatus = useStore((state) => state.runtimeStatus)
    const logs = useStore((state) => state.logs)
    const clearLogs = useStore((state) => state.clearLogs)
    const graphArtifactAvailability = useExecutionGraphArtifactAvailability(selectedRunId, runtimeStatus)
    const logsEndRef = useRef<HTMLDivElement>(null)
    const dragStateRef = useRef<{ startY: number; startHeight: number } | null>(null)
    const [terminalHeight, setTerminalHeight] = useState(() => {
        if (typeof window === 'undefined') {
            return DEFAULT_TERMINAL_HEIGHT
        }
        const stored = window.localStorage.getItem(TERMINAL_HEIGHT_STORAGE_KEY)
        const parsed = Number.parseInt(stored || '', 10)
        return Number.isFinite(parsed) ? clampTerminalHeight(parsed) : DEFAULT_TERMINAL_HEIGHT
    })

    useEffect(() => {
        logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [logs])

    useEffect(() => {
        if (typeof window === 'undefined') {
            return
        }
        window.localStorage.setItem(TERMINAL_HEIGHT_STORAGE_KEY, String(terminalHeight))
    }, [terminalHeight])

    const resizeTerminal = useCallback((nextHeight: number) => {
        setTerminalHeight(clampTerminalHeight(nextHeight))
    }, [])

    useEffect(() => {
        const handlePointerMove = (event: MouseEvent) => {
            const dragState = dragStateRef.current
            if (!dragState) {
                return
            }
            resizeTerminal(dragState.startHeight + (dragState.startY - event.clientY))
        }

        const handlePointerUp = () => {
            if (!dragStateRef.current) {
                return
            }
            dragStateRef.current = null
            document.body.style.cursor = ''
            document.body.style.userSelect = ''
        }

        window.addEventListener('mousemove', handlePointerMove)
        window.addEventListener('mouseup', handlePointerUp)
        return () => {
            window.removeEventListener('mousemove', handlePointerMove)
            window.removeEventListener('mouseup', handlePointerUp)
        }
    }, [resizeTerminal])

    const graphArtifactStatusLabel = useMemo(() => {
        if (!selectedRunId) {
            return 'Select a planning/build run to inspect artifacts.'
        }
        if (graphArtifactAvailability === 'available') {
            return 'Graph artifact is available.'
        }
        if (graphArtifactAvailability === 'checking') {
            return 'Checking graph artifact availability...'
        }
        if (graphArtifactAvailability === 'missing') {
            return 'Graph artifact not available for this run yet.'
        }
        if (graphArtifactAvailability === 'error') {
            return 'Could not load graph artifact availability.'
        }
        return 'Graph artifact status unknown.'
    }, [selectedRunId, graphArtifactAvailability])
    const latestLog = logs.length > 0 ? logs[logs.length - 1] : null

    if (viewMode !== 'execution') return null

    return (
        <footer
            data-testid="execution-footer-stream"
            style={{ height: terminalHeight }}
            className="border-t bg-background flex flex-col z-30 shadow-[0_-10px_40px_rgba(0,0,0,0.1)]"
        >
            <div
                data-testid="execution-footer-resize-handle"
                role="separator"
                aria-label="Resize terminal output"
                aria-orientation="horizontal"
                aria-valuemin={MIN_TERMINAL_HEIGHT}
                aria-valuemax={typeof window === 'undefined' ? MAX_TERMINAL_HEIGHT_FALLBACK : clampTerminalHeight(Number.MAX_SAFE_INTEGER)}
                aria-valuenow={terminalHeight}
                tabIndex={0}
                onMouseDown={(event) => {
                    event.preventDefault()
                    dragStateRef.current = {
                        startY: event.clientY,
                        startHeight: terminalHeight,
                    }
                    document.body.style.cursor = 'row-resize'
                    document.body.style.userSelect = 'none'
                }}
                onKeyDown={(event) => {
                    if (event.key === 'ArrowUp') {
                        event.preventDefault()
                        resizeTerminal(terminalHeight + RESIZE_STEP_PX)
                    } else if (event.key === 'ArrowDown') {
                        event.preventDefault()
                        resizeTerminal(terminalHeight - RESIZE_STEP_PX)
                    }
                }}
                className="group flex h-3 shrink-0 cursor-row-resize items-center justify-center bg-muted/40"
            >
                <div className="h-1 w-14 rounded-full bg-border transition-colors group-hover:bg-muted-foreground group-focus-visible:bg-muted-foreground" />
            </div>
            <div className="h-10 border-b flex items-center justify-between px-4 bg-muted/30 shrink-0">
                <div className="flex items-center gap-2">
                    <TerminalSquare className="w-4 h-4 text-muted-foreground" />
                    <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Terminal Output</span>
                </div>
                <div className="flex items-center gap-2">
                    <span data-testid="execution-footer-workflow-status" className="rounded border border-border bg-background px-2 py-0.5 text-[11px] text-muted-foreground">
                        Status: {runtimeStatus}
                    </span>
                    <span data-testid="execution-footer-log-count" className="rounded border border-border bg-background px-2 py-0.5 text-[11px] text-muted-foreground">
                        Logs: {logs.length}
                    </span>
                    <Button
                        data-testid="execution-footer-terminal-clear"
                        onClick={clearLogs}
                        variant="ghost"
                        size="xs"
                        className="px-2 text-xs font-medium text-muted-foreground hover:text-foreground"
                    >
                        Clear
                    </Button>
                </div>
            </div>
            <ExplainabilityPanel />
            <div data-testid="execution-footer-workflow-artifacts" className="flex items-center justify-between gap-3 border-b bg-muted/10 px-4 py-2 text-[11px]">
                <div className="min-w-0">
                    <p data-testid="execution-footer-workflow-artifact-status" className="truncate text-muted-foreground">
                        {graphArtifactStatusLabel}
                    </p>
                    <p className="truncate text-muted-foreground/80">
                        {latestLog ? `Latest log: ${latestLog.msg}` : 'No runtime logs yet.'}
                    </p>
                </div>
                {selectedRunId && graphArtifactAvailability === 'available' ? (
                    <Button asChild variant="outline" size="xs" className="whitespace-nowrap">
                        <a
                            data-testid="execution-footer-workflow-artifact-link"
                            href={`${ATTRACTOR_BASE_PREFIX}/pipelines/${encodeURIComponent(selectedRunId)}/graph`}
                            target="_blank"
                            rel="noreferrer"
                        >
                            Open graph artifact
                        </a>
                    </Button>
                ) : null}
            </div>
            <div data-testid="execution-footer-terminal-output" className="min-h-24 flex-1 overflow-y-auto p-4 font-mono text-sm space-y-1">
                {logs.map((log, i) => (
                    <div key={i} className="flex gap-4 py-0.5 border-b border-border/50 last:border-0 hover:bg-muted/50 rounded px-2">
                        <span className="text-muted-foreground w-20 shrink-0 select-none">{log.time}</span>
                        <span className={`break-all ${log.type === 'success' ? 'text-green-500' :
                            log.type === 'error' ? 'text-destructive' :
                                'text-foreground'
                            }`}>
                            {log.msg}
                        </span>
                    </div>
                ))}
                <div ref={logsEndRef} />
            </div>
        </footer>
    )
}
