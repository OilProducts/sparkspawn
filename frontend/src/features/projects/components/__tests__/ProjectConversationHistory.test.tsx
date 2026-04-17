import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { ProjectConversationHistory } from '@/features/projects/components/ProjectConversationHistory'
import type { ConversationTimelineEntry } from '@/features/projects/model/types'

const formatConversationTimestamp = (value: string) => `formatted:${value}`

const renderHistory = (
    activeConversationHistory: ConversationTimelineEntry[],
    overrides: {
        onSubmitRequestUserInput?: (requestId: string, answers: Record<string, string>) => void | Promise<void>
        requestUserInputActionError?: string | null
        submittingRequestUserInputIds?: Record<string, boolean>
    } = {},
) =>
    render(
        <ProjectConversationHistory
            activeConversationId="conversation-1"
            isConversationHistoryLoading={false}
            hasRenderableConversationHistory={activeConversationHistory.length > 0}
            activeConversationHistory={activeConversationHistory}
            activeFlowRunRequestsById={new Map()}
            activeFlowLaunchesById={new Map()}
            latestFlowRunRequestId={null}
            latestFlowLaunchId={null}
            expandedToolCalls={{}}
            expandedThinkingEntries={{}}
            pendingFlowRunRequestId={null}
            requestUserInputActionError={overrides.requestUserInputActionError ?? null}
            submittingRequestUserInputIds={overrides.submittingRequestUserInputIds ?? {}}
            formatConversationTimestamp={formatConversationTimestamp}
            onSubmitRequestUserInput={overrides.onSubmitRequestUserInput ?? vi.fn()}
            onToggleToolCallExpanded={vi.fn()}
            onToggleThinkingEntryExpanded={vi.fn()}
            onReviewFlowRunRequest={vi.fn()}
            onOpenFlowRun={vi.fn()}
        />,
    )

const InteractiveHistory = ({
    activeConversationHistory,
}: {
    activeConversationHistory: ConversationTimelineEntry[]
}) => {
    const [expandedToolCalls, setExpandedToolCalls] = useState<Record<string, boolean>>({})
    const [expandedThinkingEntries, setExpandedThinkingEntries] = useState<Record<string, boolean>>({})

    return (
        <ProjectConversationHistory
            activeConversationId="conversation-1"
            isConversationHistoryLoading={false}
            hasRenderableConversationHistory
            activeConversationHistory={activeConversationHistory}
            activeFlowRunRequestsById={new Map()}
            activeFlowLaunchesById={new Map()}
            latestFlowRunRequestId={null}
            latestFlowLaunchId={null}
            expandedToolCalls={expandedToolCalls}
            expandedThinkingEntries={expandedThinkingEntries}
            pendingFlowRunRequestId={null}
            requestUserInputActionError={null}
            submittingRequestUserInputIds={{}}
            formatConversationTimestamp={formatConversationTimestamp}
            onSubmitRequestUserInput={vi.fn()}
            onToggleToolCallExpanded={(toolCallId) =>
                setExpandedToolCalls((current) => ({
                    ...current,
                    [toolCallId]: !current[toolCallId],
                }))
            }
            onToggleThinkingEntryExpanded={(entryId) =>
                setExpandedThinkingEntries((current) => ({
                    ...current,
                    [entryId]: !current[entryId],
                }))
            }
            onReviewFlowRunRequest={vi.fn()}
            onOpenFlowRun={vi.fn()}
        />
    )
}

const makeMessageEntry = (
    overrides: Partial<Extract<ConversationTimelineEntry, { kind: 'message' }>> = {},
): Extract<ConversationTimelineEntry, { kind: 'message' }> => ({
    id: overrides.id ?? 'message-1',
    kind: 'message',
    role: overrides.role ?? 'assistant',
    content: overrides.content ?? 'Plain text response.',
    timestamp: overrides.timestamp ?? '2026-04-16T15:27:47Z',
    status: overrides.status ?? 'complete',
    error: overrides.error ?? null,
    presentation: overrides.presentation ?? 'default',
})

const makeToolCallEntry = (
    overrides: Partial<Extract<ConversationTimelineEntry, { kind: 'tool_call' }>> = {},
): Extract<ConversationTimelineEntry, { kind: 'tool_call' }> => ({
    id: overrides.id ?? 'entry-tool-1',
    kind: 'tool_call',
    role: 'system',
    timestamp: overrides.timestamp ?? '2026-04-16T15:27:47Z',
    toolCall: overrides.toolCall ?? {
        id: 'tool-1',
        kind: 'command_execution',
        status: 'completed',
        title: 'List files',
        command: '/bin/zsh -lc printf "**literal**"',
        output: '[README](https://example.com)',
        filePaths: [],
    },
})

const makeModeChangeEntry = (
    overrides: Partial<Extract<ConversationTimelineEntry, { kind: 'mode_change' }>> = {},
): Extract<ConversationTimelineEntry, { kind: 'mode_change' }> => ({
    id: overrides.id ?? 'mode-change-1',
    kind: 'mode_change',
    role: 'system',
    timestamp: overrides.timestamp ?? '2026-04-16T15:27:47Z',
    mode: overrides.mode ?? 'plan',
})

