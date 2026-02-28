import { useStore, type SaveErrorKind } from '@/store'

interface SaveFlowErrorDetail {
    status?: string
    error?: string
}

const FALLBACK_SAVE_FAILURE_MESSAGE = 'Flow save failed before confirmation from backend.'
let lastSaveRequest: { name: string; content: string } | null = null

function parseErrorDetail(payload: unknown): SaveFlowErrorDetail {
    if (!payload || typeof payload !== 'object') {
        return {}
    }
    if ('detail' in payload && payload.detail && typeof payload.detail === 'object') {
        return payload.detail as SaveFlowErrorDetail
    }
    return payload as SaveFlowErrorDetail
}

function buildErrorMessage(status: string | undefined, error: string | undefined, statusCode: number): string {
    if (status === 'parse_error') {
        return `Save blocked by DOT parse error: ${error ?? FALLBACK_SAVE_FAILURE_MESSAGE}`
    }
    if (status === 'validation_error') {
        return `Save blocked by validation errors: ${error ?? FALLBACK_SAVE_FAILURE_MESSAGE}`
    }
    if (status === 'conflict' || statusCode === 409) {
        return `Save conflict detected: ${error ?? 'The flow was modified elsewhere. Refresh and re-apply your changes.'}`
    }
    if (error) {
        return error
    }
    return `Flow save failed with HTTP ${statusCode}.`
}

export async function retryLastSaveContent(): Promise<boolean> {
    if (!lastSaveRequest) return false
    return saveFlowContent(lastSaveRequest.name, lastSaveRequest.content)
}

export async function saveFlowContent(name: string, content: string): Promise<boolean> {
    const { markSaveInFlight, markSaveSuccess, markSaveFailure, markSaveConflict } = useStore.getState()
    lastSaveRequest = { name, content }
    markSaveInFlight()

    let response: Response
    try {
        response = await fetch('/api/flows', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, content }),
        })
    } catch (error) {
        const message = error instanceof Error ? error.message : 'network error while saving flow'
        markSaveFailure(`Flow save failed: ${message}`, 'network')
        return false
    }

    let payload: unknown = null
    try {
        payload = await response.json()
    } catch {
        payload = null
    }

    if (!response.ok) {
        const detail = parseErrorDetail(payload)
        const message = buildErrorMessage(detail.status, detail.error, response.status)
        if (detail.status === 'conflict' || response.status === 409) {
            markSaveConflict(message)
            return false
        }
        let errorKind: SaveErrorKind = 'http'
        if (detail.status === 'parse_error') {
            errorKind = 'parse_error'
        } else if (detail.status === 'validation_error') {
            errorKind = 'validation_error'
        }
        markSaveFailure(message, errorKind)
        return false
    }

    const status = typeof (payload as { status?: unknown } | null)?.status === 'string'
        ? (payload as { status: string }).status
        : undefined
    if (status !== 'saved') {
        if (status === 'conflict') {
            markSaveConflict(buildErrorMessage(status, undefined, response.status))
            return false
        }
        markSaveFailure(FALLBACK_SAVE_FAILURE_MESSAGE, 'unknown')
        return false
    }

    markSaveSuccess()
    return true
}
