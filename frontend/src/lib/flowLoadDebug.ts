import type { DiagnosticEntry } from '@/state/store-types'

export const FLOW_LOAD_DEBUG_QUERY_PARAM = 'debugFlowLoad'
export const FLOW_LOAD_DEBUG_STORAGE_KEY = 'spark.debug.flow_load'
const FLOW_LOAD_DEBUG_TRACE_LIMIT = 200

export type FlowLoadDebugEvent = {
    timestamp: string
    event: string
    flowName: string | null
    details?: Record<string, unknown>
}

declare global {
    interface Window {
        __sparkFlowLoadDebug?: FlowLoadDebugEvent[]
    }
}

export const isFlowLoadDebugEnabled = () => {
    if (typeof window === 'undefined') {
        return false
    }
    try {
        const params = new URLSearchParams(window.location.search)
        if (params.get(FLOW_LOAD_DEBUG_QUERY_PARAM) === '1') {
            return true
        }
        return window.localStorage.getItem(FLOW_LOAD_DEBUG_STORAGE_KEY) === '1'
    } catch {
        return false
    }
}

const ensureFlowLoadDebugTrace = () => {
    if (typeof window === 'undefined') {
        return null
    }
    if (!window.__sparkFlowLoadDebug) {
        window.__sparkFlowLoadDebug = []
    }
    return window.__sparkFlowLoadDebug
}

export const clearFlowLoadDebugTrace = () => {
    if (typeof window === 'undefined') {
        return
    }
    window.__sparkFlowLoadDebug = []
}

export const summarizeDiagnosticsForFlowLoadDebug = (diagnostics?: DiagnosticEntry[]) => {
    const entries = diagnostics ?? []
    const ruleIds = [...new Set(entries.map((diagnostic) => diagnostic.rule_id))].slice(0, 12)
    return {
        diagnosticCount: entries.length,
        errorCount: entries.filter((diagnostic) => diagnostic.severity === 'error').length,
        warningCount: entries.filter((diagnostic) => diagnostic.severity === 'warning').length,
        infoCount: entries.filter((diagnostic) => diagnostic.severity === 'info').length,
        ruleIds,
    }
}

export const recordFlowLoadDebug = (
    event: string,
    flowName: string | null,
    details?: Record<string, unknown>,
) => {
    if (!isFlowLoadDebugEnabled()) {
        return
    }
    const trace = ensureFlowLoadDebugTrace()
    const entry: FlowLoadDebugEvent = {
        timestamp: new Date().toISOString(),
        event,
        flowName,
        details,
    }
    if (trace) {
        trace.push(entry)
        if (trace.length > FLOW_LOAD_DEBUG_TRACE_LIMIT) {
            trace.splice(0, trace.length - FLOW_LOAD_DEBUG_TRACE_LIMIT)
        }
    }
    if (details) {
        console.debug(`[flow-load] ${event}`, {
            flowName,
            ...details,
        })
        return
    }
    console.debug(`[flow-load] ${event}`, { flowName })
}

export const extractDebugErrorSummary = (error: unknown) => {
    if (error instanceof Error) {
        return {
            message: error.message,
            name: error.name,
        }
    }
    return {
        message: String(error),
        name: typeof error,
    }
}
