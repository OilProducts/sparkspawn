export interface RunInitiationFormState {
    projectPath: string
    flowSource: string
    workingDirectory: string
    backend: string
    model: string | null
}

export interface PipelineStartPayload {
    flow_content: string
    working_directory: string
    backend: string
    model: string | null
    flow_name: string | null
}

export function buildPipelineStartPayload(
    form: RunInitiationFormState,
    flowContent: string,
): PipelineStartPayload {
    return {
        flow_content: flowContent,
        working_directory: form.workingDirectory,
        backend: form.backend,
        model: form.model,
        flow_name: form.flowSource || null,
    }
}
