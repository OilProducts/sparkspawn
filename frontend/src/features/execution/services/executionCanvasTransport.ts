import {
    fetchFlowPayloadValidated,
    fetchPreviewValidated,
    type PreviewResponsePayload,
} from '@/lib/attractorClient'

export type ExecutionCanvasPreviewResponse = PreviewResponsePayload

export const loadExecutionFlowPayload = fetchFlowPayloadValidated
export const loadExecutionCanvasPreview = fetchPreviewValidated
