import { expect, test, type Page } from '@playwright/test'
import { ensureScreenshotDir, gotoWithRegisteredProject, screenshotPath, stubProjectMetadata } from '../fixtures/smoke-helpers'

type SmokeRunRecord = {
  run_id: string
  flow_name: string
  status: string
  outcome: 'success' | 'failure' | null
  working_directory: string
  project_path: string
  git_branch: string | null
  git_commit: string | null
  model: string
  started_at: string
  ended_at: string | null
  last_error: string
  token_usage: number
  current_node?: string | null
}

test.beforeAll(() => {
  ensureScreenshotDir()
})

test.beforeEach(async ({ page }) => {
  await stubProjectMetadata(page)
})

function buildSmokeRun(projectPath: string, overrides: Partial<SmokeRunRecord> = {}): SmokeRunRecord {
  return {
    run_id: overrides.run_id ?? `run-${Date.now()}`,
    flow_name: overrides.flow_name ?? 'SmokeFlow',
    status: overrides.status ?? 'completed',
    outcome: overrides.outcome ?? 'success',
    working_directory: overrides.working_directory ?? `${projectPath}/workspace`,
    project_path: overrides.project_path ?? projectPath,
    git_branch: overrides.git_branch ?? 'main',
    git_commit: overrides.git_commit ?? 'abc1234',
    model: overrides.model ?? 'gpt-5',
    started_at: overrides.started_at ?? '2026-03-03T12:00:00Z',
    ended_at: overrides.ended_at ?? '2026-03-03T12:02:00Z',
    last_error: overrides.last_error ?? '',
    token_usage: overrides.token_usage ?? 42,
    current_node: overrides.current_node ?? null,
  }
}

