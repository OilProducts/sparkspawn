import { useCallback } from 'react'

import { ApiHttpError, fetchPipelineCancelValidated } from '@/lib/attractorClient'
import { useDialogController } from '@/ui'

import type { RunRecord } from '../model/shared'

const logUnexpectedRunError = (error: unknown) => {
    if (error instanceof ApiHttpError) {
        return
    }
    console.error(error)
}

type UseRunActionsArgs = {
    fetchRuns: () => Promise<void>
    setRuns: React.Dispatch<React.SetStateAction<RunRecord[]>>
}

export function useRunActions({ fetchRuns, setRuns }: UseRunActionsArgs) {
    const { alert, confirm } = useDialogController()

    const requestCancel = useCallback(async (runId: string, currentStatus: string) => {
        if (currentStatus !== 'running') {
            return
        }
        const confirmed = await confirm({
            title: 'Cancel run?',
            description: 'It will stop after the active node finishes.',
            confirmLabel: 'Cancel run',
            cancelLabel: 'Keep running',
            confirmVariant: 'destructive',
        })
        if (!confirmed) {
            return
        }
        setRuns((current) =>
            current.map((run) => (
                run.run_id === runId
                    ? { ...run, status: 'cancel_requested' }
                    : run
            )),
        )
        try {
            await fetchPipelineCancelValidated(runId)
            void fetchRuns()
        } catch (err) {
            logUnexpectedRunError(err)
            setRuns((current) =>
                current.map((run) => (
                    run.run_id === runId
                        ? { ...run, status: currentStatus }
                        : run
                )),
            )
            await alert({
                title: 'Cancel failed',
                description: 'Failed to cancel run.',
            })
        }
    }, [alert, confirm, fetchRuns, setRuns])

    return {
        requestCancel,
    }
}
