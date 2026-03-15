import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { RefreshCcw } from 'lucide-react'
import { useStore } from '@/store'
import {
    computeRunMetadataFreshness,
    formatRunMetadataLastUpdated,
    RUN_METADATA_STALE_AFTER_MS,
} from '@/lib/runMetadataFreshness'
import { useNarrowViewport } from '@/lib/useNarrowViewport'
import {
    ApiHttpError,
    fetchPipelineAnswerValidated,
    fetchPipelineCancelValidated,
    fetchPipelineCheckpointValidated,
    fetchPipelineContextValidated,
    fetchPipelineGraphValidated,
    fetchPipelineQuestionsValidated,
    fetchRunsListValidated,
    fetchPipelineArtifactsValidated,
    fetchPipelineArtifactPreviewValidated,
    pipelineArtifactHref,
    pipelineEventsUrl,
} from '@/lib/attractorClient'
import { RunArtifactsCard } from './runs/RunArtifactsCard'
import { RunCheckpointCard } from './runs/RunCheckpointCard'
import { RunContextCard } from './runs/RunContextCard'
import { RunEventTimelineCard } from './runs/RunEventTimelineCard'
import { RunGraphvizCard } from './runs/RunGraphvizCard'
import { RunList } from './runs/RunList'
import { RunSummaryCard } from './runs/RunSummaryCard'
import type {
    ArtifactErrorState,
    ArtifactListEntry,
    ArtifactListResponse,
    CheckpointErrorState,
    CheckpointResponse,
    ContextErrorState,
    ContextExportEntry,
    ContextResponse,
    FormattedContextValue,
    GraphvizErrorState,
    GroupedTimelineEntry,
    PendingInterviewGate,
    PendingInterviewGateGroup,
    PendingQuestionSnapshot,
    RunRecord,
    TimelineCorrelationDescriptor,
    TimelineEventCategory,
    TimelineEventEntry,
    TimelineSeverity,
} from './runs/shared'

const TIMELINE_EVENT_TYPES: Record<string, TimelineEventCategory> = {
    PipelineStarted: 'lifecycle',
    PipelineCompleted: 'lifecycle',
    PipelineFailed: 'lifecycle',
    StageStarted: 'stage',
    StageCompleted: 'stage',
    StageFailed: 'stage',
    StageRetrying: 'stage',
    ParallelStarted: 'parallel',
    ParallelBranchStarted: 'parallel',
    ParallelBranchCompleted: 'parallel',
    ParallelCompleted: 'parallel',
    InterviewStarted: 'interview',
    InterviewInform: 'interview',
    InterviewCompleted: 'interview',
    InterviewTimeout: 'interview',
    human_gate: 'interview',
    CheckpointSaved: 'checkpoint',
}

const TIMELINE_MAX_ITEMS = 200
const RETRY_CORRELATION_EVENT_TYPES = new Set(['StageStarted', 'StageFailed', 'StageRetrying', 'StageCompleted'])
const PENDING_GATE_FALLBACK_RECEIVED_AT = '1970-01-01T00:00:00Z'

const logUnexpectedRunError = (error: unknown) => {
    if (error instanceof ApiHttpError) {
        return
    }
    console.error(error)
}

const asRecord = (value: unknown): Record<string, unknown> | null => {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
        return null
    }
    return value as Record<string, unknown>
}

const asFiniteNumber = (value: unknown): number | null => {
    if (typeof value !== 'number' || !Number.isFinite(value)) {
        return null
    }
    return value
}

const checkpointErrorFromResponse = (status: number, detail: string | null): CheckpointErrorState => {
    const normalizedDetail = detail?.toLowerCase()
    if (status === 404 && normalizedDetail === 'checkpoint unavailable') {
        return {
            message: 'Checkpoint unavailable for this run.',
            help: 'Run may still be in progress or did not persist checkpoint data yet.',
        }
    }
    if (status === 404 && normalizedDetail === 'unknown pipeline') {
        return {
            message: 'Run is no longer available.',
            help: 'The selected run could not be found. Refresh run history and pick a different run.',
        }
    }
    return {
        message: `Unable to load checkpoint (HTTP ${status}).`,
        help: detail ? `Backend returned: ${detail}.` : 'Retry, and check backend availability if this keeps failing.',
    }
}

const contextErrorFromResponse = (status: number, detail: string | null): ContextErrorState => {
    const normalizedDetail = detail?.toLowerCase()
    if (status === 404 && normalizedDetail === 'context unavailable') {
        return {
            message: 'Context unavailable for this run.',
            help: 'Run may still be in progress or did not persist context data yet.',
        }
    }
    if (status === 404 && normalizedDetail === 'unknown pipeline') {
        return {
            message: 'Run is no longer available.',
            help: 'The selected run could not be found. Refresh run history and pick a different run.',
        }
    }
    return {
        message: `Unable to load context (HTTP ${status}).`,
        help: detail ? `Backend returned: ${detail}.` : 'Retry, and check backend availability if this keeps failing.',
    }
}

const artifactErrorFromResponse = (status: number, detail: string | null): ArtifactErrorState => {
    const normalizedDetail = detail?.toLowerCase()
    if (status === 404 && normalizedDetail === 'unknown pipeline') {
        return {
            message: 'Run is no longer available.',
            help: 'The selected run could not be found. Refresh run history and pick a different run.',
        }
    }
    return {
        message: `Unable to load artifacts (HTTP ${status}).`,
        help: detail ? `Backend returned: ${detail}.` : 'Retry, and check backend availability if this keeps failing.',
    }
}

const artifactPreviewErrorFromResponse = (status: number, detail: string | null): string => {
    const normalizedDetail = detail?.toLowerCase()
    if (status === 404 && normalizedDetail === 'artifact not found') {
        return 'Artifact preview unavailable because the file was not found for this run. This run may be partial or artifacts may have been pruned.'
    }
    if (status === 404 && normalizedDetail === 'unknown pipeline') {
        return 'Artifact preview unavailable because this run is no longer available. Refresh run history and pick a different run.'
    }
    return detail
        ? `Unable to load artifact preview (HTTP ${status}): ${detail}.`
        : `Unable to load artifact preview (HTTP ${status}).`
}

const graphvizErrorFromResponse = (status: number, detail: string | null): GraphvizErrorState => {
    const normalizedDetail = detail?.toLowerCase()
    if (status === 404 && normalizedDetail === 'unknown pipeline') {
        return {
            message: 'Run is no longer available.',
            help: 'The selected run could not be found. Refresh run history and pick a different run.',
        }
    }
    if (status === 404 && normalizedDetail === 'graph visualization unavailable') {
        return {
            message: 'Graph visualization unavailable for this run.',
            help: 'This run may not have produced a Graphviz SVG yet.',
        }
    }
    return {
        message: `Unable to load graph visualization (HTTP ${status}).`,
        help: detail ? `Backend returned: ${detail}.` : 'Retry, and check backend availability if this keeps failing.',
    }
}

const EXPECTED_CORE_ARTIFACT_PATHS = ['manifest.json', 'checkpoint.json']

const formatContextValue = (value: unknown): FormattedContextValue => {
    if (value === null) {
        return {
            renderedValue: 'null',
            valueType: 'null',
            renderKind: 'scalar',
        }
    }

    if (typeof value === 'string') {
        return {
            renderedValue: JSON.stringify(value),
            valueType: 'string',
            renderKind: 'scalar',
        }
    }

    if (typeof value === 'number' || typeof value === 'boolean') {
        return {
            renderedValue: String(value),
            valueType: typeof value,
            renderKind: 'scalar',
        }
    }

    const valueType = Array.isArray(value) ? 'array' : 'object'
    let renderedValue = ''
    try {
        renderedValue = JSON.stringify(value, null, 2) ?? String(value)
    } catch {
        renderedValue = String(value)
    }

    return {
        renderedValue,
        valueType,
        renderKind: 'structured',
    }
}

