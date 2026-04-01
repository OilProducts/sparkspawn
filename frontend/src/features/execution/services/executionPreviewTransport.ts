import {
    fetchFlowPayloadValidated,
    fetchPipelineGraphPreviewValidated,
    fetchPreviewValidated,
    type PreviewResponsePayload,
} from '@/lib/attractorClient'

export type ExecutionPreviewResponse = PreviewResponsePayload

export const loadExecutionFlowPayload = fetchFlowPayloadValidated
export const loadExecutionFlowPreview = fetchPreviewValidated
export const loadExecutionRunGraphPreview = fetchPipelineGraphPreviewValidated
