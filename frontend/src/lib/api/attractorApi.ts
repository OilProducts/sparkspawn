import type { CanonicalPreviewGraphPayload } from '@/lib/canonicalFlowModel'
import {
    ApiSchemaError,
    asOptionalNullableString,
    asOptionalString,
    asOptionalStringArray,
    asUnknownRecord,
    expectObjectRecord,
    expectString,
    fetchJsonWithValidation,
    fetchTextWithValidation,
    parseDiagnosticList,
} from './shared'

export interface FlowPayloadResponse {
    name: string
    content: string
}

export interface PreviewResponsePayload {
    status: string
    graph?: CanonicalPreviewGraphPayload
    diagnostics?: import('@/state/store-types').DiagnosticEntry[]
    errors?: import('@/state/store-types').DiagnosticEntry[]
    error?: string
}

export interface PipelineStartResponse {
    status: string
    pipeline_id?: string
    run_id?: string
    working_directory?: string
    model?: string
    diagnostics?: import('@/state/store-types').DiagnosticEntry[]
    errors?: import('@/state/store-types').DiagnosticEntry[]
    error?: string
}

export interface PipelineStatusResponse {
    pipeline_id: string
    status: string
    flow_name?: string
    working_directory?: string
    model?: string
    last_error?: string | null
    completed_nodes?: string[]
    started_at?: string
    ended_at?: string | null
    result?: string | null
}

export interface PipelineCancelResponse {
    status: string
    pipeline_id: string
}

export interface PipelineCheckpointResponse {
    pipeline_id: string
    checkpoint: Record<string, unknown>
}

export interface PipelineContextResponse {
    pipeline_id: string
    context: Record<string, unknown>
}

export interface PipelineQuestionsResponse {
    questions: Array<Record<string, unknown>>
}

export interface PipelineAnswerResponse {
    status: string
    pipeline_id: string
    question_id: string
}

export type PipelineGraphResponse = string

export interface RunRecordResponse {
    run_id: string
    flow_name: string
    status: string
    result?: string | null
    working_directory: string
    project_path?: string
    git_branch?: string | null
    git_commit?: string | null
    spec_id?: string | null
    plan_id?: string | null
    model: string
    started_at: string
    ended_at?: string | null
    last_error?: string
    token_usage?: number | null
}

export interface RunsListResponse {
    runs: RunRecordResponse[]
}

export interface RuntimeStatusResponse {
    status: string
    last_error?: string | null
    last_working_directory?: string | null
    last_model?: string | null
    last_completed_nodes?: string[] | null
    last_flow_name?: string | null
    last_run_id?: string | null
}

export function parseFlowListResponse(payload: unknown, endpoint = '/api/flows'): string[] {
    if (!Array.isArray(payload)) {
        throw new ApiSchemaError(endpoint, 'Expected an array of flow names.')
    }
    if (!payload.every((entry) => typeof entry === 'string')) {
        throw new ApiSchemaError(endpoint, 'Expected every flow name to be a string.')
    }
    return [...payload]
}

export function parseFlowPayloadResponse(payload: unknown, endpoint = '/api/flows/{name}'): FlowPayloadResponse {
    const record = expectObjectRecord(payload, endpoint)
    return {
        name: typeof record.name === 'string' ? record.name : '',
        content: expectString(record.content, endpoint, 'content'),
    }
}

export function parsePreviewResponse(payload: unknown, endpoint = '/preview'): PreviewResponsePayload {
    const record = expectObjectRecord(payload, endpoint)
    const status = typeof record.status === 'string' ? record.status : 'ok'
    const graphRecord = asUnknownRecord(record.graph)
    let graph: CanonicalPreviewGraphPayload | undefined
    if (graphRecord) {
        const nodes = graphRecord.nodes
        const edges = graphRecord.edges
        if (!Array.isArray(nodes) || !Array.isArray(edges)) {
            throw new ApiSchemaError(endpoint, 'Expected "graph.nodes" and "graph.edges" to be arrays.')
        }
        const normalizedNodes = nodes
            .map((node) => asUnknownRecord(node))
            .filter((node): node is Record<string, unknown> => node !== null)
        const normalizedEdges = edges
            .map((edge) => asUnknownRecord(edge))
            .filter((edge): edge is Record<string, unknown> => edge !== null)
        graph = {
            nodes: normalizedNodes,
            edges: normalizedEdges,
            graph_attrs: asUnknownRecord(graphRecord.graph_attrs),
            defaults: asUnknownRecord(graphRecord.defaults),
            subgraphs: Array.isArray(graphRecord.subgraphs) ? graphRecord.subgraphs : undefined,
        }
    }
    return {
        status,
        graph,
        diagnostics: parseDiagnosticList(record.diagnostics, endpoint, 'diagnostics'),
        errors: parseDiagnosticList(record.errors, endpoint, 'errors'),
        error: asOptionalString(record.error),
    }
}

