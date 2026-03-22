import { useEffect, useMemo, useState } from "react"

import type { TriggerResponse, TriggerSourceType } from "@/lib/workspaceClient"
import {
  createTriggerValidated,
  deleteTriggerValidated,
  fetchTriggerListValidated,
  updateTriggerValidated,
} from "@/lib/workspaceClient"

type TriggerFormState = {
  name: string
  enabled: boolean
  sourceType: TriggerSourceType
  flowName: string
  projectPath: string
  staticContextText: string
  scheduleKind: 'once' | 'interval' | 'weekly'
  scheduleRunAt: string
  scheduleIntervalSeconds: string
  scheduleWeekdays: string
  scheduleHour: string
  scheduleMinute: string
  pollUrl: string
  pollIntervalSeconds: string
  pollHeadersText: string
  pollItemsPath: string
  pollItemIdPath: string
  flowEventFlowName: string
  flowEventStatuses: string
}

const EMPTY_FORM: TriggerFormState = {
  name: '',
  enabled: true,
  sourceType: 'schedule',
  flowName: '',
  projectPath: '',
  staticContextText: '{}',
  scheduleKind: 'interval',
  scheduleRunAt: '',
  scheduleIntervalSeconds: '300',
  scheduleWeekdays: 'mon,fri',
  scheduleHour: '9',
  scheduleMinute: '0',
  pollUrl: 'https://example.com/data.json',
  pollIntervalSeconds: '300',
  pollHeadersText: '{}',
  pollItemsPath: 'items',
  pollItemIdPath: 'id',
  flowEventFlowName: '',
  flowEventStatuses: 'success,failed',
}

const SHARED_WEBHOOK_ENDPOINT = '/workspace/api/webhooks'

function formatTimestamp(value?: string | null): string {
  if (!value) return 'Never'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString()
}

function sourceSummary(trigger: TriggerResponse): string {
  if (trigger.source_type === 'schedule') {
    const kind = typeof trigger.source.kind === 'string' ? trigger.source.kind : 'schedule'
    return `Schedule · ${kind}`
  }
  if (trigger.source_type === 'poll') {
    return `Poll · ${String(trigger.source.url ?? '')}`
  }
  if (trigger.source_type === 'webhook') {
    return `Webhook · key ${String(trigger.source.webhook_key ?? '')}`
  }
  if (trigger.source_type === 'workspace_event') {
    return `System event · ${String(trigger.source.event_name ?? '')}`
  }
  return `Flow event · ${String(trigger.source.flow_name ?? 'any flow')}`
}

function buildSourcePayload(form: TriggerFormState): Record<string, unknown> {
  if (form.sourceType === 'schedule') {
    if (form.scheduleKind === 'once') {
      return {
        kind: 'once',
        run_at: form.scheduleRunAt.trim(),
      }
    }
    if (form.scheduleKind === 'interval') {
      return {
        kind: 'interval',
        interval_seconds: parseInt(form.scheduleIntervalSeconds, 10),
      }
    }
    return {
      kind: 'weekly',
      weekdays: form.scheduleWeekdays.split(',').map((entry) => entry.trim().toLowerCase()).filter(Boolean),
      hour: parseInt(form.scheduleHour, 10),
      minute: parseInt(form.scheduleMinute, 10),
    }
  }
  if (form.sourceType === 'poll') {
    return {
      url: form.pollUrl.trim(),
      interval_seconds: parseInt(form.pollIntervalSeconds, 10),
      headers: JSON.parse(form.pollHeadersText || '{}') as Record<string, unknown>,
      items_path: form.pollItemsPath.trim(),
      item_id_path: form.pollItemIdPath.trim(),
    }
  }
  if (form.sourceType === 'flow_event') {
    return {
      flow_name: form.flowEventFlowName.trim() || null,
      statuses: form.flowEventStatuses.split(',').map((entry) => entry.trim().toLowerCase()).filter(Boolean),
    }
  }
  return {}
}