async function stubRunSummary(page: Page, run: SmokeRunRecord) {
  await page.route('**/attractor/runs**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        runs: [run],
      }),
    })
  })

  await page.route(`**/attractor/pipelines/${run.run_id}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        pipeline_id: run.run_id,
        ...run,
        completed_nodes: run.current_node ? [run.current_node] : [],
        progress: {
          current_node: run.current_node ?? null,
          completed_nodes: run.current_node ? [run.current_node] : [],
        },
      }),
    })
  })
}

async function openRunsForSmokeTest(page: Page, projectPath: string) {
  await gotoWithRegisteredProject(page, projectPath)
  await page.getByTestId('nav-mode-runs').click()
  await expect(page.getByTestId('run-history-row').first()).toBeVisible()
  await page.getByTestId('run-history-row').first().click()
  await expect(page.getByTestId('run-summary-panel')).toBeVisible()
}

test('run summary panel renders populated metadata for items 9.1-01 and 9.6-02', async ({ page }) => {
  const projectPath = `/tmp/ui-smoke-project-runs-summary-${Date.now()}`
  const run = buildSmokeRun(projectPath, {
    run_id: `run-summary-${Date.now()}`,
    flow_name: 'SmokeFlow',
    git_branch: 'feature/traceability',
    git_commit: 'fedcba9876543210',
  })

  await stubRunSummary(page, run)
  await openRunsForSmokeTest(page, projectPath)

  await expect(page.getByTestId('run-summary-panel')).toContainText(run.run_id)
  await expect(page.getByTestId('run-summary-status')).toContainText('Completed')
  await expect(page.getByTestId('run-summary-outcome')).toContainText('Success')
  await expect(page.getByTestId('run-summary-flow-name')).toContainText('SmokeFlow')
  await expect(page.getByTestId('run-summary-model')).toContainText('gpt-5')
  await expect(page.getByTestId('run-summary-working-directory')).toContainText(`${projectPath}/workspace`)
  await expect(page.getByTestId('run-summary-project-path')).toContainText(projectPath)
  await expect(page.getByTestId('run-summary-git-branch')).toContainText('feature/traceability')
  await expect(page.getByTestId('run-summary-git-commit')).toContainText('fedcba9876543210')
  await expect(page.getByTestId('run-summary-token-usage')).toContainText('42')
  await page.screenshot({ path: screenshotPath('08b-runs-panel-populated-summary.png'), fullPage: true })
})

test('run checkpoint viewer fetches checkpoint payload for item 9.2-01', async ({ page }) => {
  const projectPath = `/tmp/ui-smoke-project-runs-checkpoint-${Date.now()}`
  const run = buildSmokeRun(projectPath, {
    run_id: `run-checkpoint-${Date.now()}`,
    flow_name: 'CheckpointFlow',
    current_node: 'implement',
  })
  let checkpointFetchCount = 0

  await stubRunSummary(page, run)
  await page.route(`**/attractor/pipelines/${run.run_id}/checkpoint`, async (route) => {
    checkpointFetchCount += 1
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        pipeline_id: run.run_id,
        checkpoint: {
          current_node: 'implement',
          completed_nodes: ['start', 'plan'],
          retry_counts: { implement: 1 },
          timestamp: '2026-03-03T12:01:30Z',
        },
      }),
    })
  })

  await openRunsForSmokeTest(page, projectPath)

  await expect(page.getByTestId('run-checkpoint-panel')).toBeVisible()
  await expect(page.getByTestId('run-checkpoint-payload')).toContainText('"pipeline_id":')
  await expect(page.getByTestId('run-checkpoint-payload')).toContainText('"current_node": "implement"')
  await expect.poll(() => checkpointFetchCount).toBeGreaterThanOrEqual(1)

  await page.getByTestId('run-checkpoint-refresh-button').click()
  await expect.poll(() => checkpointFetchCount).toBeGreaterThanOrEqual(2)
  await page.screenshot({ path: screenshotPath('08d-runs-panel-checkpoint-viewer.png'), fullPage: true })
})

test('run context viewer supports search, copy, and export actions for items 9.3-01 and 9.3-03', async ({ page }) => {
  const projectPath = `/tmp/ui-smoke-project-runs-context-${Date.now()}`
  const run = buildSmokeRun(projectPath, {
    run_id: `run-context-${Date.now()}`,
    flow_name: 'ContextFlow',
  })

  await stubRunSummary(page, run)
  await page.route(`**/attractor/pipelines/${run.run_id}/context`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        pipeline_id: run.run_id,
        context: {
          'graph.goal': 'Ship copy export',
          owner: 'reviewer',
          retries: 1,
        },
      }),
    })
  })

  await openRunsForSmokeTest(page, projectPath)
  await page.evaluate(() => {
    Object.defineProperty(window.navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: async (value: string) => {
          ;(globalThis as typeof globalThis & { __copied_context_payload__?: string }).__copied_context_payload__ = value
        },
      },
    })
  })

  await expect(page.getByTestId('run-context-panel')).toBeVisible()
  await expect(page.getByTestId('run-context-table')).toBeVisible()
  await page.getByTestId('run-context-search-input').fill('owner')
  await expect(page.getByTestId('run-context-row')).toHaveCount(1)
  await expect(page.getByTestId('run-context-row-value-scalar')).toContainText('reviewer')

  await page.getByTestId('run-context-copy-button').click()
  await expect(page.getByTestId('run-context-copy-status')).toContainText('Filtered context copied.')
  await expect
    .poll(() => page.evaluate(() => (globalThis as typeof globalThis & { __copied_context_payload__?: string }).__copied_context_payload__ || ''))
    .toContain(`"pipeline_id": "${run.run_id}"`)
  await expect(page.getByTestId('run-context-export-button')).toHaveAttribute('href', /data:application\/json/)
  await page.screenshot({ path: screenshotPath('08f-runs-panel-context-viewer.png'), fullPage: true })
})

test('run graph panel renders /pipelines/{id}/graph-preview output for item 9.5-02', async ({ page }) => {
  const projectPath = `/tmp/ui-smoke-project-runs-graph-${Date.now()}`
  const run = buildSmokeRun(projectPath, {
    run_id: `run-graph-${Date.now()}`,
    flow_name: 'GraphFlow',
  })

  await stubRunSummary(page, run)
  await page.route(`**/attractor/pipelines/${run.run_id}/graph-preview`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'ok',
        graph: {
          graph_attrs: {
            label: 'Run graph smoke',
          },
          nodes: [
            { id: 'start', label: 'Start', shape: 'Mdiamond' },
            { id: 'review', label: 'Review', shape: 'box' },
            { id: 'done', label: 'Done', shape: 'Msquare' },
          ],
          edges: [
            { from: 'start', to: 'review', label: null, condition: null, weight: null, fidelity: null, thread_id: null, loop_restart: false },
            { from: 'review', to: 'done', label: null, condition: null, weight: null, fidelity: null, thread_id: null, loop_restart: false },
          ],
        },
        diagnostics: [],
        errors: [],
      }),
    })
  })

  await openRunsForSmokeTest(page, projectPath)

  const graphPanel = page.getByTestId('run-graph-panel')
  await expect(graphPanel).toBeVisible()
  await page.getByTestId('run-graph-toggle-button').click()
  await expect(page.getByTestId('run-graph-canvas')).toBeVisible()
  await expect(page.locator('[data-testid="run-graph-canvas"] .react-flow__node')).toHaveCount(3)
  await graphPanel.scrollIntoViewIfNeeded()
  await graphPanel.screenshot({ path: screenshotPath('08n-runs-panel-run-graph.png') })
})

test('run artifact browser handles missing files and partial run states for item 9.5-03', async ({ page }) => {
  const projectPath = `/tmp/ui-smoke-project-runs-artifacts-missing-${Date.now()}`
  const run = buildSmokeRun(projectPath, {
    run_id: `run-artifacts-missing-${Date.now()}`,
    flow_name: 'ArtifactMissingFlow',
    status: 'failed',
    outcome: null,
    git_commit: 'art9503',
    last_error: 'stage artifact missing',
    token_usage: 9,
  })

  await stubRunSummary(page, run)
  await page.route(`**/attractor/pipelines/${run.run_id}/artifacts`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        pipeline_id: run.run_id,
        artifacts: [
          {
            path: 'plan/prompt.md',
            size_bytes: 80,
            media_type: 'text/markdown',
            viewable: true,
          },
        ],
      }),
    })
  })
  await page.route(`**/attractor/pipelines/${run.run_id}/artifacts/**`, async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname.endsWith(`/pipelines/${run.run_id}/artifacts`)) {
      await route.fallback()
      return
    }
    await route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Artifact not found' }),
    })
  })

  await openRunsForSmokeTest(page, projectPath)

  const artifactPanel = page.getByTestId('run-artifact-panel')
  await expect(artifactPanel).toBeVisible()
  await expect(page.getByTestId('run-artifact-partial-run-note')).toContainText(
    'This run may be partial or artifacts may have been pruned.',
  )
  await expect(page.getByTestId('run-artifact-partial-run-note')).toContainText(
    'Missing expected files: manifest.json, checkpoint.json.',
  )

  const promptRow = page.getByTestId('run-artifact-row').filter({ hasText: 'plan/prompt.md' }).first()
  await promptRow.getByTestId('run-artifact-view-button').click()
  await expect(page.getByTestId('run-artifact-viewer-error')).toContainText(
    'Artifact preview unavailable because the file was not found for this run.',
  )

  await artifactPanel.scrollIntoViewIfNeeded()
  await artifactPanel.screenshot({ path: screenshotPath('08o-runs-panel-artifact-missing-partial.png') })
})