const buildContextExportPayload = (
    runId: string,
    contextEntries: ContextExportEntry[]
) => JSON.stringify(
    {
        pipeline_id: runId,
        exported_at: new Date().toISOString(),
        context: Object.fromEntries(contextEntries.map((entry) => [entry.key, entry.value])),
    },
    null,
    2
)

const timelineNodeIdFromEvent = (payload: Record<string, unknown>): string | null => {
    const candidates = [payload.node_id, payload.node, payload.name, payload.stage]
    for (const value of candidates) {
        if (typeof value === 'string' && value.trim().length > 0) {
            return value.trim()
        }
    }
    return null
}

const timelineSeverityFromEvent = (type: string, payload: Record<string, unknown>): TimelineSeverity => {
    const severityValue = typeof payload.severity === 'string'
        ? payload.severity
        : typeof payload.level === 'string'
            ? payload.level
            : ''
    const normalized = severityValue.trim().toLowerCase()
    if (normalized === 'info' || normalized === 'warning' || normalized === 'error') {
        return normalized
    }

    if (type === 'PipelineFailed' || type === 'StageFailed') {
        return 'error'
    }
    if (type === 'StageRetrying' || type === 'InterviewTimeout') {
        return 'warning'
    }
    return 'info'
}

type InterviewOutcomeProvenance = 'accepted' | 'skipped' | 'timeout_default_applied' | 'timeout_no_default' | null

const asTrimmedString = (value: unknown): string | null => {
    if (typeof value !== 'string') {
        return null
    }
    const trimmed = value.trim()
    return trimmed.length > 0 ? trimmed : null
}

const interviewOutcomeProvenanceFromPayload = (
    type: string,
    payload: Record<string, unknown>
): InterviewOutcomeProvenance => {
    const rawProvenance = asTrimmedString(payload.outcome_provenance) ?? asTrimmedString(payload.provenance)
    const normalizedProvenance = rawProvenance?.toLowerCase()
    if (
        normalizedProvenance === 'accepted'
        || normalizedProvenance === 'skipped'
        || normalizedProvenance === 'timeout_default_applied'
        || normalizedProvenance === 'timeout_no_default'
    ) {
        return normalizedProvenance
    }

    if (type === 'InterviewCompleted') {
        const answer = asTrimmedString(payload.answer)
        if (!answer) {
            return null
        }
        return answer.toLowerCase() === 'skipped' ? 'skipped' : 'accepted'
    }

    if (type === 'InterviewTimeout') {
        const defaultChoice = asTrimmedString(payload.default_choice_label)
            ?? asTrimmedString(payload.default_choice_target)
        return defaultChoice ? 'timeout_default_applied' : 'timeout_no_default'
    }

    return null
}

const interviewDefaultChoiceLabelFromPayload = (payload: Record<string, unknown>): string | null => (
    asTrimmedString(payload.default_choice_label)
    ?? asTrimmedString(payload.default_choice_target)
)

const timelineSummaryFromEvent = (type: string, payload: Record<string, unknown>, nodeId: string | null): string => {
    if (type === 'PipelineStarted') {
        return `Pipeline started at ${nodeId || 'start'}`
    }
    if (type === 'PipelineCompleted') {
        return `Pipeline completed at ${nodeId || 'exit'}`
    }
    if (type === 'PipelineFailed') {
        const error = typeof payload.error === 'string' && payload.error.trim().length > 0
            ? payload.error.trim()
            : null
        return error ? `Pipeline failed: ${error}` : 'Pipeline failed'
    }
    if (type === 'StageStarted') {
        return `Stage ${nodeId || 'unknown'} started`
    }
    if (type === 'StageCompleted') {
        const outcome = typeof payload.outcome === 'string' && payload.outcome.trim().length > 0
            ? payload.outcome.trim()
            : null
        return outcome
            ? `Stage ${nodeId || 'unknown'} completed (${outcome})`
            : `Stage ${nodeId || 'unknown'} completed`
    }
    if (type === 'StageFailed') {
        const error = typeof payload.error === 'string' && payload.error.trim().length > 0
            ? payload.error.trim()
            : null
        return error
            ? `Stage ${nodeId || 'unknown'} failed: ${error}`
            : `Stage ${nodeId || 'unknown'} failed`
    }
    if (type === 'StageRetrying') {
        const attempt = asFiniteNumber(payload.attempt)
        return attempt !== null
            ? `Stage ${nodeId || 'unknown'} retrying (attempt ${attempt})`
            : `Stage ${nodeId || 'unknown'} retrying`
    }
    if (type === 'ParallelStarted') {
        const branchCount = asFiniteNumber(payload.branch_count)
        return branchCount !== null ? `Parallel fan-out started (${branchCount} branches)` : 'Parallel fan-out started'
    }
    if (type === 'ParallelBranchStarted') {
        const branchName = typeof payload.branch === 'string' && payload.branch.trim().length > 0
            ? payload.branch.trim()
            : nodeId || 'unknown'
        return `Parallel branch ${branchName} started`
    }
    if (type === 'ParallelBranchCompleted') {
        const branchName = typeof payload.branch === 'string' && payload.branch.trim().length > 0
            ? payload.branch.trim()
            : nodeId || 'unknown'
        const success = payload.success === true ? 'success' : payload.success === false ? 'failed' : null
        return success
            ? `Parallel branch ${branchName} completed (${success})`
            : `Parallel branch ${branchName} completed`
    }
    if (type === 'ParallelCompleted') {
        const successCount = asFiniteNumber(payload.success_count)
        const failureCount = asFiniteNumber(payload.failure_count)
        if (successCount !== null && failureCount !== null) {
            return `Parallel fan-out completed (${successCount} success, ${failureCount} failed)`
        }
        return 'Parallel fan-out completed'
    }
    if (type === 'InterviewStarted') {
        return `Interview started for ${nodeId || 'human gate'}`
    }
    if (type === 'InterviewInform') {
        const message = asTrimmedString(payload.message)
            ?? asTrimmedString(payload.prompt)
            ?? asTrimmedString(payload.question)
        return message
            ? `Interview info for ${nodeId || 'human gate'}: ${message}`
            : `Interview info for ${nodeId || 'human gate'}`
    }
    if (type === 'InterviewCompleted') {
        const answer = asTrimmedString(payload.answer)
        const provenance = interviewOutcomeProvenanceFromPayload(type, payload)
        if (provenance === 'skipped') {
            return `Interview completed for ${nodeId || 'human gate'} (skipped)`
        }
        if (provenance === 'accepted') {
            return answer
                ? `Interview completed for ${nodeId || 'human gate'} (accepted answer: ${answer})`
                : `Interview completed for ${nodeId || 'human gate'} (accepted answer)`
        }
        return answer
            ? `Interview completed for ${nodeId || 'human gate'} (${answer})`
            : `Interview completed for ${nodeId || 'human gate'}`
    }
    if (type === 'InterviewTimeout') {
        const provenance = interviewOutcomeProvenanceFromPayload(type, payload)
        if (provenance === 'timeout_default_applied') {
            const defaultChoiceLabel = interviewDefaultChoiceLabelFromPayload(payload)
            return defaultChoiceLabel
                ? `Interview timed out for ${nodeId || 'human gate'} (default applied: ${defaultChoiceLabel})`
                : `Interview timed out for ${nodeId || 'human gate'} (default applied)`
        }
        if (provenance === 'timeout_no_default') {
            return `Interview timed out for ${nodeId || 'human gate'} (no default applied)`
        }
        return `Interview timed out for ${nodeId || 'human gate'}`
    }
    if (type === 'human_gate') {
        const prompt = typeof payload.prompt === 'string' && payload.prompt.trim().length > 0
            ? payload.prompt.trim()
            : null
        return prompt
            ? `Human gate pending: ${prompt}`
            : `Human gate pending for ${nodeId || 'unknown'}`
    }
    if (type === 'CheckpointSaved') {
        return `Checkpoint saved at ${nodeId || 'current node'}`
    }
    return type
}

