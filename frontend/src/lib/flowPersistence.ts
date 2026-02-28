import { useStore } from '@/store'

interface SaveFlowErrorDetail {
    status?: string
    error?: string
}

const FALLBACK_SAVE_FAILURE_MESSAGE = 'Flow save failed before confirmation from backend.'

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
    if (error) {
        return error
    }
    return `Flow save failed with HTTP ${statusCode}.`
}

export async function saveFlowContent(name: string, content: string): Promise<boolean> {
    const { markSaveInFlight, markSaveSuccess, markSaveFailure } = useStore.getState()
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
        markSaveFailure(`Flow save failed: ${message}`)
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
        markSaveFailure(message)
        return false
    }

    const status = typeof (payload as { status?: unknown } | null)?.status === 'string'
        ? (payload as { status: string }).status
        : undefined
    if (status !== 'saved') {
        markSaveFailure(FALLBACK_SAVE_FAILURE_MESSAGE)
        return false
    }

    markSaveSuccess()
    return true
}