function buildActionPayload(form: TriggerFormState): Record<string, unknown> {
  return {
    flow_name: form.flowName.trim(),
    project_path: form.projectPath.trim() || null,
    static_context: JSON.parse(form.staticContextText || '{}') as Record<string, unknown>,
  }
}

function triggerToForm(trigger: TriggerResponse): TriggerFormState {
  const source = trigger.source
  return {
    name: trigger.name,
    enabled: trigger.enabled,
    sourceType: trigger.source_type,
    flowName: trigger.action.flow_name,
    projectPath: trigger.action.project_path ?? '',
    staticContextText: JSON.stringify(trigger.action.static_context ?? {}, null, 2),
    scheduleKind: (typeof source.kind === 'string' ? source.kind : 'interval') as 'once' | 'interval' | 'weekly',
    scheduleRunAt: typeof source.run_at === 'string' ? source.run_at : '',
    scheduleIntervalSeconds: `${typeof source.interval_seconds === 'number' ? source.interval_seconds : 300}`,
    scheduleWeekdays: Array.isArray(source.weekdays) ? source.weekdays.map((entry) => String(entry)).join(',') : 'mon,fri',
    scheduleHour: `${typeof source.hour === 'number' ? source.hour : 9}`,
    scheduleMinute: `${typeof source.minute === 'number' ? source.minute : 0}`,
    pollUrl: typeof source.url === 'string' ? source.url : 'https://example.com/data.json',
    pollIntervalSeconds: `${typeof source.interval_seconds === 'number' ? source.interval_seconds : 300}`,
    pollHeadersText: JSON.stringify(source.headers ?? {}, null, 2),
    pollItemsPath: typeof source.items_path === 'string' ? source.items_path : 'items',
    pollItemIdPath: typeof source.item_id_path === 'string' ? source.item_id_path : 'id',
    flowEventFlowName: typeof source.flow_name === 'string' ? source.flow_name : '',
    flowEventStatuses: Array.isArray(source.statuses) ? source.statuses.map((entry) => String(entry)).join(',') : 'success,failed',
  }
}