const toTimelineEvent = (value: unknown, sequence: number): TimelineEventEntry | null => {
    const payload = asRecord(value)
    if (!payload) {
        return null
    }
    const type = typeof payload.type === 'string' ? payload.type : ''
    const category = TIMELINE_EVENT_TYPES[type]
    if (!category) {
        return null
    }
    const nodeId = timelineNodeIdFromEvent(payload)
    const stageIndex = asFiniteNumber(payload.index)
    return {
        id: `${type}-${sequence}`,
        sequence,
        type,
        category,
        severity: timelineSeverityFromEvent(type, payload),
        nodeId,
        stageIndex,
        summary: timelineSummaryFromEvent(type, payload, nodeId),
        receivedAt: new Date().toISOString(),
        payload,
    }
}

const timelineEntityKey = (event: TimelineEventEntry): string | null => {
    if (!event.nodeId && event.stageIndex === null) {
        return null
    }
    return `${event.nodeId ?? 'unknown'}::${event.stageIndex !== null ? String(event.stageIndex) : 'na'}`
}

const timelineCorrelationDescriptorFromEvent = (
    event: TimelineEventEntry,
    retryEntityKeys: ReadonlySet<string>
): TimelineCorrelationDescriptor | null => {
    const entityKey = timelineEntityKey(event)
    if (!entityKey) {
        return null
    }
    const stageSuffix = event.stageIndex !== null ? ` (index ${event.stageIndex})` : ''
    const subject = event.nodeId ?? 'unknown'

    if (event.category === 'interview') {
        return {
            key: `interview:${entityKey}`,
            kind: 'interview',
            label: `Interview sequence for ${subject}${stageSuffix}`,
        }
    }

    if (event.category === 'stage' && RETRY_CORRELATION_EVENT_TYPES.has(event.type) && retryEntityKeys.has(entityKey)) {
        return {
            key: `retry:${entityKey}`,
            kind: 'retry',
            label: `Retry sequence for ${subject}${stageSuffix}`,
        }
    }

    return null
}

const normalizeScopePath = (value: string) => {
    const trimmed = value.trim()
    if (!trimmed) return ''
    const slashNormalized = trimmed.replace(/\\/g, '/').replace(/\/{2,}/g, '/')
    const prefix = slashNormalized.startsWith('/') ? '/' : ''
    const rawBody = prefix ? slashNormalized.slice(1) : slashNormalized
    const parts = rawBody.split('/').filter((part) => part.length > 0)
    const segments: string[] = []
    for (const part of parts) {
        if (part === '.') {
            continue
        }
        if (part === '..') {
            segments.pop()
            continue
        }
        segments.push(part)
    }
    const normalizedBody = segments.join('/')
    if (!normalizedBody && prefix) {
        return prefix
    }
    return `${prefix}${normalizedBody}`
}

const runBelongsToProjectScope = (run: RunRecord, projectPath: string) => {
    const normalizedProjectPath = normalizeScopePath(projectPath)
    if (!normalizedProjectPath) return false

    const runWorkingDirectory = normalizeScopePath(run.working_directory || '')
    if (!runWorkingDirectory) return false
    if (runWorkingDirectory === normalizedProjectPath) return true

    return runWorkingDirectory.startsWith(`${normalizedProjectPath}/`)
}

const asStringOption = (
    value: unknown
): { label: string; value: string; key: string | null; description: string | null } | null => {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
        return null
    }
    const candidate = value as Record<string, unknown>
    const rawLabel = typeof candidate.label === 'string' ? candidate.label.trim() : ''
    const rawValue = typeof candidate.value === 'string' ? candidate.value.trim() : ''
    if (!rawLabel || !rawValue) {
        return null
    }
    const rawKey = typeof candidate.key === 'string' ? candidate.key.trim() : ''
    const metadata = asRecord(candidate.metadata)
    const rawMetadataDescription = metadata && typeof metadata.description === 'string'
        ? metadata.description.trim()
        : ''
    const rawDescription = typeof candidate.description === 'string' ? candidate.description.trim() : ''
    return {
        label: rawLabel,
        value: rawValue,
        key: rawKey || null,
        description: rawDescription || rawMetadataDescription || null,
    }
}

const pendingGateOptionsFromPayload = (payload: Record<string, unknown>) => {
    const rawOptions = Array.isArray(payload.options) ? payload.options : []
    const seenValues = new Set<string>()
    const options: Array<{ label: string; value: string; key: string | null; description: string | null }> = []
    for (const rawOption of rawOptions) {
        const option = asStringOption(rawOption)
        if (!option || seenValues.has(option.value)) {
            continue
        }
        seenValues.add(option.value)
        options.push(option)
    }
    return options
}

const pendingGateQuestionTypeFromPayload = (
    payload: Record<string, unknown>
): 'MULTIPLE_CHOICE' | 'YES_NO' | 'CONFIRMATION' | 'FREEFORM' | null => {
    const candidateValue = typeof payload.question_type === 'string'
        ? payload.question_type
        : typeof payload.questionType === 'string'
            ? payload.questionType
            : ''
    const normalized = candidateValue.trim().toUpperCase()
    if (
        normalized === 'MULTIPLE_CHOICE'
        || normalized === 'YES_NO'
        || normalized === 'CONFIRMATION'
        || normalized === 'FREEFORM'
    ) {
        return normalized
    }
    const rawOptions = Array.isArray(payload.options) ? payload.options : []
    return rawOptions.length > 0 ? 'MULTIPLE_CHOICE' : null
}

const pendingGateSemanticFallbackOptions = (
    questionType: 'MULTIPLE_CHOICE' | 'YES_NO' | 'CONFIRMATION' | 'FREEFORM' | null
): Array<{ label: string; value: string; key: string | null; description: string | null }> => {
    if (questionType === 'YES_NO') {
        return [
            { label: 'Yes', value: 'YES', key: 'Y', description: null },
            { label: 'No', value: 'NO', key: 'N', description: null },
        ]
    }
    if (questionType === 'CONFIRMATION') {
        return [
            { label: 'Confirm', value: 'YES', key: 'Y', description: null },
            { label: 'Cancel', value: 'NO', key: 'N', description: null },
        ]
    }
    return []
}

const asPendingQuestionSnapshot = (value: unknown): PendingQuestionSnapshot | null => {
    const payload = asRecord(value)
    if (!payload) {
        return null
    }
    const questionIdValue = payload.question_id
    const questionId = typeof questionIdValue === 'string' ? questionIdValue.trim() : ''
    if (!questionId) {
        return null
    }

    const promptValue = payload.prompt
    const questionPromptValue = payload.question
    const messageValue = payload.message
    const prompt = typeof promptValue === 'string' && promptValue.trim().length > 0
        ? promptValue.trim()
        : typeof questionPromptValue === 'string' && questionPromptValue.trim().length > 0
            ? questionPromptValue.trim()
            : typeof messageValue === 'string' && messageValue.trim().length > 0
                ? messageValue.trim()
                : `Question ${questionId}`

    const nodeIdValue = payload.node_id
    const nodeId = typeof nodeIdValue === 'string' && nodeIdValue.trim().length > 0 ? nodeIdValue.trim() : null
    const questionType = pendingGateQuestionTypeFromPayload(payload)
    const payloadOptions = pendingGateOptionsFromPayload(payload)
    const options = payloadOptions.length > 0
        ? payloadOptions
        : pendingGateSemanticFallbackOptions(questionType)

    return {
        questionId,
        nodeId,
        prompt,
        questionType,
        options,
    }
}

