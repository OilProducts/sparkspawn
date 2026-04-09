import { routeFixedNodeGraph, type FixedNodeRouterRequest } from './edgeRouting'

type RouteMessage = {
    requestId: number
    request: FixedNodeRouterRequest
}

type WorkerScope = typeof globalThis & {
    onmessage: ((event: MessageEvent<RouteMessage>) => void) | null
    postMessage: (message: unknown) => void
}

const workerScope = globalThis as WorkerScope

workerScope.onmessage = (event: MessageEvent<RouteMessage>) => {
    try {
        const result = routeFixedNodeGraph(event.data.request)
        workerScope.postMessage({
            requestId: event.data.requestId,
            routes: result.routes,
        })
    } catch (error) {
        workerScope.postMessage({
            requestId: event.data.requestId,
            error: error instanceof Error ? error.message : 'Route worker failed.',
        })
    }
}
