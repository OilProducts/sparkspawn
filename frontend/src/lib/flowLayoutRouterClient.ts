import { routeFixedNodeGraph, type FixedNodeRouterRequest } from './edgeRouting'

type PendingRouteRequest = {
    resolve: (routes: Record<string, import('./edgeRouting').EdgeRoute>) => void
    reject: (error: Error) => void
}

let workerInstance: Worker | null = null
let workerRequestId = 0
const pendingRequests = new Map<number, PendingRouteRequest>()

function getWorker(): Worker | null {
    if (typeof Worker === 'undefined') {
        return null
    }

    if (!workerInstance) {
        workerInstance = new Worker(
            new URL('./flowLayoutRouterWorker.ts', import.meta.url),
            { type: 'module' },
        )
        workerInstance.onmessage = (event: MessageEvent<{
            requestId: number
            routes?: Record<string, import('./edgeRouting').EdgeRoute>
            error?: string
        }>) => {
            const pendingRequest = pendingRequests.get(event.data.requestId)
            if (!pendingRequest) {
                return
            }
            pendingRequests.delete(event.data.requestId)
            if (event.data.error) {
                pendingRequest.reject(new Error(event.data.error))
                return
            }
            pendingRequest.resolve(event.data.routes ?? {})
        }
        workerInstance.onerror = () => {
            pendingRequests.forEach((pendingRequest) => {
                pendingRequest.reject(new Error('Route worker crashed.'))
            })
            pendingRequests.clear()
            workerInstance = null
        }
    }

    return workerInstance
}

export async function routeFixedNodeGraphInWorker(
    request: FixedNodeRouterRequest,
): Promise<Record<string, import('./edgeRouting').EdgeRoute>> {
    const worker = getWorker()
    if (!worker) {
        return routeFixedNodeGraph(request).routes
    }

    workerRequestId += 1
    const requestId = workerRequestId

    return new Promise((resolve, reject) => {
        pendingRequests.set(requestId, { resolve, reject })
        worker.postMessage({
            requestId,
            request,
        })
    })
}