export function RunsPanel() {
    const isNarrowViewport = useNarrowViewport()
    const viewMode = useStore((state) => state.viewMode)
    const activeProjectPath = useStore((state) => state.activeProjectPath)
    const selectedRunId = useStore((state) => state.selectedRunId)
    const setSelectedRunId = useStore((state) => state.setSelectedRunId)
    const setViewMode = useStore((state) => state.setViewMode)
    const setExecutionFlow = useStore((state) => state.setExecutionFlow)
    const setActiveProjectPath = useStore((state) => state.setActiveProjectPath)
    const setSpecId = useStore((state) => state.setSpecId)
    const setPlanId = useStore((state) => state.setPlanId)
    const [runs, setRuns] = useState<RunRecord[]>([])
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [now, setNow] = useState(() => Date.now())
    const [lastFetchedAtMs, setLastFetchedAtMs] = useState<number | null>(null)
    const [checkpointData, setCheckpointData] = useState<CheckpointResponse | null>(null)
    const [isCheckpointLoading, setIsCheckpointLoading] = useState(false)
    const [checkpointError, setCheckpointError] = useState<CheckpointErrorState | null>(null)
    const [contextData, setContextData] = useState<ContextResponse | null>(null)
    const [isContextLoading, setIsContextLoading] = useState(false)
    const [contextError, setContextError] = useState<ContextErrorState | null>(null)
    const [contextSearchQuery, setContextSearchQuery] = useState('')
    const [contextCopyStatus, setContextCopyStatus] = useState('')
    const [artifactData, setArtifactData] = useState<ArtifactListResponse | null>(null)
    const [isArtifactLoading, setIsArtifactLoading] = useState(false)
    const [artifactError, setArtifactError] = useState<ArtifactErrorState | null>(null)
    const [selectedArtifactPath, setSelectedArtifactPath] = useState<string | null>(null)
    const [artifactViewerPayload, setArtifactViewerPayload] = useState('')
    const [artifactViewerError, setArtifactViewerError] = useState<string | null>(null)
    const [isArtifactViewerLoading, setIsArtifactViewerLoading] = useState(false)
    const [graphvizMarkup, setGraphvizMarkup] = useState('')
    const [isGraphvizLoading, setIsGraphvizLoading] = useState(false)
    const [graphvizError, setGraphvizError] = useState<GraphvizErrorState | null>(null)
    const [timelineEvents, setTimelineEvents] = useState<TimelineEventEntry[]>([])
    const [timelineError, setTimelineError] = useState<string | null>(null)
    const [isTimelineLive, setIsTimelineLive] = useState(false)
    const [timelineTypeFilter, setTimelineTypeFilter] = useState('all')
    const [timelineNodeStageFilter, setTimelineNodeStageFilter] = useState('')
    const [timelineCategoryFilter, setTimelineCategoryFilter] = useState<'all' | TimelineEventCategory>('all')
    const [timelineSeverityFilter, setTimelineSeverityFilter] = useState<'all' | TimelineSeverity>('all')
    const [pendingGateActionError, setPendingGateActionError] = useState<string | null>(null)
    const [submittingGateIds, setSubmittingGateIds] = useState<Record<string, boolean>>({})
    const [answeredGateIds, setAnsweredGateIds] = useState<Record<string, boolean>>({})
    const [pendingQuestionSnapshots, setPendingQuestionSnapshots] = useState<PendingQuestionSnapshot[]>([])
    const [freeformAnswersByGateId, setFreeformAnswersByGateId] = useState<Record<string, string>>({})
    const timelineSequenceRef = useRef(0)
    const [metadataStaleAfterMs] = useState(() => {
        const override = (globalThis as typeof globalThis & { __RUNS_METADATA_STALE_AFTER_MS__?: unknown })
            .__RUNS_METADATA_STALE_AFTER_MS__
        return typeof override === 'number' && Number.isFinite(override) && override > 0
            ? override
            : RUN_METADATA_STALE_AFTER_MS
    })
    const isFetchingRef = useRef(false)

    const fetchRuns = useCallback(async () => {
        if (isFetchingRef.current) return
        isFetchingRef.current = true
        setIsLoading(true)
        setError(null)
        try {
            const data = await fetchRunsListValidated()
            setRuns(data.runs)
            setLastFetchedAtMs(Date.now())
        } catch (err) {
            logUnexpectedRunError(err)
            setError('Unable to load runs')
        } finally {
            isFetchingRef.current = false
            setIsLoading(false)
        }
    }, [])

    useEffect(() => {
        if (viewMode !== 'runs') return
        void fetchRuns()
    }, [viewMode, fetchRuns])

    useEffect(() => {
        if (viewMode !== 'runs') return
        const refreshInterval = window.setInterval(() => {
            void fetchRuns()
        }, 15_000)
        return () => window.clearInterval(refreshInterval)
    }, [viewMode, fetchRuns])

    useEffect(() => {
        if (viewMode !== 'runs') return
        const interval = window.setInterval(() => setNow(Date.now()), 1000)
        return () => window.clearInterval(interval)
    }, [viewMode])

    const scopedRuns = useMemo(() => {
        if (!activeProjectPath) return []
        return runs.filter((run) => runBelongsToProjectScope(run, activeProjectPath))
    }, [runs, activeProjectPath])

    const summary = useMemo(() => {
        const total = scopedRuns.length
        const running = scopedRuns.filter(
            (run) => run.status === 'running' || run.status === 'cancel_requested' || run.status === 'abort_requested'
        ).length
        return { total, running }
    }, [scopedRuns])

    const selectedRunSummary = useMemo(() => {
        if (!selectedRunId) return null
        return scopedRuns.find((run) => run.run_id === selectedRunId) || null
    }, [scopedRuns, selectedRunId])
    const degradedDetailPanels = useMemo(() => {
        const panels: string[] = []
        if (checkpointError) {
            panels.push('checkpoint')
        }
        if (contextError) {
            panels.push('context')
        }
        if (artifactError) {
            panels.push('artifacts')
        }
        if (graphvizError) {
            panels.push('graph visualization')
        }
        if (timelineError) {
            panels.push('event timeline')
        }
        return panels
    }, [checkpointError, contextError, artifactError, graphvizError, timelineError])

    const metadataFreshness = computeRunMetadataFreshness({
        isLoading,
        lastFetchedAtMs,
        nowMs: now,
        staleAfterMs: metadataStaleAfterMs,
    })
    const metadataFreshnessLabel =
        metadataFreshness === 'refreshing'
            ? 'Refreshing'
            : metadataFreshness === 'stale'
                ? 'Stale'
                : metadataFreshness === 'fresh'
                    ? 'Fresh'
                    : 'Never'
    const metadataFreshnessStyle =
        metadataFreshness === 'stale'
            ? 'border-amber-500/40 bg-amber-500/10 text-amber-800'
            : metadataFreshness === 'fresh'
                ? 'border-green-500/40 bg-green-500/10 text-green-800'
                : 'border-border bg-muted text-muted-foreground'

    const fetchCheckpoint = useCallback(async () => {
        if (!selectedRunSummary) {
            setCheckpointData(null)
            setCheckpointError(null)
            setIsCheckpointLoading(false)
            return
        }
        setIsCheckpointLoading(true)
        setCheckpointError(null)
        try {
            const payload = await fetchPipelineCheckpointValidated(selectedRunSummary.run_id) as CheckpointResponse
            setCheckpointData(payload)
        } catch (err) {
            logUnexpectedRunError(err)
            setCheckpointData(null)
            if (err instanceof ApiHttpError) {
                setCheckpointError(checkpointErrorFromResponse(err.status, err.detail))
                return
            }
            setCheckpointError({
                message: 'Unable to load checkpoint.',
                help: 'Check your network/backend connection and retry.',
            })
        } finally {
            setIsCheckpointLoading(false)
        }
    }, [selectedRunSummary])

    const fetchContext = useCallback(async () => {
        if (!selectedRunSummary) {
            setContextData(null)
            setContextError(null)
            setIsContextLoading(false)
            return
        }
        setIsContextLoading(true)
        setContextError(null)
        try {
            const payload = await fetchPipelineContextValidated(selectedRunSummary.run_id) as ContextResponse
            setContextData(payload)
        } catch (err) {
            logUnexpectedRunError(err)
            setContextData(null)
            if (err instanceof ApiHttpError) {
                setContextError(contextErrorFromResponse(err.status, err.detail))
                return
            }
            setContextError({
                message: 'Unable to load context.',
                help: 'Check your network/backend connection and retry.',
            })
        } finally {
            setIsContextLoading(false)
        }
    }, [selectedRunSummary])

    const fetchArtifacts = useCallback(async () => {
        if (!selectedRunSummary) {
            setArtifactData(null)
            setArtifactError(null)
            setIsArtifactLoading(false)
            return
        }
        setIsArtifactLoading(true)
        setArtifactError(null)
        try {
            const payload = await fetchPipelineArtifactsValidated(selectedRunSummary.run_id)
            setArtifactData(payload)
        } catch (err) {
            logUnexpectedRunError(err)
            setArtifactData(null)
            if (err instanceof ApiHttpError) {
                setArtifactError(artifactErrorFromResponse(err.status, err.detail))
                return
            }
            setArtifactError({
                message: 'Unable to load artifacts.',
                help: 'Check your network/backend connection and retry.',
            })
        } finally {
            setIsArtifactLoading(false)
        }
    }, [selectedRunSummary])

    const fetchGraphviz = useCallback(async () => {
        if (!selectedRunSummary) {
            setGraphvizMarkup('')
            setGraphvizError(null)
            setIsGraphvizLoading(false)
            return
        }
        setIsGraphvizLoading(true)
        setGraphvizError(null)
        try {
            const svgMarkup = await fetchPipelineGraphValidated(selectedRunSummary.run_id)
            setGraphvizMarkup(svgMarkup)
        } catch (err) {
            logUnexpectedRunError(err)
            setGraphvizMarkup('')
            if (err instanceof ApiHttpError) {
                setGraphvizError(graphvizErrorFromResponse(err.status, err.detail))
                return
            }
            setGraphvizError({
                message: 'Unable to load graph visualization.',
                help: 'Check your network/backend connection and retry.',
            })
        } finally {
            setIsGraphvizLoading(false)
        }
    }, [selectedRunSummary])

    const fetchPendingQuestions = useCallback(async () => {
        if (!selectedRunSummary) {
            setPendingQuestionSnapshots([])
            return
        }
        try {
            const payload = await fetchPipelineQuestionsValidated(selectedRunSummary.run_id)
            const rawQuestions = payload.questions
            const parsedQuestions = rawQuestions
                .map((question) => asPendingQuestionSnapshot(question))
                .filter((question): question is PendingQuestionSnapshot => question !== null)
            setPendingQuestionSnapshots(parsedQuestions)
        } catch (err) {
            logUnexpectedRunError(err)
            setPendingQuestionSnapshots([])
        }
    }, [selectedRunSummary])

    useEffect(() => {
        if (viewMode !== 'runs' || !selectedRunSummary) {
            setCheckpointData(null)
            setCheckpointError(null)
            setIsCheckpointLoading(false)
            return
        }
        void fetchCheckpoint()
    }, [viewMode, selectedRunSummary, fetchCheckpoint])

    useEffect(() => {
        if (viewMode !== 'runs' || !selectedRunSummary) {
            setContextData(null)
            setContextError(null)
            setIsContextLoading(false)
            setContextSearchQuery('')
            setContextCopyStatus('')
            return
        }
        setContextSearchQuery('')
        setContextCopyStatus('')
        void fetchContext()
    }, [viewMode, selectedRunSummary, fetchContext])

    useEffect(() => {
        if (viewMode !== 'runs' || !selectedRunSummary) {
            setArtifactData(null)
            setArtifactError(null)
            setIsArtifactLoading(false)
            setSelectedArtifactPath(null)
            setArtifactViewerPayload('')
            setArtifactViewerError(null)
            setIsArtifactViewerLoading(false)
            return
        }
        setSelectedArtifactPath(null)
        setArtifactViewerPayload('')
        setArtifactViewerError(null)
        setIsArtifactViewerLoading(false)
        void fetchArtifacts()
    }, [viewMode, selectedRunSummary, fetchArtifacts])

    useEffect(() => {
        if (viewMode !== 'runs' || !selectedRunSummary) {
            setGraphvizMarkup('')
            setGraphvizError(null)
            setIsGraphvizLoading(false)
            return
        }
        setGraphvizMarkup('')
        setGraphvizError(null)
        setIsGraphvizLoading(false)
        void fetchGraphviz()
    }, [viewMode, selectedRunSummary, fetchGraphviz])

    useEffect(() => {
        if (viewMode !== 'runs' || !selectedRunSummary) {
            setPendingQuestionSnapshots([])
            return
        }
        void fetchPendingQuestions()
    }, [viewMode, selectedRunSummary, fetchPendingQuestions])

    const selectedRunTimelineId = selectedRunSummary?.run_id ?? null

    useEffect(() => {
        setPendingGateActionError(null)
        setSubmittingGateIds({})
        setAnsweredGateIds({})
        setPendingQuestionSnapshots([])
    }, [selectedRunTimelineId])

    useEffect(() => {
        if (viewMode !== 'runs' || !selectedRunTimelineId) {
            timelineSequenceRef.current = 0
            setTimelineEvents([])
            setTimelineError(null)
            setIsTimelineLive(false)
            setTimelineTypeFilter('all')
            setTimelineNodeStageFilter('')
            setTimelineCategoryFilter('all')
            setTimelineSeverityFilter('all')
            return
        }

        timelineSequenceRef.current = 0
        setTimelineEvents([])
        setTimelineError(null)
        setIsTimelineLive(false)
        setTimelineTypeFilter('all')
        setTimelineNodeStageFilter('')
        setTimelineCategoryFilter('all')
        setTimelineSeverityFilter('all')

        const source = new EventSource(pipelineEventsUrl(selectedRunTimelineId))
        source.onopen = () => {
            setTimelineError(null)
            setIsTimelineLive(true)
        }
        source.onmessage = (event) => {
            try {
                const payload = JSON.parse(event.data) as unknown
                const sequence = timelineSequenceRef.current
                const timelineEvent = toTimelineEvent(payload, sequence)
                if (!timelineEvent) {
                    return
                }
                timelineSequenceRef.current = sequence + 1
                setTimelineEvents((current) => [timelineEvent, ...current].slice(0, TIMELINE_MAX_ITEMS))
            } catch {
                // ignore malformed events
            }
        }
        source.onerror = () => {
            setIsTimelineLive(false)
            setTimelineError((current) => current || 'Event timeline stream unavailable. Reopen this run to retry.')
        }

        return () => {
            source.close()
            setIsTimelineLive(false)
        }
    }, [viewMode, selectedRunTimelineId])

    const checkpointSnapshot = useMemo(() => asRecord(checkpointData?.checkpoint), [checkpointData])
    const checkpointCurrentNode = useMemo(() => {
        const currentNode = checkpointSnapshot?.current_node
        return typeof currentNode === 'string' && currentNode.trim().length > 0 ? currentNode : '—'
    }, [checkpointSnapshot])
    const checkpointCompletedNodes = useMemo(() => {
        const completedNodes = checkpointSnapshot?.completed_nodes
        if (!Array.isArray(completedNodes)) return '—'
        const normalized = completedNodes
            .map((value) => (typeof value === 'string' ? value.trim() : ''))
            .filter((value) => value.length > 0)
        return normalized.length > 0 ? normalized.join(', ') : '—'
    }, [checkpointSnapshot])
    const checkpointRetryCounters = useMemo(() => {
        const retryCounts = asRecord(checkpointSnapshot?.retry_counts)
        if (!retryCounts) return '—'
        const pairs = Object.entries(retryCounts)
            .filter(([key]) => key.trim().length > 0)
            .map(([key, value]) => {
                if (typeof value === 'number' && Number.isFinite(value)) return `${key}: ${value}`
                if (typeof value === 'string' || typeof value === 'boolean') return `${key}: ${String(value)}`
                return `${key}: ${JSON.stringify(value)}`
            })
        return pairs.length > 0 ? pairs.join(', ') : '—'
    }, [checkpointSnapshot])
    const contextSnapshot = useMemo(() => asRecord(contextData?.context), [contextData])
    const contextRows = useMemo(() => {
        if (!contextSnapshot) return []
        return Object.entries(contextSnapshot)
            .map(([key, value]) => {
                const formatted = formatContextValue(value)
                return { key, rawValue: value, ...formatted }
            })
            .sort((a, b) => a.key.localeCompare(b.key))
    }, [contextSnapshot])
    const filteredContextRows = useMemo(() => {
        const normalizedQuery = contextSearchQuery.trim().toLowerCase()
        if (!normalizedQuery) return contextRows
        return contextRows.filter((row) => (
            row.key.toLowerCase().includes(normalizedQuery)
            || row.renderedValue.toLowerCase().includes(normalizedQuery)
        ))
    }, [contextRows, contextSearchQuery])
    const contextExportPayload = useMemo(() => {
        if (!selectedRunSummary) return ''
        return buildContextExportPayload(
            selectedRunSummary.run_id,
            filteredContextRows.map((row) => ({ key: row.key, value: row.rawValue }))
        )
    }, [selectedRunSummary, filteredContextRows])
    const contextExportHref = useMemo(() => {
        if (!contextExportPayload) return ''
        return `data:application/json;charset=utf-8,${encodeURIComponent(contextExportPayload)}`
    }, [contextExportPayload])
    const copyContextToClipboard = useCallback(async () => {
        if (!contextExportPayload || filteredContextRows.length === 0) {
            setContextCopyStatus('No context entries available to copy.')
            return
        }
        try {
            await window.navigator.clipboard.writeText(contextExportPayload)
            setContextCopyStatus('Filtered context copied.')
        } catch (error) {
            console.error(error)
            setContextCopyStatus('Copy failed. Clipboard access is unavailable.')
        }
    }, [contextExportPayload, filteredContextRows])
    const artifactEntries = useMemo(() => {
        return artifactData?.artifacts || []
    }, [artifactData])
    const missingCoreArtifacts = useMemo(() => {
        if (artifactEntries.length === 0) return []
        const available = new Set(artifactEntries.map((entry) => entry.path))
        return EXPECTED_CORE_ARTIFACT_PATHS.filter((path) => !available.has(path))
    }, [artifactEntries])
    const showPartialRunArtifactNote = artifactEntries.length === 0 || missingCoreArtifacts.length > 0
    const selectedArtifactEntry = useMemo(() => {
        if (!selectedArtifactPath) return null
        return artifactEntries.find((entry) => entry.path === selectedArtifactPath) || null
    }, [artifactEntries, selectedArtifactPath])
    const viewArtifact = useCallback(async (entry: ArtifactListEntry) => {
        if (!selectedRunSummary) {
            return
        }
        setSelectedArtifactPath(entry.path)
        setArtifactViewerPayload('')
        setArtifactViewerError(null)
        if (!entry.viewable) {
            setArtifactViewerError('Preview unavailable for this artifact type. Use download action.')
            return
        }
        setIsArtifactViewerLoading(true)
        try {
            const payload = await fetchPipelineArtifactPreviewValidated(selectedRunSummary.run_id, entry.path)
            setArtifactViewerPayload(payload)
        } catch (error) {
            logUnexpectedRunError(error)
            if (error instanceof ApiHttpError) {
                setArtifactViewerError(artifactPreviewErrorFromResponse(error.status, error.detail))
                return
            }
            setArtifactViewerError('Unable to load artifact preview. Check your network/backend connection and retry.')
        } finally {
            setIsArtifactViewerLoading(false)
        }
    }, [selectedRunSummary])
    const artifactDownloadHref = useCallback((artifactPath: string) => {
        if (!selectedRunSummary) return ''
        return pipelineArtifactHref(selectedRunSummary.run_id, artifactPath, true)
    }, [selectedRunSummary])
    const graphvizViewerSrc = useMemo(() => {
        if (!graphvizMarkup) return ''
        return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(graphvizMarkup)}`
    }, [graphvizMarkup])
    const timelineTypeOptions = useMemo(() => {
        return Array.from(new Set(timelineEvents.map((event) => event.type))).sort((left, right) => left.localeCompare(right))
    }, [timelineEvents])
    const filteredTimelineEvents = useMemo(() => {
        const normalizedNodeStageFilter = timelineNodeStageFilter.trim().toLowerCase()

        return timelineEvents.filter((event) => {
            if (timelineTypeFilter !== 'all' && event.type !== timelineTypeFilter) {
                return false
            }
            if (timelineCategoryFilter !== 'all' && event.category !== timelineCategoryFilter) {
                return false
            }
            if (timelineSeverityFilter !== 'all' && event.severity !== timelineSeverityFilter) {
                return false
            }
            if (!normalizedNodeStageFilter) {
                return true
            }

            const nodeIdMatch = (event.nodeId ?? '').toLowerCase().includes(normalizedNodeStageFilter)
            const stageIndexMatch = event.stageIndex !== null && String(event.stageIndex).includes(normalizedNodeStageFilter)
            return nodeIdMatch || stageIndexMatch
        })
    }, [timelineCategoryFilter, timelineEvents, timelineNodeStageFilter, timelineSeverityFilter, timelineTypeFilter])
    const retryCorrelationEntityKeys = useMemo(() => {
        const keys = new Set<string>()
        for (const event of timelineEvents) {
            const entityKey = timelineEntityKey(event)
            if (!entityKey) {
                continue
            }
            if (event.type === 'StageRetrying' || asFiniteNumber(event.payload.attempt) !== null) {
                keys.add(entityKey)
            }
        }
        return keys
    }, [timelineEvents])
    const groupedTimelineEntries = useMemo(() => {
        const entries: GroupedTimelineEntry[] = []
        const groupedEntryIndex = new Map<string, number>()

        for (const event of filteredTimelineEvents) {
            const correlation = timelineCorrelationDescriptorFromEvent(event, retryCorrelationEntityKeys)
            if (!correlation) {
                entries.push({
                    id: event.id,
                    correlation: null,
                    events: [event],
                })
                continue
            }

            const existingIndex = groupedEntryIndex.get(correlation.key)
            if (existingIndex === undefined) {
                groupedEntryIndex.set(correlation.key, entries.length)
                entries.push({
                    id: `group-${correlation.key}`,
                    correlation,
                    events: [event],
                })
                continue
            }

            entries[existingIndex].events.push(event)
        }

        return entries
    }, [filteredTimelineEvents, retryCorrelationEntityKeys])
    const timelineDroppedCount = Math.max(0, timelineSequenceRef.current - timelineEvents.length)
    const pendingInterviewGates = useMemo(() => {
        const closedEntityKeys = new Set<string>()
        const pendingGates: PendingInterviewGate[] = []
        const pendingGateKeys = new Set<string>()
        for (const event of timelineEvents) {
            if (event.category !== 'interview') {
                continue
            }
            const entityKey = timelineEntityKey(event) || `event:${event.id}`
            if (closedEntityKeys.has(entityKey)) {
                continue
            }
            if (event.type === 'InterviewCompleted' || event.type === 'InterviewTimeout') {
                closedEntityKeys.add(entityKey)
                continue
            }
            if (event.type !== 'InterviewStarted' && event.type !== 'human_gate' && event.type !== 'InterviewInform') {
                continue
            }

            const questionIdValue = event.payload.question_id
            const questionId = typeof questionIdValue === 'string' && questionIdValue.trim().length > 0
                ? questionIdValue.trim()
                : null
            const questionType = pendingGateQuestionTypeFromPayload(event.payload)
            const payloadOptions = pendingGateOptionsFromPayload(event.payload)
            const options = payloadOptions.length > 0
                ? payloadOptions
                : pendingGateSemanticFallbackOptions(questionType)
            const questionPrompt = event.payload.question
            const gatePrompt = event.payload.prompt
            const informMessage = event.payload.message
            const prompt = typeof questionPrompt === 'string' && questionPrompt.trim().length > 0
                ? questionPrompt.trim()
                : typeof gatePrompt === 'string' && gatePrompt.trim().length > 0
                    ? gatePrompt.trim()
                    : typeof informMessage === 'string' && informMessage.trim().length > 0
                        ? informMessage.trim()
                    : event.summary
            const dedupeKey = `${event.nodeId ?? ''}::${prompt.toLowerCase()}`
            if (pendingGateKeys.has(dedupeKey)) {
                continue
            }
            pendingGateKeys.add(dedupeKey)
            pendingGates.push({
                eventId: event.id,
                sequence: event.sequence,
                receivedAt: event.receivedAt,
                nodeId: event.nodeId,
                stageIndex: event.stageIndex,
                prompt,
                questionId,
                questionType,
                options,
            })
        }
        let nextSequence = pendingGates.reduce((maxSequence, gate) => Math.max(maxSequence, gate.sequence), 0) + 1
        for (const question of pendingQuestionSnapshots) {
            const questionIdMatch = pendingGates.some((gate) => gate.questionId === question.questionId)
            if (questionIdMatch) {
                continue
            }
            const dedupeKey = `${question.nodeId ?? ''}::${question.prompt.toLowerCase()}`
            if (pendingGateKeys.has(dedupeKey)) {
                continue
            }
            pendingGateKeys.add(dedupeKey)
            pendingGates.push({
                eventId: `question:${question.questionId}`,
                sequence: nextSequence,
                receivedAt: PENDING_GATE_FALLBACK_RECEIVED_AT,
                nodeId: question.nodeId,
                stageIndex: null,
                prompt: question.prompt,
                questionId: question.questionId,
                questionType: question.questionType,
                options: question.options,
            })
            nextSequence += 1
        }
        return pendingGates
    }, [pendingQuestionSnapshots, timelineEvents])
    const visiblePendingInterviewGates = useMemo(
        () => pendingInterviewGates.filter((gate) => !gate.questionId || !answeredGateIds[gate.questionId]),
        [pendingInterviewGates, answeredGateIds]
    )
    const groupedPendingInterviewGates = useMemo(() => {
        const grouped = new Map<string, PendingInterviewGateGroup>()
        for (const gate of visiblePendingInterviewGates) {
            const key = `${gate.nodeId ?? 'human-gate'}::${gate.stageIndex !== null ? String(gate.stageIndex) : 'na'}`
            if (!grouped.has(key)) {
                const headingNode = gate.nodeId ?? 'human gate'
                const headingStage = gate.stageIndex !== null ? ` (index ${gate.stageIndex})` : ''
                grouped.set(key, {
                    key,
                    heading: `${headingNode}${headingStage}`,
                    gates: [],
                })
            }
            grouped.get(key)?.gates.push(gate)
        }
        const sortedGroups = Array.from(grouped.values()).map((group) => ({
            ...group,
            gates: [...group.gates].sort((left, right) => left.sequence - right.sequence),
        }))
        sortedGroups.sort((left, right) => {
            const leftSequence = left.gates[0]?.sequence ?? Number.MAX_SAFE_INTEGER
            const rightSequence = right.gates[0]?.sequence ?? Number.MAX_SAFE_INTEGER
            if (leftSequence !== rightSequence) {
                return leftSequence - rightSequence
            }
            return left.key.localeCompare(right.key)
        })
        return sortedGroups
    }, [visiblePendingInterviewGates])

    const submitPendingGateAnswer = useCallback(async (gate: PendingInterviewGate, selectedValue: string) => {
        if (!selectedRunTimelineId || !gate.questionId || !selectedValue.trim()) {
            return
        }
        setPendingGateActionError(null)
        setSubmittingGateIds((previous) => ({
            ...previous,
            [gate.questionId!]: true,
        }))
        try {
            await fetchPipelineAnswerValidated(selectedRunTimelineId, gate.questionId, selectedValue)
            setAnsweredGateIds((previous) => ({
                ...previous,
                [gate.questionId!]: true,
            }))
            setFreeformAnswersByGateId((previous) => {
                const next = { ...previous }
                delete next[gate.questionId!]
                return next
            })
        } catch (err) {
            logUnexpectedRunError(err)
            if (err instanceof ApiHttpError) {
                const detailSuffix = err.detail ? `: ${err.detail}` : ''
                setPendingGateActionError(`Unable to submit answer (HTTP ${err.status})${detailSuffix}.`)
            } else {
                setPendingGateActionError('Unable to submit answer. Check connection/backend and retry.')
            }
        } finally {
            setSubmittingGateIds((previous) => {
                const next = { ...previous }
                delete next[gate.questionId!]
                return next
            })
        }
    }, [selectedRunTimelineId])

    const openRun = (run: RunRecord) => {
        setSelectedRunId(run.run_id)
        setExecutionFlow(run.flow_name || null)
        setViewMode('execution')
    }

    const openRunArtifact = (run: RunRecord, artifactType: 'spec' | 'plan') => {
        const artifactId = artifactType === 'spec' ? run.spec_id : run.plan_id
        if (!artifactId) {
            return
        }
        if (run.project_path) {
            setActiveProjectPath(run.project_path)
        }
        if (artifactType === 'spec') {
            setSpecId(artifactId)
        } else {
            setPlanId(artifactId)
        }
        setViewMode('home')
    }

    const requestCancel = async (runId: string, currentStatus: string) => {
        if (currentStatus !== 'running') {
            return
        }
        if (!window.confirm('Cancel this run? It will stop after the active node finishes.')) {
            return
        }
        setRuns((current) =>
            current.map((run) => (
                run.run_id === runId
                    ? { ...run, status: 'cancel_requested' }
                    : run
            ))
        )
        try {
            await fetchPipelineCancelValidated(runId)
            void fetchRuns()
        } catch (err) {
            logUnexpectedRunError(err)
            setRuns((current) =>
                current.map((run) => (
                    run.run_id === runId
                        ? { ...run, status: currentStatus }
                        : run
                ))
            )
            window.alert('Failed to cancel run')
        }
    }

    return (
        <div data-testid="runs-panel" className={`flex-1 overflow-auto ${isNarrowViewport ? 'p-3' : 'p-6'}`}>
            <div className="mx-auto w-full max-w-6xl space-y-6">
                <div className="flex items-center justify-between">
                    <div className="space-y-1">
                        <h2 className="text-lg font-semibold">Run History</h2>
                        <p className="text-sm text-muted-foreground">
                            {summary.total} total runs · {summary.running} running
                        </p>
                    </div>
                    <button
                        onClick={() => void fetchRuns()}
                        data-testid="runs-refresh-button"
                        className="inline-flex h-8 items-center gap-2 rounded-md border border-border px-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground hover:text-foreground"
                    >
                        <RefreshCcw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
                        Refresh
                    </button>
                </div>
                <div className="flex flex-wrap items-center gap-2 text-xs">
                    <span
                        data-testid="run-metadata-freshness-indicator"
                        className={`inline-flex items-center rounded-md border px-2 py-1 font-semibold uppercase tracking-wide ${metadataFreshnessStyle}`}
                    >
                        {metadataFreshnessLabel}
                    </span>
                    <span data-testid="run-metadata-last-updated" className="text-muted-foreground">
                        {formatRunMetadataLastUpdated({ lastFetchedAtMs, nowMs: now })}
                    </span>
                </div>
                {metadataFreshness === 'stale' && (
                    <div data-testid="run-metadata-stale-indicator" className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-800">
                        Run metadata may be stale. Refresh to load the latest run status.
                    </div>
                )}

                {error && (
                    <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                        {error}
                    </div>
                )}
                {!activeProjectPath && (
                    <div className="rounded-md border border-border bg-card px-3 py-2 text-sm text-muted-foreground">
                        Select an active project to view run history for that project.
                    </div>
                )}
                {activeProjectPath && scopedRuns.length > 0 && !selectedRunSummary && (
                    <div data-testid="run-selection-empty-state" className="rounded-md border border-border bg-card px-3 py-2 text-sm text-muted-foreground">
                        Select a run from the history table to inspect its details.
                    </div>
                )}
                {selectedRunSummary && (
                    <RunSummaryCard
                        activeProjectPath={activeProjectPath}
                        now={now}
                        run={selectedRunSummary}
                    />
                )}
                {selectedRunSummary && degradedDetailPanels.length > 0 && (
                    <div
                        data-testid="run-partial-api-failure-banner"
                        className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-800"
                    >
                        Some run detail endpoints are unavailable. Non-dependent panels remain functional.
                        <span className="ml-1 text-xs">
                            Affected surfaces: {degradedDetailPanels.join(', ')}.
                        </span>
                    </div>
                )}
                {selectedRunSummary && (
                    <RunCheckpointCard
                        checkpointCompletedNodes={checkpointCompletedNodes}
                        checkpointCurrentNode={checkpointCurrentNode}
                        checkpointData={checkpointData?.checkpoint ?? null}
                        checkpointError={checkpointError}
                        checkpointRetryCounters={checkpointRetryCounters}
                        isLoading={isCheckpointLoading}
                        onRefresh={() => {
                            void fetchCheckpoint()
                        }}
                    />
                )}
                {selectedRunSummary && (
                    <RunContextCard
                        contextCopyStatus={contextCopyStatus}
                        contextError={contextError}
                        contextExportHref={contextExportHref || null}
                        filteredContextRows={filteredContextRows}
                        isLoading={isContextLoading}
                        onCopy={() => {
                            void copyContextToClipboard()
                        }}
                        onRefresh={() => {
                            setContextCopyStatus('')
                            void fetchContext()
                        }}
                        onSearchQueryChange={setContextSearchQuery}
                        runId={selectedRunSummary.run_id}
                        searchQuery={contextSearchQuery}
                    />
                )}
                {selectedRunSummary && (
                    <RunArtifactsCard
                        artifactDownloadHref={(artifactPath) => artifactDownloadHref(artifactPath) || null}
                        artifactEntries={artifactEntries}
                        artifactError={artifactError}
                        artifactViewerError={artifactViewerError}
                        artifactViewerPayload={artifactViewerPayload || null}
                        isArtifactViewerLoading={isArtifactViewerLoading}
                        isLoading={isArtifactLoading}
                        missingCoreArtifacts={missingCoreArtifacts}
                        onRefresh={() => {
                            void fetchArtifacts()
                        }}
                        onViewArtifact={(artifact) => {
                            void viewArtifact(artifact)
                        }}
                        selectedArtifactEntry={selectedArtifactEntry}
                        showPartialRunArtifactNote={showPartialRunArtifactNote}
                    />
                )}
                {selectedRunSummary && (
                    <RunGraphvizCard
                        graphvizError={graphvizError}
                        graphvizViewerSrc={graphvizViewerSrc || null}
                        isGraphvizLoading={isGraphvizLoading}
                        onRefresh={() => {
                            void fetchGraphviz()
                        }}
                        runId={selectedRunSummary.run_id}
                    />
                )}
                {selectedRunSummary && (
                    <RunEventTimelineCard
                        isNarrowViewport={isNarrowViewport}
                        isTimelineLive={isTimelineLive}
                        timelineDroppedCount={timelineDroppedCount}
                        timelineError={timelineError}
                        timelineEvents={timelineEvents}
                        visiblePendingInterviewGates={visiblePendingInterviewGates}
                        groupedPendingInterviewGates={groupedPendingInterviewGates}
                        pendingGateActionError={pendingGateActionError}
                        submittingGateIds={submittingGateIds}
                        freeformAnswersByGateId={freeformAnswersByGateId}
                        timelineTypeFilter={timelineTypeFilter}
                        timelineTypeOptions={timelineTypeOptions}
                        timelineNodeStageFilter={timelineNodeStageFilter}
                        timelineCategoryFilter={timelineCategoryFilter}
                        timelineSeverityFilter={timelineSeverityFilter}
                        filteredTimelineEvents={filteredTimelineEvents}
                        groupedTimelineEntries={groupedTimelineEntries}
                        onTimelineCategoryFilterChange={setTimelineCategoryFilter}
                        onTimelineNodeStageFilterChange={setTimelineNodeStageFilter}
                        onTimelineSeverityFilterChange={setTimelineSeverityFilter}
                        onTimelineTypeFilterChange={setTimelineTypeFilter}
                        onFreeformAnswerChange={(questionId, value) => {
                            setFreeformAnswersByGateId((previous) => ({
                                ...previous,
                                [questionId]: value,
                            }))
                        }}
                        onSubmitPendingGateAnswer={(gate, selectedValue) => {
                            void submitPendingGateAnswer(gate, selectedValue)
                        }}
                    />
                )}
                <RunList
                    activeProjectPath={activeProjectPath}
                    now={now}
                    onOpenRun={openRun}
                    onOpenRunArtifact={openRunArtifact}
                    onRequestCancel={(runId, currentStatus) => {
                        void requestCancel(runId, currentStatus)
                    }}
                    runs={scopedRuns}
                    selectedRunId={selectedRunId}
                />
            </div>
        </div>
    )
}