const makeContextCompactionEntry = (
    overrides: Partial<Extract<ConversationTimelineEntry, { kind: 'context_compaction' }>> = {},
): Extract<ConversationTimelineEntry, { kind: 'context_compaction' }> => ({
    id: overrides.id ?? 'context-compaction-1',
    kind: 'context_compaction',
    role: 'system',
    timestamp: overrides.timestamp ?? '2026-04-16T15:27:47Z',
    content: overrides.content ?? 'Context compacted to continue the turn.',
    status: overrides.status ?? 'complete',
})

const makeRequestUserInputEntry = (
    overrides: Partial<Extract<ConversationTimelineEntry, { kind: 'request_user_input' }>> = {},
): Extract<ConversationTimelineEntry, { kind: 'request_user_input' }> => ({
    id: overrides.id ?? 'request-user-input-1',
    kind: 'request_user_input',
    role: 'system',
    timestamp: overrides.timestamp ?? '2026-04-17T12:00:00Z',
    content: overrides.content ?? 'Which path should I take?',
    status: overrides.status ?? 'pending',
    requestUserInput: overrides.requestUserInput ?? {
        requestId: 'request-1',
        status: 'pending',
        questions: [
            {
                id: 'path_choice',
                header: 'Path',
                question: 'Which path should I take?',
                questionType: 'MULTIPLE_CHOICE',
                options: [
                    {
                        label: 'Inline card',
                        description: 'Keep the request inside the timeline.',
                    },
                    {
                        label: 'Composer takeover',
                        description: 'Move the unanswered state into the composer.',
                    },
                ],
                allowOther: true,
                isSecret: false,
            },
            {
                id: 'constraints',
                header: 'Constraints',
                question: 'What constraints matter?',
                questionType: 'FREEFORM',
                options: [],
                allowOther: false,
                isSecret: false,
            },
        ],
        answers: {},
        submittedAt: null,
    },
})

const makePlanEntry = (
    overrides: Partial<Extract<ConversationTimelineEntry, { kind: 'plan' }>> = {},
): Extract<ConversationTimelineEntry, { kind: 'plan' }> => ({
    id: overrides.id ?? 'plan-1',
    kind: 'plan',
    role: 'assistant',
    content: overrides.content ?? '1. Ship the regression test.\n2. Validate the real session path.',
    timestamp: overrides.timestamp ?? '2026-04-16T15:27:47Z',
    status: overrides.status ?? 'complete',
    error: overrides.error ?? null,
})

