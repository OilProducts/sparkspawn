import { useMemo, useState, type Dispatch, type SetStateAction } from 'react'
import {
    createTriggerValidated,
    deleteTriggerValidated,
    updateTriggerValidated,
    type TriggerResponse,
} from '@/lib/workspaceClient'
import {
    buildTriggerActionPayload,
    buildTriggerSourcePayload,
    EMPTY_TRIGGER_FORM,
    type TriggerFormState,
    triggerToFormState,
} from '../model/triggerForm'
import { useDialogController } from '@/ui'

type UseTriggerEditorArgs = {
    refreshTriggers: () => Promise<void>
    selectedTrigger: TriggerResponse | null
    setError: (value: string | null) => void
    setRevealedWebhookSecrets: Dispatch<SetStateAction<Record<string, string>>>
    setSelectedTriggerId: (value: string | null) => void
}

export function useTriggerEditor({
    refreshTriggers,
    selectedTrigger,
    setError,
    setRevealedWebhookSecrets,
    setSelectedTriggerId,
}: UseTriggerEditorArgs) {
    const { confirm } = useDialogController()
    const [newTriggerForm, setNewTriggerForm] = useState<TriggerFormState>(EMPTY_TRIGGER_FORM)
    const [editTriggerDraft, setEditTriggerDraft] = useState<{
        triggerId: string | null
        form: TriggerFormState | null
    }>(
        selectedTrigger
            ? {
                triggerId: selectedTrigger.id,
                form: triggerToFormState(selectedTrigger),
            }
            : {
                triggerId: null,
                form: null,
            },
    )
    const selectedTriggerForm = useMemo(
        () => (selectedTrigger ? triggerToFormState(selectedTrigger) : null),
        [selectedTrigger],
    )
    const resolvedEditTriggerForm = editTriggerDraft.triggerId === selectedTrigger?.id
        ? editTriggerDraft.form
        : selectedTriggerForm

    const onCreateTrigger = async () => {
        try {
            const created = await createTriggerValidated({
                name: newTriggerForm.name,
                enabled: newTriggerForm.enabled,
                source_type: newTriggerForm.sourceType,
                action: buildTriggerActionPayload(newTriggerForm),
                source: buildTriggerSourcePayload(newTriggerForm),
            })
            setRevealedWebhookSecrets((current) =>
                created.webhook_secret ? { ...current, [created.id]: created.webhook_secret } : current,
            )
            setNewTriggerForm(EMPTY_TRIGGER_FORM)
            await refreshTriggers()
            setSelectedTriggerId(created.id)
        } catch (nextError) {
            setError(nextError instanceof Error ? nextError.message : 'Unable to create trigger.')
        }
    }

    const onSaveSelectedTrigger = async () => {
        if (!selectedTrigger || !resolvedEditTriggerForm) return
        try {
            const updated = await updateTriggerValidated(selectedTrigger.id, {
                name: resolvedEditTriggerForm.name,
                enabled: resolvedEditTriggerForm.enabled,
                action: buildTriggerActionPayload(resolvedEditTriggerForm),
                source: selectedTrigger.protected ? undefined : buildTriggerSourcePayload(resolvedEditTriggerForm),
            })
            setRevealedWebhookSecrets((current) =>
                updated.webhook_secret ? { ...current, [updated.id]: updated.webhook_secret } : current,
            )
            await refreshTriggers()
        } catch (nextError) {
            setError(nextError instanceof Error ? nextError.message : 'Unable to save trigger.')
        }
    }

    const onDeleteSelectedTrigger = async () => {
        if (!selectedTrigger || selectedTrigger.protected) return
        const confirmed = await confirm({
            title: 'Delete trigger?',
            description: `Delete trigger "${selectedTrigger.name}"?`,
            confirmLabel: 'Delete',
            cancelLabel: 'Keep trigger',
            confirmVariant: 'destructive',
        })
        if (!confirmed) return
        try {
            await deleteTriggerValidated(selectedTrigger.id)
            setSelectedTriggerId(null)
            await refreshTriggers()
        } catch (nextError) {
            setError(nextError instanceof Error ? nextError.message : 'Unable to delete trigger.')
        }
    }

    return {
        editTriggerForm: resolvedEditTriggerForm,
        newTriggerForm,
        onCreateTrigger,
        onDeleteSelectedTrigger,
        onSaveSelectedTrigger,
        setEditTriggerForm: (next: TriggerFormState | null) => {
            setEditTriggerDraft({
                triggerId: selectedTrigger?.id ?? null,
                form: next,
            })
        },
        setNewTriggerForm,
    }
}
