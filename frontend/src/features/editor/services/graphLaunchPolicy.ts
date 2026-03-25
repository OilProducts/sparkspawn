import {
    fetchWorkspaceFlowValidated,
    updateWorkspaceFlowLaunchPolicyValidated,
    type FlowLaunchPolicy,
} from '@/lib/workspaceClient'

export type { FlowLaunchPolicy }

export const loadGraphLaunchPolicy = (flowName: string) => (
    fetchWorkspaceFlowValidated(flowName, 'human')
)

export const saveGraphLaunchPolicy = updateWorkspaceFlowLaunchPolicyValidated
