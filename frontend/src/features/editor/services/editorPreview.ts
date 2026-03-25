import {
    fetchFlowPayloadValidated,
    fetchPreviewValidated,
    type PreviewResponsePayload,
} from '@/lib/attractorClient'

export type EditorPreviewResponse = PreviewResponsePayload

export const loadEditorFlowPayload = fetchFlowPayloadValidated
export const loadEditorPreview = fetchPreviewValidated
