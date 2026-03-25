import { useEffect, useMemo, useRef, useState, type Dispatch, type SetStateAction } from 'react'
import {
    createTriggerValidated,
    deleteTriggerValidated,
    updateTriggerValidated,
    type TriggerResponse,
} from '@/lib/workspaceClient'
import {
    buildTriggerActionPayload,
    buildTriggerSourcePayload,
    createEmptyTriggerForm,
    type TriggerFormState,
    triggerToFormState,
} from '../model/triggerForm'
import { useDialogController } from '@/ui'

type UseTriggerEditorArgs = {
    activeProjectPath: string | null
    refreshTriggers: () => Promise<void>
    selectedTrigger: TriggerResponse | null
    setError: (value: string | null) => void
    setRevealedWebhookSecrets: Dispatch<SetStateAction<Record<string, string>>>
    setSelectedTriggerId: (value: string | null) => void
}

type NewTriggerDraftState = {
    form: TriggerFormState
    targetBehavior: 'default' | 'active' | 'manual'
}

type EditTriggerDraftState = {
    triggerId: string | null
    form: TriggerFormState | null
    targetBehavior: 'inferred' | 'active' | 'manual'
}

const resolveActiveTargetFields = (activeProjectPath: string | null) => ({
    targetMode: activeProjectPath ? 'active' as const : 'none' as const,
    projectPath: activeProjectPath ?? '',
})

const applyActiveTargetFields = (
    form: TriggerFormState,
    activeProjectPath: string | null,
): TriggerFormState => {
    const nextTargetFields = resolveActiveTargetFields(activeProjectPath)
    if (
        form.targetMode === nextTargetFields.targetMode
        && form.projectPath === nextTargetFields.projectPath
    ) {
        return form
    }
    return {
        ...form,
        ...nextTargetFields,
    }
}

const applyInferredTargetFields = (
    form: TriggerFormState,
    selectedTrigger: TriggerResponse,
    activeProjectPath: string | null,
): TriggerFormState => {
    const inferredTarget = triggerToFormState(selectedTrigger, activeProjectPath)
    if (
        form.targetMode === inferredTarget.targetMode
        && form.projectPath === inferredTarget.projectPath
    ) {
        return form
    }
    return {
        ...form,
        targetMode: inferredTarget.targetMode,
        projectPath: inferredTarget.projectPath,
    }
}

const didTriggerTargetChange = (current: TriggerFormState, next: TriggerFormState) => (
    current.targetMode !== next.targetMode
    || current.projectPath !== next.projectPath
)

const buildProtectedTriggerUpdatePayload = (form: TriggerFormState) => ({
    name: form.name,
    enabled: form.enabled,
    action: {
        flow_name: form.flowName.trim(),
    },
})

export function useTriggerEditor({
    activeProjectPath,
    refreshTriggers,
    selectedTrigger,
    setError,
    setRevealedWebhookSecrets,
    setSelectedTriggerId,
}: UseTriggerEditorArgs) {
    const { confirm } = useDialogController()
    const activeProjectPathRef = useRef(activeProjectPath)
    const [newTriggerDraft, setNewTriggerDraft] = useState<NewTriggerDraftState>(() => ({
        form: createEmptyTriggerForm(activeProjectPath),
        targetBehavior: 'default',
    }))
    const [editTriggerDraft, setEditTriggerDraft] = useState<EditTriggerDraftState>({
        triggerId: null,
        form: null,
        targetBehavior: 'inferred',
    })
    const selectedTriggerForm = useMemo(
        () => (selectedTrigger ? triggerToFormState(selectedTrigger, activeProjectPath) : null),
        [activeProjectPath, selectedTrigger],
    )
    const newTriggerForm = newTriggerDraft.form
    const resolvedEditTriggerForm = editTriggerDraft.triggerId === selectedTrigger?.id
        ? editTriggerDraft.form
        : selectedTriggerForm

    useEffect(() => {
        activeProjectPathRef.current = activeProjectPath
    }, [activeProjectPath])

    useEffect(() => {
        setNewTriggerDraft((current) => {
            if (current.targetBehavior === 'manual') {
                return current
            }
            const syncedForm = applyActiveTargetFields(current.form, activeProjectPath)
            if (syncedForm === current.form) {
                return current
            }
            return {
                ...current,
                form: syncedForm,
            }
        })
    }, [activeProjectPath])

    useEffect(() => {
        setEditTriggerDraft((current) => {
            if (!selectedTrigger || current.triggerId !== selectedTrigger.id || !current.form) {
                return current
            }
            if (current.targetBehavior === 'manual') {
                return current
            }
            const syncedForm = current.targetBehavior === 'active'
                ? applyActiveTargetFields(current.form, activeProjectPath)
                : applyInferredTargetFields(current.form, selectedTrigger, activeProjectPath)
            if (syncedForm === current.form) {
                return current
            }
            return {
                ...current,
                form: syncedForm,
            }
        })
    }, [activeProjectPath, selectedTrigger])

    useEffect(() => {
        setEditTriggerDraft((current) => (
            current.triggerId === selectedTrigger?.id
                ? current
                : {
                    triggerId: null,
                    form: null,
                    targetBehavior: 'inferred',
                }
        ))
    }, [selectedTrigger?.id])

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
            setNewTriggerDraft({
                form: createEmptyTriggerForm(activeProjectPathRef.current),
                targetBehavior: 'default',
            })
            await refreshTriggers()
            setSelectedTriggerId(created.id)
        } catch (nextError) {
            setError(nextError instanceof Error ? nextError.message : 'Unable to create trigger.')
        }
    }

    const onSaveSelectedTrigger = async () => {
        if (!selectedTrigger || !resolvedEditTriggerForm) return
        try {
            const payload = selectedTrigger.protected
                ? buildProtectedTriggerUpdatePayload(resolvedEditTriggerForm)
                : {
                    name: resolvedEditTriggerForm.name,
                    enabled: resolvedEditTriggerForm.enabled,
                    action: buildTriggerActionPayload(resolvedEditTriggerForm),
                    source: buildTriggerSourcePayload(resolvedEditTriggerForm),
                }
            const updated = await updateTriggerValidated(selectedTrigger.id, payload)
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
            setEditTriggerDraft((current) => {
                const currentForm = current.triggerId === selectedTrigger?.id && current.form
                    ? current.form
                    : selectedTriggerForm ?? next
                const targetBehavior = currentForm && next && didTriggerTargetChange(currentForm, next)
                    ? (next.targetMode === 'active' ? 'active' : 'manual')
                    : current.triggerId === selectedTrigger?.id
                        ? current.targetBehavior
                        : 'inferred'
                return {
                    triggerId: selectedTrigger?.id ?? null,
                    form: next,
                    targetBehavior,
                }
            })
        },
        setNewTriggerForm: (next: TriggerFormState) => {
            setNewTriggerDraft((current) => ({
                form: next,
                targetBehavior: didTriggerTargetChange(current.form, next)
                    ? (next.targetMode === 'active' ? 'active' : 'manual')
                    : current.targetBehavior,
            }))
        },
    }
}
