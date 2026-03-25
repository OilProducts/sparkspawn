import { useStore } from "@/store"
import { getModelSuggestions, LLM_PROVIDER_OPTIONS } from "@/lib/llmSuggestions"
import { FieldRow, Input, NativeSelect, Panel, PanelContent, PanelHeader, PanelTitle, SectionHeader } from "@/ui"

export function SettingsPanel() {
    const uiDefaults = useStore((state) => state.uiDefaults)
    const setUiDefault = useStore((state) => state.setUiDefault)

    return (
        <div data-testid="settings-panel" className="flex-1 overflow-auto p-6">
            <div className="mx-auto w-full max-w-2xl space-y-6">
                <SectionHeader
                    title="Settings"
                    description="Global defaults apply to new flows and are snapshotted per flow."
                />

                <Panel>
                    <PanelHeader>
                        <PanelTitle>LLM Defaults (Global)</PanelTitle>
                    </PanelHeader>
                    <PanelContent className="space-y-3 pt-0">
                        <FieldRow label="Default LLM Provider" htmlFor="settings-default-llm-provider">
                            <Input
                                id="settings-default-llm-provider"
                                value={uiDefaults.llm_provider}
                                onChange={(event) => setUiDefault('llm_provider', event.target.value)}
                                list="settings-llm-provider-options"
                                className="text-xs"
                                placeholder="openai"
                            />
                            <datalist id="settings-llm-provider-options">
                                {LLM_PROVIDER_OPTIONS.map((provider) => (
                                    <option key={provider} value={provider} />
                                ))}
                            </datalist>
                        </FieldRow>
                        <FieldRow label="Default LLM Model" htmlFor="settings-default-llm-model">
                            <Input
                                id="settings-default-llm-model"
                                value={uiDefaults.llm_model}
                                onChange={(event) => setUiDefault('llm_model', event.target.value)}
                                list="settings-llm-model-options"
                                className="text-xs"
                                placeholder="gpt-5.2"
                            />
                            <datalist id="settings-llm-model-options">
                                {getModelSuggestions(uiDefaults.llm_provider).map((modelOption) => (
                                    <option key={modelOption} value={modelOption} />
                                ))}
                            </datalist>
                        </FieldRow>
                        <FieldRow label="Default Reasoning Effort" htmlFor="settings-default-reasoning-effort">
                            <NativeSelect
                                id="settings-default-reasoning-effort"
                                value={uiDefaults.reasoning_effort}
                                onChange={(event) => setUiDefault('reasoning_effort', event.target.value)}
                                className="text-xs"
                            >
                                <option value="">Use handler default</option>
                                <option value="low">Low</option>
                                <option value="medium">Medium</option>
                                <option value="high">High</option>
                            </NativeSelect>
                        </FieldRow>
                    </PanelContent>
                </Panel>
            </div>
        </div>
    )
}