export function parsePipelineStartResponse(payload: unknown, endpoint = '/pipelines'): PipelineStartResponse {
    const record = expectObjectRecord(payload, endpoint)
    return {
        status: expectString(record.status, endpoint, 'status'),
        pipeline_id: asOptionalString(record.pipeline_id),
        run_id: asOptionalString(record.run_id),
        working_directory: asOptionalString(record.working_directory),
        model: asOptionalString(record.model),
        diagnostics: parseDiagnosticList(record.diagnostics, endpoint, 'diagnostics'),
        errors: parseDiagnosticList(record.errors, endpoint, 'errors'),
        error: asOptionalString(record.error),
    }
}

export function parsePipelineStatusResponse(payload: unknown, endpoint = '/pipelines/{id}'): PipelineStatusResponse {
    const record = expectObjectRecord(payload, endpoint)
    return {
        pipeline_id: expectString(record.pipeline_id, endpoint, 'pipeline_id'),
        status: expectString(record.status, endpoint, 'status'),
        flow_name: asOptionalString(record.flow_name),
        working_directory: asOptionalString(record.working_directory),
        model: asOptionalString(record.model),
        last_error: asOptionalNullableString(record.last_error),
        completed_nodes: asOptionalStringArray(record.completed_nodes),
        started_at: asOptionalString(record.started_at),
        ended_at: asOptionalNullableString(record.ended_at),
        result: asOptionalNullableString(record.result),
    }
}

export function parsePipelineCancelResponse(payload: unknown, endpoint = '/pipelines/{id}/cancel'): PipelineCancelResponse {
    const record = expectObjectRecord(payload, endpoint)
    return {
        status: expectString(record.status, endpoint, 'status'),
        pipeline_id: expectString(record.pipeline_id, endpoint, 'pipeline_id'),
    }
}

export function parsePipelineCheckpointResponse(
    payload: unknown,
    endpoint = '/pipelines/{id}/checkpoint',
): PipelineCheckpointResponse {
    const record = expectObjectRecord(payload, endpoint)
    return {
        pipeline_id: expectString(record.pipeline_id, endpoint, 'pipeline_id'),
        checkpoint: expectObjectRecord(record.checkpoint, endpoint),
    }
}

export function parsePipelineContextResponse(payload: unknown, endpoint = '/pipelines/{id}/context'): PipelineContextResponse {
    const record = expectObjectRecord(payload, endpoint)
    return {
        pipeline_id: expectString(record.pipeline_id, endpoint, 'pipeline_id'),
        context: expectObjectRecord(record.context, endpoint),
    }
}

export function parsePipelineQuestionsResponse(
    payload: unknown,
    endpoint = '/pipelines/{id}/questions',
): PipelineQuestionsResponse {
    const record = expectObjectRecord(payload, endpoint)
    const rawQuestions = record.questions
    if (!Array.isArray(rawQuestions)) {
        throw new ApiSchemaError(endpoint, 'Expected "questions" to be an array.')
    }
    return {
        questions: rawQuestions
            .map((question) => asUnknownRecord(question))
            .filter((question): question is Record<string, unknown> => question !== null),
    }
}

export function parsePipelineAnswerResponse(
    payload: unknown,
    endpoint = '/pipelines/{id}/questions/{qid}/answer',
): PipelineAnswerResponse {
    const record = expectObjectRecord(payload, endpoint)
    return {
        status: expectString(record.status, endpoint, 'status'),
        pipeline_id: expectString(record.pipeline_id, endpoint, 'pipeline_id'),
        question_id: expectString(record.question_id, endpoint, 'question_id'),
    }
}

export function parsePipelineGraphResponse(payload: unknown, endpoint = '/pipelines/{id}/graph'): PipelineGraphResponse {
    if (typeof payload !== 'string') {
        throw new ApiSchemaError(endpoint, 'Expected SVG/text response body.')
    }
    if (payload.trim().length === 0) {
        throw new ApiSchemaError(endpoint, 'Expected non-empty SVG/text response body.')
    }
    return payload
}

function parseRunRecord(payload: unknown): RunRecordResponse | null {
    const record = asUnknownRecord(payload)
    if (!record) {
        return null
    }
    if (typeof record.run_id !== 'string' || typeof record.status !== 'string') {
        return null
    }
    return {
        run_id: record.run_id,
        flow_name: typeof record.flow_name === 'string' ? record.flow_name : '',
        status: record.status,
        result: asOptionalNullableString(record.result),
        working_directory: typeof record.working_directory === 'string' ? record.working_directory : '',
        project_path: asOptionalString(record.project_path),
        git_branch: asOptionalNullableString(record.git_branch),
        git_commit: asOptionalNullableString(record.git_commit),
        spec_id: asOptionalNullableString(record.spec_id),
        plan_id: asOptionalNullableString(record.plan_id),
        model: typeof record.model === 'string' ? record.model : '',
        started_at: typeof record.started_at === 'string' ? record.started_at : '',
        ended_at: asOptionalNullableString(record.ended_at),
        last_error: asOptionalString(record.last_error),
        token_usage: typeof record.token_usage === 'number'
            ? record.token_usage
            : record.token_usage === null
                ? null
                : undefined,
    }
}

