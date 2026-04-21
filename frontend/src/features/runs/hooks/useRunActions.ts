import { useCallback } from 'react'

import { ApiHttpError, fetchPipelineCancelValidated, fetchPipelineRetryValidated } from '@/lib/attractorClient'
import { useDialogController } from '@/components/app/dialog-controller'
import type { RunRecord } from '../model/shared'

const logUnexpectedRunError = (error: unknown) => {
    if (error instanceof ApiHttpError) {
        return
    }
    console.error(error)
}

type UseRunActionsArgs = {
    setRuns: React.Dispatch<React.SetStateAction<RunRecord[]>>
}

export function useRunActions({ setRuns }: UseRunActionsArgs) {
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
    }, [alert, confirm, setRuns])

    const requestRetry = useCallback(async (runId: string, currentStatus: string) => {
        if (currentStatus !== 'failed') {
            return
        }
        const confirmed = await confirm({
            title: 'Retry run?',
            description: 'It will resume this run from its checkpoint using the same run id.',
            confirmLabel: 'Retry run',
            cancelLabel: 'Keep failed',
        })
        if (!confirmed) {
            return
        }
        setRuns((current) =>
            current.map((run) => (
                run.run_id === runId
                    ? { ...run, status: 'running', last_error: '' }
                    : run
            )),
        )
        try {
            await fetchPipelineRetryValidated(runId)
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
                title: 'Retry failed',
                description: 'Failed to retry run.',
            })
        }
    }, [alert, confirm, setRuns])

    return {
        requestCancel,
        requestRetry,
    }
}
