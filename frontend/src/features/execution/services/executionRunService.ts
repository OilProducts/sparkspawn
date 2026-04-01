import {
    ApiHttpError,
    fetchFlowPayloadValidated,
    fetchPipelineCancelValidated,
    fetchPipelineContinueValidated,
    fetchPipelineStartValidated,
} from '@/lib/attractorClient'
import { fetchProjectMetadataValidated } from '@/lib/workspaceClient'

export { ApiHttpError }

export const cancelExecutionRun = fetchPipelineCancelValidated
export const continueExecutionRun = fetchPipelineContinueValidated
export const loadExecutionFlowPayload = fetchFlowPayloadValidated
export const loadExecutionProjectMetadata = fetchProjectMetadataValidated
export const startExecutionRun = fetchPipelineStartValidated
