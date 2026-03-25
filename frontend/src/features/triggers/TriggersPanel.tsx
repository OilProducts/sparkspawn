import { useState } from "react"

import { TriggerEditor } from "./components/TriggerEditor"
import {
  formatTriggerTimestamp,
  SHARED_WEBHOOK_ENDPOINT,
  triggerSourceSummary,
} from "./model/triggerForm"
import { useTriggersList } from "./hooks/useTriggersList"
import { useTriggerEditor } from "./hooks/useTriggerEditor"
import { useWebhookSecretRegeneration } from "./hooks/useWebhookSecretRegeneration"
import { Button, EmptyState, InlineNotice, Panel, PanelContent, PanelHeader, PanelTitle, SectionHeader } from "@/ui"

export function TriggersPanel() {
  const [revealedWebhookSecrets, setRevealedWebhookSecrets] = useState<Record<string, string>>({})
  const {
    customTriggers,
    error,
    loading,
    refreshTriggers,
    selectedTrigger,
    selectedTriggerId,
    setError,
    setSelectedTriggerId,
    systemTriggers,
  } = useTriggersList()
  const {
    editTriggerForm,
    newTriggerForm,
    onCreateTrigger,
    onDeleteSelectedTrigger,
    onSaveSelectedTrigger,
    setEditTriggerForm,
    setNewTriggerForm,
  } = useTriggerEditor({
    refreshTriggers,
    selectedTrigger,
    setError,
    setRevealedWebhookSecrets,
    setSelectedTriggerId,
  })
  const { isRegenerating, onRegenerateWebhookSecret } = useWebhookSecretRegeneration({
    refreshTriggers,
    selectedTrigger,
    setError,
    setRevealedWebhookSecrets,
  })

  return (
    <section data-testid="triggers-panel" className="flex-1 overflow-auto p-6">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
        <SectionHeader
          title="Triggers"
          description="Manage system routing, schedules, polling, flow-event automation, and shared webhook ingress."
        />

        {error ? (
          <InlineNotice tone="error">
            {error}
          </InlineNotice>
        ) : null}

        <div className="grid gap-6 lg:grid-cols-[minmax(20rem,26rem)_minmax(0,1fr)]">
          <div className="space-y-4">
            <Panel>
              <PanelHeader className="flex flex-row items-center justify-between gap-2">
                <div>
                  <PanelTitle>System triggers</PanelTitle>
                  <div className="text-sm text-muted-foreground">Protected approval and review routing.</div>
                </div>
                <Button
                  type="button"
                  onClick={() => void refreshTriggers()}
                  variant="outline"
                  size="xs"
                >
                  {loading ? 'Refreshing…' : 'Refresh'}
                </Button>
              </PanelHeader>
              <PanelContent className="space-y-2 pt-0">
                {systemTriggers.map((trigger) => (
                  <Button
                    key={trigger.id}
                    type="button"
                    data-testid={`trigger-row-${trigger.id}`}
                    onClick={() => setSelectedTriggerId(trigger.id)}
                    variant="outline"
                    className={`h-auto w-full justify-start rounded-md px-3 py-2 text-left ${selectedTriggerId === trigger.id ? 'border-foreground bg-muted/60' : 'border-border bg-background/70'}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-medium">{trigger.name}</span>
                      <span className="text-[11px] text-muted-foreground">{trigger.enabled ? 'Enabled' : 'Disabled'}</span>
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">{triggerSourceSummary(trigger)}</div>
                  </Button>
                ))}
                {systemTriggers.length === 0 ? <EmptyState className="text-xs" description="No protected triggers configured." /> : null}
              </PanelContent>
            </Panel>

            <Panel>
              <PanelHeader>
                <PanelTitle>Custom triggers</PanelTitle>
              </PanelHeader>
              <PanelContent className="space-y-2 pt-0">
                {customTriggers.map((trigger) => (
                  <Button
                    key={trigger.id}
                    type="button"
                    onClick={() => setSelectedTriggerId(trigger.id)}
                    variant="outline"
                    className={`h-auto w-full justify-start rounded-md px-3 py-2 text-left ${selectedTriggerId === trigger.id ? 'border-foreground bg-muted/60' : 'border-border bg-background/70'}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-medium">{trigger.name}</span>
                      <span className="text-[11px] text-muted-foreground">{trigger.enabled ? 'Enabled' : 'Disabled'}</span>
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">{triggerSourceSummary(trigger)}</div>
                  </Button>
                ))}
                {customTriggers.length === 0 ? <EmptyState className="text-xs" description="No custom triggers yet." /> : null}
              </PanelContent>
            </Panel>
          </div>

          <div className="space-y-6">
            <Panel>
              <PanelHeader>
                <PanelTitle>Create trigger</PanelTitle>
              </PanelHeader>
              <PanelContent className="pt-0">
              <TriggerEditor
                form={newTriggerForm}
                onChange={setNewTriggerForm}
                mode="create"
                protectedTrigger={false}
              />
              <div className="mt-4 flex justify-end">
                <Button
                  type="button"
                  data-testid="trigger-create-button"
                  onClick={() => void onCreateTrigger()}
                >
                  Create trigger
                </Button>
              </div>
              </PanelContent>
            </Panel>

            <Panel>
              <PanelHeader className="flex flex-row items-center justify-between gap-2">
                <div>
                  <PanelTitle>Selected trigger</PanelTitle>
                  <div className="text-sm text-muted-foreground">
                    {selectedTrigger ? selectedTrigger.id : 'Select a trigger to inspect and edit it.'}
                  </div>
                </div>
                {selectedTrigger && !selectedTrigger.protected ? (
                  <Button
                    type="button"
                    data-testid="trigger-delete-button"
                    onClick={() => void onDeleteSelectedTrigger()}
                    variant="outline"
                    size="xs"
                    className="border-destructive/40 text-destructive hover:bg-destructive/10"
                  >
                    Delete
                  </Button>
                ) : null}
              </PanelHeader>

              {selectedTrigger && editTriggerForm ? (
                <PanelContent className="pt-0">
                  <TriggerEditor
                    form={editTriggerForm}
                    onChange={setEditTriggerForm}
                    mode="edit"
                    protectedTrigger={selectedTrigger.protected}
                  />

                  {selectedTrigger.source_type === 'webhook' ? (
                    <div className="mt-4 space-y-2 rounded-md border border-border bg-background/70 p-3 text-sm">
                      <div className="font-medium text-foreground">Shared webhook ingress</div>
                      <div className="text-muted-foreground">POST JSON to <code>{SHARED_WEBHOOK_ENDPOINT}</code> with:</div>
                      <div className="font-mono text-xs text-foreground">
                        X-Spark-Webhook-Key: {String(selectedTrigger.source.webhook_key ?? '')}
                      </div>
                      <div className="font-mono text-xs text-foreground">
                        X-Spark-Webhook-Secret: {revealedWebhookSecrets[selectedTrigger.id] ?? 'Hidden after creation'}
                      </div>
                      <Button
                        type="button"
                        data-testid="trigger-regenerate-secret-button"
                        onClick={() => void onRegenerateWebhookSecret()}
                        variant="outline"
                        size="xs"
                      >
                        {isRegenerating ? 'Regenerating…' : 'Regenerate secret'}
                      </Button>
                    </div>
                  ) : null}

                  <div className="mt-4 grid gap-3 lg:grid-cols-2">
                    <div className="rounded-md border border-border bg-background/70 p-3 text-sm">
                      <div className="font-medium text-foreground">Runtime</div>
                      <div className="mt-2 text-muted-foreground">Last fired: {formatTriggerTimestamp(selectedTrigger.state.last_fired_at)}</div>
                      <div className="text-muted-foreground">Next run: {formatTriggerTimestamp(selectedTrigger.state.next_run_at)}</div>
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
                            <div className="text-xs text-muted-foreground">{formatTriggerTimestamp(entry.timestamp)}</div>
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
                    <Button
                      type="button"
                      data-testid="trigger-save-button"
                      onClick={() => void onSaveSelectedTrigger()}
                    >
                      Save trigger
                    </Button>
                  </div>
                </PanelContent>
              ) : null}
            </Panel>
          </div>
        </div>
      </div>
    </section>
  )
}
