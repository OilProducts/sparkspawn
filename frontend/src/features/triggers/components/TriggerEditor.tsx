import { Checkbox, FieldRow, Input, Label, NativeSelect, Textarea } from '@/ui'

import {
    SHARED_WEBHOOK_ENDPOINT,
    type TriggerFormState,
    type TriggerSourceType,
} from '../model/triggerForm'

export function TriggerEditor({
    form,
    onChange,
    mode,
    protectedTrigger,
}: {
    form: TriggerFormState
    onChange: (value: TriggerFormState) => void
    mode: 'create' | 'edit'
    protectedTrigger: boolean
}) {
    const sourceTypeDisabled = protectedTrigger || mode === 'edit'

    return (
        <div className="mt-4 space-y-3">
            <div className="grid gap-3 lg:grid-cols-2">
                <FieldRow label="Name" htmlFor="trigger-name" className="text-sm">
                    <Input
                        id="trigger-name"
                        value={form.name}
                        onChange={(event) => onChange({ ...form, name: event.target.value })}
                        className="text-sm"
                    />
                </FieldRow>
                <FieldRow label="Target Flow" htmlFor="trigger-target-flow" className="text-sm">
                    <Input
                        id="trigger-target-flow"
                        value={form.flowName}
                        onChange={(event) => onChange({ ...form, flowName: event.target.value })}
                        className="text-sm font-mono"
                    />
                </FieldRow>
            </div>

            <div className="grid gap-3 lg:grid-cols-3">
                <FieldRow label="Source Type" htmlFor="trigger-source-type" className="text-sm">
                    <NativeSelect
                        id="trigger-source-type"
                        value={form.sourceType}
                        onChange={(event) => onChange({ ...form, sourceType: event.target.value as TriggerSourceType })}
                        disabled={sourceTypeDisabled}
                        className="text-sm"
                    >
                        <option value="schedule">Schedule</option>
                        <option value="poll">Poll</option>
                        <option value="webhook">Webhook</option>
                        <option value="flow_event">Flow Event</option>
                        {protectedTrigger ? <option value="workspace_event">Workspace Event</option> : null}
                    </NativeSelect>
                </FieldRow>
                <FieldRow label="Project Target" htmlFor="trigger-project-target" className="text-sm">
                    <Input
                        id="trigger-project-target"
                        value={form.projectPath}
                        onChange={(event) => onChange({ ...form, projectPath: event.target.value })}
                        disabled={protectedTrigger}
                        className="text-sm"
                    />
                </FieldRow>
                <Label htmlFor="trigger-enabled" className="flex items-end gap-2 text-sm">
                    <Checkbox
                        id="trigger-enabled"
                        checked={form.enabled}
                        onCheckedChange={(checked) => onChange({ ...form, enabled: checked === true })}
                    />
                    <span className="text-xs font-medium text-foreground">Enabled</span>
                </Label>
            </div>

            {form.sourceType === 'schedule' ? (
                <div className="grid gap-3 lg:grid-cols-2">
                    <FieldRow label="Schedule Kind" htmlFor="trigger-schedule-kind" className="text-sm">
                        <NativeSelect
                            id="trigger-schedule-kind"
                            value={form.scheduleKind}
                            onChange={(event) => onChange({ ...form, scheduleKind: event.target.value as 'once' | 'interval' | 'weekly' })}
                            className="text-sm"
                        >
                            <option value="interval">Interval</option>
                            <option value="once">One Shot</option>
                            <option value="weekly">Weekly</option>
                        </NativeSelect>
                    </FieldRow>
                    {form.scheduleKind === 'interval' ? (
                        <FieldRow label="Interval Seconds" htmlFor="trigger-schedule-interval-seconds" className="text-sm">
                            <Input
                                id="trigger-schedule-interval-seconds"
                                value={form.scheduleIntervalSeconds}
                                onChange={(event) => onChange({ ...form, scheduleIntervalSeconds: event.target.value })}
                                className="text-sm"
                            />
                        </FieldRow>
                    ) : null}
                    {form.scheduleKind === 'once' ? (
                        <FieldRow label="Run At (ISO UTC)" htmlFor="trigger-schedule-run-at" className="text-sm lg:col-span-2">
                            <Input
                                id="trigger-schedule-run-at"
                                value={form.scheduleRunAt}
                                onChange={(event) => onChange({ ...form, scheduleRunAt: event.target.value })}
                                className="text-sm font-mono"
                                placeholder="2026-03-22T15:00:00Z"
                            />
                        </FieldRow>
                    ) : null}
                    {form.scheduleKind === 'weekly' ? (
                        <>
                            <FieldRow label="Weekdays" htmlFor="trigger-schedule-weekdays" className="text-sm">
                                <Input
                                    id="trigger-schedule-weekdays"
                                    value={form.scheduleWeekdays}
                                    onChange={(event) => onChange({ ...form, scheduleWeekdays: event.target.value })}
                                    className="text-sm"
                                    placeholder="mon,wed,fri"
                                />
                            </FieldRow>
                            <div className="grid grid-cols-2 gap-3">
                                <FieldRow label="Hour" htmlFor="trigger-schedule-hour" className="text-sm">
                                    <Input
                                        id="trigger-schedule-hour"
                                        value={form.scheduleHour}
                                        onChange={(event) => onChange({ ...form, scheduleHour: event.target.value })}
                                        className="text-sm"
                                    />
                                </FieldRow>
                                <FieldRow label="Minute" htmlFor="trigger-schedule-minute" className="text-sm">
                                    <Input
                                        id="trigger-schedule-minute"
                                        value={form.scheduleMinute}
                                        onChange={(event) => onChange({ ...form, scheduleMinute: event.target.value })}
                                        className="text-sm"
                                    />
                                </FieldRow>
                            </div>
                        </>
                    ) : null}
                </div>
            ) : null}

            {form.sourceType === 'poll' ? (
                <div className="grid gap-3 lg:grid-cols-2">
                    <FieldRow label="Poll URL" htmlFor="trigger-poll-url" className="text-sm lg:col-span-2">
                        <Input
                            id="trigger-poll-url"
                            value={form.pollUrl}
                            onChange={(event) => onChange({ ...form, pollUrl: event.target.value })}
                            className="text-sm font-mono"
                        />
                    </FieldRow>
                    <FieldRow label="Interval Seconds" htmlFor="trigger-poll-interval-seconds" className="text-sm">
                        <Input
                            id="trigger-poll-interval-seconds"
                            value={form.pollIntervalSeconds}
                            onChange={(event) => onChange({ ...form, pollIntervalSeconds: event.target.value })}
                            className="text-sm"
                        />
                    </FieldRow>
                    <FieldRow label="Items Path" htmlFor="trigger-poll-items-path" className="text-sm">
                        <Input
                            id="trigger-poll-items-path"
                            value={form.pollItemsPath}
                            onChange={(event) => onChange({ ...form, pollItemsPath: event.target.value })}
                            className="text-sm"
                        />
                    </FieldRow>
                    <FieldRow label="Item ID Path" htmlFor="trigger-poll-item-id-path" className="text-sm">
                        <Input
                            id="trigger-poll-item-id-path"
                            value={form.pollItemIdPath}
                            onChange={(event) => onChange({ ...form, pollItemIdPath: event.target.value })}
                            className="text-sm"
                        />
                    </FieldRow>
                    <FieldRow label="Headers JSON" htmlFor="trigger-poll-headers-json" className="text-sm lg:col-span-2">
                        <Textarea
                            id="trigger-poll-headers-json"
                            value={form.pollHeadersText}
                            onChange={(event) => onChange({ ...form, pollHeadersText: event.target.value })}
                            className="min-h-24 font-mono text-xs"
                        />
                    </FieldRow>
                </div>
            ) : null}

            {form.sourceType === 'flow_event' ? (
                <div className="grid gap-3 lg:grid-cols-2">
                    <FieldRow label="Observed Flow" htmlFor="trigger-flow-event-flow-name" className="text-sm">
                        <Input
                            id="trigger-flow-event-flow-name"
                            value={form.flowEventFlowName}
                            onChange={(event) => onChange({ ...form, flowEventFlowName: event.target.value })}
                            className="text-sm font-mono"
                            placeholder="Leave blank for any observed flow"
                        />
                    </FieldRow>
                    <FieldRow label="Terminal Statuses" htmlFor="trigger-flow-event-statuses" className="text-sm">
                        <Input
                            id="trigger-flow-event-statuses"
                            value={form.flowEventStatuses}
                            onChange={(event) => onChange({ ...form, flowEventStatuses: event.target.value })}
                            className="text-sm"
                            placeholder="completed,failed"
                        />
                    </FieldRow>
                </div>
            ) : null}

            {form.sourceType === 'webhook' ? (
                <div className="rounded-md border border-border bg-background/70 px-3 py-2 text-sm text-muted-foreground">
                    Webhook triggers use the shared ingress endpoint at <code>{SHARED_WEBHOOK_ENDPOINT}</code>. The key and secret are generated automatically.
                </div>
            ) : null}

            <FieldRow label="Static Context JSON" htmlFor="trigger-static-context-json" className="text-sm">
                <Textarea
                    id="trigger-static-context-json"
                    value={form.staticContextText}
                    onChange={(event) => onChange({ ...form, staticContextText: event.target.value })}
                    disabled={protectedTrigger}
                    className="min-h-24 font-mono text-xs"
                />
            </FieldRow>
        </div>
    )
}