export function parseRunsListResponse(payload: unknown, endpoint = '/runs'): RunsListResponse {
    const record = expectObjectRecord(payload, endpoint)
    if (!Array.isArray(record.runs)) {
        throw new ApiSchemaError(endpoint, 'Expected "runs" to be an array.')
    }
    return {
        runs: record.runs
            .map((run) => parseRunRecord(run))
            .filter((run): run is RunRecordResponse => run !== null),
    }
}

export function parseRuntimeStatusResponse(payload: unknown, endpoint = '/status'): RuntimeStatusResponse {
    const record = expectObjectRecord(payload, endpoint)
    return {
        status: expectString(record.status, endpoint, 'status'),
        last_error: asOptionalNullableString(record.last_error),
        last_working_directory: asOptionalNullableString(record.last_working_directory),
        last_model: asOptionalNullableString(record.last_model),
        last_completed_nodes: asOptionalStringArray(record.last_completed_nodes) ?? null,
        last_flow_name: asOptionalNullableString(record.last_flow_name),
        last_run_id: asOptionalNullableString(record.last_run_id),
    }
}

export async function fetchFlowListValidated(): Promise<string[]> {
    return fetchJsonWithValidation('/api/flows', undefined, '/api/flows', parseFlowListResponse)
}

export async function fetchFlowPayloadValidated(flowName: string): Promise<FlowPayloadResponse> {
    const url = `/api/flows/${encodeURIComponent(flowName)}`
    return fetchJsonWithValidation(url, undefined, '/api/flows/{name}', parseFlowPayloadResponse)
}

export async function fetchPreviewValidated(flowContent: string): Promise<PreviewResponsePayload> {
    return fetchJsonWithValidation(
        '/preview',
        {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ flow_content: flowContent }),
        },
        '/preview',
        parsePreviewResponse,
    )
}

export async function fetchPipelineStartValidated(payload: Record<string, unknown>): Promise<PipelineStartResponse> {
    return fetchJsonWithValidation(
        '/pipelines',
        {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        },
        '/pipelines',
        parsePipelineStartResponse,
    )
}

export async function fetchPipelineStatusValidated(pipelineId: string): Promise<PipelineStatusResponse> {
    const url = `/pipelines/${encodeURIComponent(pipelineId)}`
    return fetchJsonWithValidation(url, undefined, '/pipelines/{id}', parsePipelineStatusResponse)
}

export async function fetchPipelineCancelValidated(pipelineId: string): Promise<PipelineCancelResponse> {
    const url = `/pipelines/${encodeURIComponent(pipelineId)}/cancel`
    return fetchJsonWithValidation(
        url,
        { method: 'POST' },
        '/pipelines/{id}/cancel',
        parsePipelineCancelResponse,
    )
}

export async function fetchPipelineCheckpointValidated(pipelineId: string): Promise<PipelineCheckpointResponse> {
    const url = `/pipelines/${encodeURIComponent(pipelineId)}/checkpoint`
    return fetchJsonWithValidation(url, undefined, '/pipelines/{id}/checkpoint', parsePipelineCheckpointResponse)
}

export async function fetchPipelineContextValidated(pipelineId: string): Promise<PipelineContextResponse> {
    const url = `/pipelines/${encodeURIComponent(pipelineId)}/context`
    return fetchJsonWithValidation(url, undefined, '/pipelines/{id}/context', parsePipelineContextResponse)
}

export async function fetchPipelineQuestionsValidated(pipelineId: string): Promise<PipelineQuestionsResponse> {
    const url = `/pipelines/${encodeURIComponent(pipelineId)}/questions`
    return fetchJsonWithValidation(url, undefined, '/pipelines/{id}/questions', parsePipelineQuestionsResponse)
}

export async function fetchPipelineAnswerValidated(
    pipelineId: string,
    questionId: string,
    selectedValue: string,
): Promise<PipelineAnswerResponse> {
    const url = `/pipelines/${encodeURIComponent(pipelineId)}/questions/${encodeURIComponent(questionId)}/answer`
    return fetchJsonWithValidation(
        url,
        {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question_id: questionId,
                selected_value: selectedValue,
            }),
        },
        '/pipelines/{id}/questions/{qid}/answer',
        parsePipelineAnswerResponse,
    )
}

export async function fetchPipelineGraphValidated(pipelineId: string): Promise<PipelineGraphResponse> {
    const url = `/pipelines/${encodeURIComponent(pipelineId)}/graph`
    return fetchTextWithValidation(url, undefined, '/pipelines/{id}/graph', parsePipelineGraphResponse)
}

export async function fetchRunsListValidated(): Promise<RunsListResponse> {
    return fetchJsonWithValidation('/runs', undefined, '/runs', parseRunsListResponse)
}

export async function fetchRuntimeStatusValidated(): Promise<RuntimeStatusResponse> {
    return fetchJsonWithValidation('/status', undefined, '/status', parseRuntimeStatusResponse)
}
