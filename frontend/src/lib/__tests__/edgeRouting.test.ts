import {
    buildRoundedPolylinePath,
    getPortAnchorPoint,
    getRouteMidpoint,
    routeFixedNodeGraph,
    routeIntersectsRect,
} from '@/lib/edgeRouting'
import { describe, expect, it } from 'vitest'

describe('edgeRouting', () => {
    it('anchors ports by side and slot count', () => {
        expect(getPortAnchorPoint(
            { x: 0, y: 0, width: 220, height: 110 },
            { side: 'right', slot: 0, slotCount: 4 },
        )).toEqual({ x: 220, y: 22 })

        expect(getPortAnchorPoint(
            { x: 320, y: 220, width: 220, height: 110 },
            { side: 'left', slot: 3, slotCount: 4 },
        )).toEqual({ x: 320, y: 308 })
    })

    it('builds rounded polyline paths', () => {
        expect(buildRoundedPolylinePath([
            { x: 110, y: 110 },
            { x: 110, y: 160 },
            { x: 410, y: 160 },
            { x: 410, y: 200 },
        ])).toBe('M 110 110 L 110 148 Q 110 160 122 160 L 398 160 Q 410 160 410 172 L 410 200')
    })

    it('finds the midpoint along a routed polyline', () => {
        expect(getRouteMidpoint([
            { x: 0, y: 0 },
            { x: 0, y: 100 },
            { x: 100, y: 100 },
        ])).toEqual({ x: 0, y: 100 })
    })

    it('routes around fixed node obstacles', () => {
        const routes = routeFixedNodeGraph({
            nodes: [
                {
                    id: 'source',
                    rect: { x: 0, y: 0, width: 220, height: 110 },
                },
                {
                    id: 'target',
                    rect: { x: 440, y: 0, width: 220, height: 110 },
                },
                {
                    id: 'obstacle',
                    rect: { x: 270, y: 20, width: 110, height: 120 },
                },
            ],
            edges: [
                {
                    id: 'source->target#0',
                    source: 'source',
                    target: 'target',
                    sourcePort: { side: 'right', slot: 0, slotCount: 1 },
                    targetPort: { side: 'left', slot: 0, slotCount: 1 },
                },
            ],
        }).routes

        const route = routes['source->target#0']
        expect(route).toBeDefined()
        expect(routeIntersectsRect(route, { x: 270, y: 20, width: 110, height: 120 }, 0)).toBe(false)
    })
})