describe('ProjectConversationHistory', () => {
    it('renders markdown semantics for normal assistant messages', () => {
        renderHistory([
            makeMessageEntry({
                content: '## Steps\n\nUse **bold** text and *italics* in the response.',
            }),
        ])

        const history = screen.getByTestId('project-ai-conversation-history-list')
        expect(within(history).getByRole('heading', { level: 2, name: 'Steps' })).toBeVisible()
        expect(within(history).getByText('bold', { selector: 'strong' })).toBeVisible()
        expect(within(history).getByText('italics', { selector: 'em' })).toBeVisible()
        expect(within(history).queryByText('**bold**')).not.toBeInTheDocument()
    })

    it('renders assistant fenced code blocks as preformatted code', () => {
        renderHistory([
            makeMessageEntry({
                content: '```bash\nnpm test\n```',
            }),
        ])

        const history = screen.getByTestId('project-ai-conversation-history-list')
        const codeBlock = history.querySelector('pre > code')
        expect(codeBlock).not.toBeNull()
        expect(codeBlock).toHaveTextContent('npm test')
    })

    it('renders mode-change rows as centered inline system markers', () => {
        renderHistory([
            makeModeChangeEntry(),
        ])

        const row = screen.getByTestId('project-mode-change-row-mode-change-1')
        expect(within(row).getByText('Switched to Plan mode')).toBeVisible()
    })

    it('renders context compaction rows as centered inline system markers', () => {
        renderHistory([
            makeContextCompactionEntry(),
        ])

        const row = screen.getByTestId('project-context-compaction-row-context-compaction-1')
        expect(within(row).getByText('Context compacted to continue the turn.')).toBeVisible()
    })

    it('renders plan entries as dedicated markdown cards', () => {
        renderHistory([
            makePlanEntry({
                content: '## Proposed steps\n\n1. Add the transport regression.\n2. Run validation.',
            }),
        ])

        const planCard = screen.getByTestId('project-plan-card-plan-1')
        expect(within(planCard).getByText('Proposed Plan')).toBeVisible()
        expect(within(planCard).getByRole('heading', { level: 2, name: 'Proposed steps' })).toBeVisible()
        expect(within(planCard).getByText('Add the transport regression.')).toBeVisible()
    })

    it('renders unanswered request_user_input segments inline and submits answers through the real callback', async () => {
        const user = userEvent.setup()
        const onSubmitRequestUserInput = vi.fn()

        renderHistory([
            makeRequestUserInputEntry(),
        ], {
            onSubmitRequestUserInput,
        })

        const card = screen.getByTestId('project-request-user-input-card-request-user-input-1')
        expect(within(card).getByText('Needs Input')).toBeVisible()
        expect(within(card).getByText('Which path should I take?')).toBeVisible()
        expect(within(card).getByText('What constraints matter?')).toBeVisible()
        expect(screen.queryByTestId('project-pending-questions-preview-note')).not.toBeInTheDocument()

        await user.click(screen.getByTestId('project-request-user-input-option-path_choice-Inline card'))
        await user.type(screen.getByTestId('project-request-user-input-field-constraints'), 'Preserve the inline timeline.')
        await user.click(screen.getByTestId('project-request-user-input-submit-request-1'))

        expect(onSubmitRequestUserInput).toHaveBeenCalledWith('request-1', {
            path_choice: 'Inline card',
            constraints: 'Preserve the inline timeline.',
        })
    })

    it('renders answered request_user_input segments as compact summaries', () => {
        renderHistory([
            makeRequestUserInputEntry({
                status: 'complete',
                requestUserInput: {
                    requestId: 'request-1',
                    status: 'answered',
                    questions: [
                        {
                            id: 'path_choice',
                            header: 'Path',
                            question: 'Which path should I take?',
                            questionType: 'MULTIPLE_CHOICE',
                            options: [],
                            allowOther: false,
                            isSecret: false,
                        },
                    ],
                    answers: {
                        path_choice: 'Inline card',
                    },
                    submittedAt: '2026-04-17T12:01:00Z',
                },
            }),
        ])

        const summary = screen.getByTestId('project-request-user-input-summary-request-user-input-1')
        expect(within(summary).getByText('Answered Request')).toBeVisible()
        expect(within(summary).getByText('Which path should I take?')).toBeVisible()
        expect(within(summary).getByText('Inline card')).toBeVisible()
    })

    it('renders assistant markdown links as plain labels without anchors', () => {
        renderHistory([
            makeMessageEntry({
                content: 'Read [the docs](https://example.com/docs) before continuing.',
            }),
        ])

        const history = screen.getByTestId('project-ai-conversation-history-list')
        expect(within(history).getByText('the docs')).toBeVisible()
        expect(within(history).queryByRole('link', { name: 'the docs' })).not.toBeInTheDocument()
        expect(history).not.toHaveTextContent('https://example.com/docs')
    })

    it('keeps assistant markdown image syntax from rendering images', () => {
        renderHistory([
            makeMessageEntry({
                content: 'Diagram: ![Architecture overview](https://example.com/diagram.png)',
            }),
        ])

        const history = screen.getByTestId('project-ai-conversation-history-list')
        expect(within(history).getByText('Architecture overview')).toBeVisible()
        expect(within(history).queryByRole('img', { name: 'Architecture overview' })).not.toBeInTheDocument()
    })

    it('keeps user messages literal even when they contain markdown syntax', () => {
        renderHistory([
            makeMessageEntry({
                role: 'user',
                content: '**literal** [docs](https://example.com/docs)',
            }),
        ])

        const history = screen.getByTestId('project-ai-conversation-history-list')
        expect(history).toHaveTextContent('**literal** [docs](https://example.com/docs)')
        expect(within(history).queryByRole('link', { name: 'docs' })).not.toBeInTheDocument()
    })

    it('keeps thinking summaries collapsed until expanded', async () => {
        const user = userEvent.setup()

        render(
            <InteractiveHistory
                activeConversationHistory={[
                    makeMessageEntry({
                        id: 'segment-reasoning-1',
                        presentation: 'thinking',
                        status: 'streaming',
                        content: '**Considering proposal** Smallest safe change first.',
                    }),
                ]}
            />,
        )

        expect(screen.getByText('Considering proposal')).toBeVisible()
        expect(screen.queryByText('Smallest safe change first.')).not.toBeInTheDocument()

        await user.click(screen.getByTestId('project-thinking-toggle-segment-reasoning-1'))
        expect(screen.getByText('Smallest safe change first.')).toBeVisible()
    })

    it('keeps tool command and output rows literal and unchanged', async () => {
        const user = userEvent.setup()

        render(<InteractiveHistory activeConversationHistory={[makeToolCallEntry()]} />)

        const history = screen.getByTestId('project-ai-conversation-history-list')
        expect(history).toHaveTextContent('/bin/zsh -lc printf "**literal**"')
        expect(screen.queryByText('[README](https://example.com)')).not.toBeInTheDocument()

        await user.click(screen.getByTestId('project-tool-call-toggle-tool-1'))

        expect(screen.getByText('[README](https://example.com)')).toBeVisible()
        expect(within(history).queryByRole('link', { name: 'README' })).not.toBeInTheDocument()
    })
})