export function TriggersPanel() {
  const [triggers, setTriggers] = useState<TriggerResponse[]>([])
  const [selectedTriggerId, setSelectedTriggerId] = useState<string | null>(null)
  const [newTriggerForm, setNewTriggerForm] = useState<TriggerFormState>(EMPTY_FORM)
  const [editTriggerForm, setEditTriggerForm] = useState<TriggerFormState | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [revealedWebhookSecrets, setRevealedWebhookSecrets] = useState<Record<string, string>>({})

  const selectedTrigger = useMemo(
    () => triggers.find((trigger) => trigger.id === selectedTriggerId) ?? null,
    [selectedTriggerId, triggers],
  )

  const systemTriggers = useMemo(
    () => triggers.filter((trigger) => trigger.protected),
    [triggers],
  )
  const customTriggers = useMemo(
    () => triggers.filter((trigger) => !trigger.protected),
    [triggers],
  )

  const refreshTriggers = async () => {
    setLoading(true)
    try {
      const payload = await fetchTriggerListValidated()
      setTriggers(payload)
      setSelectedTriggerId((current) => current ?? payload[0]?.id ?? null)
      setError(null)
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Unable to load triggers.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refreshTriggers()
  }, [])

  useEffect(() => {
    if (selectedTrigger) {
      setEditTriggerForm(triggerToForm(selectedTrigger))
    } else {
      setEditTriggerForm(null)
    }
  }, [selectedTrigger])

  const onCreateTrigger = async () => {
    try {
      const created = await createTriggerValidated({
        name: newTriggerForm.name,
        enabled: newTriggerForm.enabled,
        source_type: newTriggerForm.sourceType,
        action: buildActionPayload(newTriggerForm),
        source: buildSourcePayload(newTriggerForm),
      })
      setRevealedWebhookSecrets((current) =>
        created.webhook_secret ? { ...current, [created.id]: created.webhook_secret } : current,
      )
      setNewTriggerForm(EMPTY_FORM)
      await refreshTriggers()
      setSelectedTriggerId(created.id)
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Unable to create trigger.')
    }
  }

  const onSaveSelectedTrigger = async () => {
    if (!selectedTrigger || !editTriggerForm) return
    try {
      const updated = await updateTriggerValidated(selectedTrigger.id, {
        name: editTriggerForm.name,
        enabled: editTriggerForm.enabled,
        action: buildActionPayload(editTriggerForm),
        source: selectedTrigger.protected ? undefined : buildSourcePayload(editTriggerForm),
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
    if (!window.confirm(`Delete trigger "${selectedTrigger.name}"?`)) return
    try {
      await deleteTriggerValidated(selectedTrigger.id)
      setSelectedTriggerId(null)
      await refreshTriggers()
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Unable to delete trigger.')
    }
  }

  const onRegenerateWebhookSecret = async () => {
    if (!selectedTrigger || selectedTrigger.source_type !== 'webhook') return
    try {
      const updated = await updateTriggerValidated(selectedTrigger.id, {
        regenerate_webhook_secret: true,
      })
      if (updated.webhook_secret) {
        setRevealedWebhookSecrets((current) => ({ ...current, [selectedTrigger.id]: updated.webhook_secret! }))
      }
      await refreshTriggers()
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Unable to regenerate webhook secret.')
    }
  }

  return (
    <section data-testid="triggers-panel" className="flex-1 overflow-auto p-6">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
        <div className="space-y-1">
          <h2 className="text-lg font-semibold">Triggers</h2>
          <p className="text-sm text-muted-foreground">
            Manage system routing, schedules, polling, flow-event automation, and shared webhook ingress.
          </p>
        </div>

        {error ? (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        ) : null}

        <div className="grid gap-6 lg:grid-cols-[minmax(20rem,26rem)_minmax(0,1fr)]">
          <div className="space-y-4">
            <div className="rounded-md border border-border bg-card p-4 shadow-sm">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">System triggers</div>
                  <div className="text-sm text-muted-foreground">Protected approval and review routing.</div>
                </div>
                <button
                  type="button"
                  onClick={() => void refreshTriggers()}
                  className="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                >
                  {loading ? 'Refreshing…' : 'Refresh'}
                </button>
              </div>
              <div className="mt-3 space-y-2">
                {systemTriggers.map((trigger) => (
                  <button
                    key={trigger.id}
                    type="button"
                    data-testid={`trigger-row-${trigger.id}`}
                    onClick={() => setSelectedTriggerId(trigger.id)}
                    className={`w-full rounded-md border px-3 py-2 text-left ${selectedTriggerId === trigger.id ? 'border-foreground bg-muted/60' : 'border-border bg-background/70'}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-medium">{trigger.name}</span>
                      <span className="text-[11px] text-muted-foreground">{trigger.enabled ? 'Enabled' : 'Disabled'}</span>
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">{sourceSummary(trigger)}</div>
                  </button>
                ))}
                {systemTriggers.length === 0 ? <p className="text-xs text-muted-foreground">No protected triggers configured.</p> : null}
              </div>
            </div>

            <div className="rounded-md border border-border bg-card p-4 shadow-sm">
              <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Custom triggers</div>
              <div className="mt-3 space-y-2">
                {customTriggers.map((trigger) => (
                  <button
                    key={trigger.id}
                    type="button"
                    onClick={() => setSelectedTriggerId(trigger.id)}
                    className={`w-full rounded-md border px-3 py-2 text-left ${selectedTriggerId === trigger.id ? 'border-foreground bg-muted/60' : 'border-border bg-background/70'}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-medium">{trigger.name}</span>
                      <span className="text-[11px] text-muted-foreground">{trigger.enabled ? 'Enabled' : 'Disabled'}</span>
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">{sourceSummary(trigger)}</div>
                  </button>
                ))}
                {customTriggers.length === 0 ? <p className="text-xs text-muted-foreground">No custom triggers yet.</p> : null}
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <div className="rounded-md border border-border bg-card p-4 shadow-sm">
              <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Create trigger</div>
              <TriggerEditor
                form={newTriggerForm}
                onChange={setNewTriggerForm}
                mode="create"
                protectedTrigger={false}
              />
              <div className="mt-4 flex justify-end">
                <button
                  type="button"
                  data-testid="trigger-create-button"
                  onClick={() => void onCreateTrigger()}
                  className="rounded border border-border px-3 py-2 text-sm hover:bg-muted"
                >
                  Create trigger
                </button>
              </div>
            </div>

            <div className="rounded-md border border-border bg-card p-4 shadow-sm">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Selected trigger</div>
                  <div className="text-sm text-muted-foreground">
                    {selectedTrigger ? selectedTrigger.id : 'Select a trigger to inspect and edit it.'}
                  </div>
                </div>
                {selectedTrigger && !selectedTrigger.protected ? (
                  <button
                    type="button"
                    data-testid="trigger-delete-button"
                    onClick={() => void onDeleteSelectedTrigger()}
                    className="rounded border border-destructive/40 px-2 py-1 text-xs text-destructive hover:bg-destructive/10"
                  >
                    Delete
                  </button>
                ) : null}
              </div>

              {selectedTrigger && editTriggerForm ? (
                <>
                  <TriggerEditor
                    form={editTriggerForm}
                    onChange={setEditTriggerForm}
                    mode="edit"
                    protectedTrigger={selectedTrigger.protected}
                  />

                  {selectedTrigger.source_type === 'webhook' ? (
                    <div className="mt-4 space-y-2 rounded-md border border-border bg-background/70 p-3 text-sm">
                      <div className="font-medium text-foreground">Shared webhook ingress</div>
                      <div className="text-muted-foreground">
                        POST JSON to <code>{SHARED_WEBHOOK_ENDPOINT}</code> with:
                      </div>
                      <div className="font-mono text-xs text-foreground">
                        X-Spark-Webhook-Key: {String(selectedTrigger.source.webhook_key ?? '')}
                      </div>
                      <div className="font-mono text-xs text-foreground">
                        X-Spark-Webhook-Secret: {revealedWebhookSecrets[selectedTrigger.id] ?? 'Hidden after creation'}
                      </div>
                      <button
                        type="button"
                        data-testid="trigger-regenerate-secret-button"
                        onClick={() => void onRegenerateWebhookSecret()}
                        className="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                      >
                        Regenerate secret
                      </button>
                    </div>
                  ) : null}

                  <div className="mt-4 grid gap-3 lg:grid-cols-2">
                    <div className="rounded-md border border-border bg-background/70 p-3 text-sm">
                      <div className="font-medium text-foreground">Runtime</div>
                      <div className="mt-2 text-muted-foreground">Last fired: {formatTimestamp(selectedTrigger.state.last_fired_at)}</div>
                      <div className="text-muted-foreground">Next run: {formatTimestamp(selectedTrigger.state.next_run_at)}</div>
                      <div className="text-muted-foreground">Last result: {selectedTrigger.state.last_result ?? 'Never'}</div>
                      {selectedTrigger.state.last_error ? (
                        <div className="mt-2 text-destructive">{selectedTrigger.state.last_error}</div>
                      ) : null}
                    </div>
                    <div className="rounded-md border border-border bg-background/70 p-3 text-sm">
                      <div className="font-medium text-foreground">Recent history</div>
                      <div className="mt-2 space-y-2">
                        {selectedTrigger.state.recent_history.slice(0, 5).map((entry) => (
                          <div key={`${entry.timestamp}-${entry.status}`} className="rounded border border-border/70 px-2 py-1">
                            <div className="text-xs text-foreground">{entry.status}</div>
                            <div className="text-xs text-muted-foreground">{formatTimestamp(entry.timestamp)}</div>
                            <div className="text-xs text-muted-foreground">{entry.message}</div>
                          </div>
                        ))}
                        {selectedTrigger.state.recent_history.length === 0 ? (
                          <div className="text-xs text-muted-foreground">No trigger history yet.</div>
                        ) : null}
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 flex justify-end">
                    <button
                      type="button"
                      data-testid="trigger-save-button"
                      onClick={() => void onSaveSelectedTrigger()}
                      className="rounded border border-border px-3 py-2 text-sm hover:bg-muted"
                    >
                      Save trigger
                    </button>
                  </div>
                </>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

function TriggerEditor({
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
        <label className="space-y-1 text-sm">
          <span className="text-xs font-medium text-foreground">Name</span>
          <input
            value={form.name}
            onChange={(event) => onChange({ ...form, name: event.target.value })}
            className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
          />
        </label>
        <label className="space-y-1 text-sm">
          <span className="text-xs font-medium text-foreground">Target Flow</span>
          <input
            value={form.flowName}
            onChange={(event) => onChange({ ...form, flowName: event.target.value })}
            className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm font-mono"
          />
        </label>
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        <label className="space-y-1 text-sm">
          <span className="text-xs font-medium text-foreground">Source Type</span>
          <select
            value={form.sourceType}
            onChange={(event) => onChange({ ...form, sourceType: event.target.value as TriggerSourceType })}
            disabled={sourceTypeDisabled}
            className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
          >
            <option value="schedule">Schedule</option>
            <option value="poll">Poll</option>
            <option value="webhook">Webhook</option>
            <option value="flow_event">Flow Event</option>
            {protectedTrigger ? <option value="workspace_event">Workspace Event</option> : null}
          </select>
        </label>
        <label className="space-y-1 text-sm">
          <span className="text-xs font-medium text-foreground">Project Target</span>
          <input
            value={form.projectPath}
            onChange={(event) => onChange({ ...form, projectPath: event.target.value })}
            disabled={protectedTrigger}
            className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
          />
        </label>
        <label className="flex items-end gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.enabled}
            onChange={(event) => onChange({ ...form, enabled: event.target.checked })}
            className="h-4 w-4"
          />
          <span className="text-xs font-medium text-foreground">Enabled</span>
        </label>
      </div>

      {form.sourceType === 'schedule' ? (
        <>
          <div className="grid gap-3 lg:grid-cols-2">
            <label className="space-y-1 text-sm">
              <span className="text-xs font-medium text-foreground">Schedule Kind</span>
              <select
                value={form.scheduleKind}
                onChange={(event) => onChange({ ...form, scheduleKind: event.target.value as 'once' | 'interval' | 'weekly' })}
                className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
              >
                <option value="interval">Interval</option>
                <option value="once">One Shot</option>
                <option value="weekly">Weekly</option>
              </select>
            </label>
            {form.scheduleKind === 'interval' ? (
              <label className="space-y-1 text-sm">
                <span className="text-xs font-medium text-foreground">Interval Seconds</span>
                <input
                  value={form.scheduleIntervalSeconds}
                  onChange={(event) => onChange({ ...form, scheduleIntervalSeconds: event.target.value })}
                  className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
                />
              </label>
            ) : null}
            {form.scheduleKind === 'once' ? (
              <label className="space-y-1 text-sm lg:col-span-2">
                <span className="text-xs font-medium text-foreground">Run At (ISO UTC)</span>
                <input
                  value={form.scheduleRunAt}
                  onChange={(event) => onChange({ ...form, scheduleRunAt: event.target.value })}
                  className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm font-mono"
                  placeholder="2026-03-22T15:00:00Z"
                />
              </label>
            ) : null}
            {form.scheduleKind === 'weekly' ? (
              <>
                <label className="space-y-1 text-sm">
                  <span className="text-xs font-medium text-foreground">Weekdays</span>
                  <input
                    value={form.scheduleWeekdays}
                    onChange={(event) => onChange({ ...form, scheduleWeekdays: event.target.value })}
                    className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
                    placeholder="mon,wed,fri"
                  />
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <label className="space-y-1 text-sm">
                    <span className="text-xs font-medium text-foreground">Hour</span>
                    <input
                      value={form.scheduleHour}
                      onChange={(event) => onChange({ ...form, scheduleHour: event.target.value })}
                      className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-xs font-medium text-foreground">Minute</span>
                    <input
                      value={form.scheduleMinute}
                      onChange={(event) => onChange({ ...form, scheduleMinute: event.target.value })}
                      className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
                    />
                  </label>
                </div>
              </>
            ) : null}
          </div>
        </>
      ) : null}

      {form.sourceType === 'poll' ? (
        <div className="grid gap-3 lg:grid-cols-2">
          <label className="space-y-1 text-sm lg:col-span-2">
            <span className="text-xs font-medium text-foreground">Poll URL</span>
            <input
              value={form.pollUrl}
              onChange={(event) => onChange({ ...form, pollUrl: event.target.value })}
              className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm font-mono"
            />
          </label>
          <label className="space-y-1 text-sm">
            <span className="text-xs font-medium text-foreground">Interval Seconds</span>
            <input
              value={form.pollIntervalSeconds}
              onChange={(event) => onChange({ ...form, pollIntervalSeconds: event.target.value })}
              className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
            />
          </label>
          <label className="space-y-1 text-sm">
            <span className="text-xs font-medium text-foreground">Items Path</span>
            <input
              value={form.pollItemsPath}
              onChange={(event) => onChange({ ...form, pollItemsPath: event.target.value })}
              className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
            />
          </label>
          <label className="space-y-1 text-sm">
            <span className="text-xs font-medium text-foreground">Item ID Path</span>
            <input
              value={form.pollItemIdPath}
              onChange={(event) => onChange({ ...form, pollItemIdPath: event.target.value })}
              className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
            />
          </label>
          <label className="space-y-1 text-sm lg:col-span-2">
            <span className="text-xs font-medium text-foreground">Headers JSON</span>
            <textarea
              value={form.pollHeadersText}
              onChange={(event) => onChange({ ...form, pollHeadersText: event.target.value })}
              className="min-h-24 w-full rounded-md border border-input bg-background px-2 py-2 font-mono text-xs"
            />
          </label>
        </div>
      ) : null}

      {form.sourceType === 'flow_event' ? (
        <div className="grid gap-3 lg:grid-cols-2">
          <label className="space-y-1 text-sm">
            <span className="text-xs font-medium text-foreground">Observed Flow</span>
            <input
              value={form.flowEventFlowName}
              onChange={(event) => onChange({ ...form, flowEventFlowName: event.target.value })}
              className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm font-mono"
              placeholder="Leave blank for any observed flow"
            />
          </label>
          <label className="space-y-1 text-sm">
            <span className="text-xs font-medium text-foreground">Terminal Statuses</span>
            <input
              value={form.flowEventStatuses}
              onChange={(event) => onChange({ ...form, flowEventStatuses: event.target.value })}
              className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
              placeholder="success,failed"
            />
          </label>
        </div>
      ) : null}

      {form.sourceType === 'webhook' ? (
        <div className="rounded-md border border-border bg-background/70 px-3 py-2 text-sm text-muted-foreground">
          Webhook triggers use the shared ingress endpoint at <code>{SHARED_WEBHOOK_ENDPOINT}</code>. The key and secret are generated automatically.
        </div>
      ) : null}

      <label className="space-y-1 text-sm">
        <span className="text-xs font-medium text-foreground">Static Context JSON</span>
        <textarea
          value={form.staticContextText}
          onChange={(event) => onChange({ ...form, staticContextText: event.target.value })}
          disabled={protectedTrigger}
          className="min-h-24 w-full rounded-md border border-input bg-background px-2 py-2 font-mono text-xs disabled:cursor-not-allowed disabled:opacity-60"
        />
      </label>
    </div>
  )
}
