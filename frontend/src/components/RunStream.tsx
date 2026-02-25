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

export function RunStream() {
    const addLog = useStore((state) => state.addLog)
    const setNodeStatus = useStore((state) => state.setNodeStatus)
    const setHumanGate = useStore((state) => state.setHumanGate)
    const clearHumanGate = useStore((state) => state.clearHumanGate)
    const resetNodeStatuses = useStore((state) => state.resetNodeStatuses)
    const humanGate = useStore((state) => state.humanGate)
    const setRuntimeStatus = useStore((state) => state.setRuntimeStatus)

    useEffect(() => {
        fetch('/status')
            .then((res) => res.json())
            .then((data) => {
                if (data?.status) {
                    setRuntimeStatus(data.status)
                }
            })
            .catch(() => null)

        const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
        const ws = new WebSocket(`${wsProtocol}://${window.location.host}/ws`)

        ws.onmessage = (event) => {
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
                    if (data.status !== 'waiting' && humanGate?.nodeId === data.node) {
                        clearHumanGate()
                    }
                }
                if (data.type === 'human_gate') {
                    setNodeStatus(data.node_id, 'waiting')
                    setHumanGate({
                        id: data.question_id,
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
            ws.close()
        }
    }, [
        addLog,
        setNodeStatus,
        setHumanGate,
        clearHumanGate,
        resetNodeStatuses,
        humanGate,
        setRuntimeStatus,
    ])

    return null
}
