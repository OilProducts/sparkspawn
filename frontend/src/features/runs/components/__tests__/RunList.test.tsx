import { RunList } from '@/features/runs/components/RunList'
import type { RunRecord } from '@/features/runs/model/shared'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

const makeRun = (overrides: Partial<RunRecord> = {}): RunRecord => ({
    run_id: overrides.run_id ?? 'run-1',
    flow_name: overrides.flow_name ?? 'selected.dot',
    status: overrides.status ?? 'running',
    outcome: overrides.outcome ?? null,
    outcome_reason_code: overrides.outcome_reason_code ?? null,
    outcome_reason_message: overrides.outcome_reason_message ?? null,
    working_directory: overrides.working_directory ?? '/tmp/workdir',
    project_path: overrides.project_path ?? '/tmp/project-one',
    git_branch: overrides.git_branch ?? 'main',
    git_commit: overrides.git_commit ?? 'abcdef0',
    spec_id: overrides.spec_id ?? null,
    plan_id: overrides.plan_id ?? null,
    model: overrides.model ?? 'gpt-5.4',
    started_at: overrides.started_at ?? '2026-03-22T00:00:00Z',
    ended_at: overrides.ended_at ?? null,
    last_error: overrides.last_error ?? '',
    token_usage: overrides.token_usage ?? 1234,
    current_node: overrides.current_node ?? null,
    continued_from_run_id: overrides.continued_from_run_id ?? null,
    continued_from_node: overrides.continued_from_node ?? null,
    continued_from_flow_mode: overrides.continued_from_flow_mode ?? null,
    continued_from_flow_name: overrides.continued_from_flow_name ?? null,
})

describe('RunList', () => {
    it('shows the cold-load notice only when no runs have been loaded yet', () => {
        render(
            <RunList
                activeProjectPath="/tmp/project-one"
                error={null}
                isLoading={true}
                isRefreshing={false}
                metadataFreshness="refreshing"
                now={Date.now()}
                onRefresh={vi.fn()}
                onScopeModeChange={vi.fn()}
                onSelectRun={vi.fn()}
                runs={[]}
                scopeMode="active"
                selectedRunId={null}
                status="loading"
                summaryLabel="0 total runs · 0 running"
            />,
        )

        expect(screen.getByTestId('run-list-loading')).toBeVisible()
        expect(screen.queryByTestId('run-list-scroll-region')).not.toBeInTheDocument()
    })

    it('keeps the run history visible during background refresh', () => {
        render(
            <RunList
                activeProjectPath="/tmp/project-one"
                error={null}
                isLoading={false}
                isRefreshing={true}
                metadataFreshness="refreshing"
                now={Date.now()}
                onRefresh={vi.fn()}
                onScopeModeChange={vi.fn()}
                onSelectRun={vi.fn()}
                runs={[makeRun({ flow_name: 'refreshing.dot' })]}
                scopeMode="active"
                selectedRunId={null}
                status="ready"
                summaryLabel="1 total runs · 1 running"
            />,
        )

        expect(screen.queryByTestId('run-list-loading')).not.toBeInTheDocument()
        expect(screen.getByTestId('run-list-scroll-region')).toBeVisible()
        expect(screen.getByText('refreshing.dot')).toBeVisible()
    })
})
