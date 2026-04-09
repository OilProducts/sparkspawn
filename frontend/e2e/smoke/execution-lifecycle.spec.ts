import { expect, test } from '@playwright/test'
import {
  cleanupSmokeFlowsForPage,
  createFlowForSmokeTest,
  deleteFlowAfterSmoke,
  ensureScreenshotDir,
  gotoWithRegisteredProject,
  screenshotPath,
  stubProjectMetadata,
} from '../fixtures/smoke-helpers'

test.beforeAll(() => {
  ensureScreenshotDir()
})

test.beforeEach(async ({ page }) => {
  await stubProjectMetadata(page)
})

test.afterEach(async ({ page }) => {
  await cleanupSmokeFlowsForPage(page)
})

test("warning-only diagnostics still allow execute with explicit banner for item 7.2-02", async ({ page }) => {
  const projectPath = `/tmp/ui-smoke-project-warning-only-${Date.now()}`
  const promptToken = `warning-only-${Date.now()}`
  const warningMessage = `Warning-only diagnostic ${Date.now()}`
  const flowName = await createFlowForSmokeTest(page, "ui-smoke-warning-only")

  try {
    await page.route("**/attractor/preview", async (route) => {
      const body = route.request().postData() || ""
      if (body.includes(promptToken)) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            status: "ok",
            diagnostics: [
              {
                rule_id: "warning_only_state",
                severity: "warning",
                message: warningMessage,
              },
            ],
          }),
        })
        return
      }
      await route.continue()
    })

    await page.route(`**/attractor/api/flows/${encodeURIComponent(flowName)}`, async (route) => {
      if (route.request().method() !== 'GET') {
        await route.continue()
        return
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          name: flowName,
          content: `digraph warning_only {
  start [label="Start", shape=Mdiamond]
  extract_declarations [label="Extract Testable Declarations", prompt="${promptToken}", shape=box]
  done [label="Done", shape=Msquare]
  start -> extract_declarations
  extract_declarations -> done
}`,
        }),
      })
    })

    await gotoWithRegisteredProject(page, projectPath)
    await page.getByTestId("nav-mode-execution").click()
    const flowButton = page.getByTestId("execution-flow-tree").getByRole("button", { name: flowName })
    await expect(flowButton).toBeVisible()
    const previewRequest = page.waitForRequest(
      (request) =>
        request.url().includes("/attractor/preview") &&
        request.method() === "POST" &&
        (request.postData() || "").includes(promptToken),
    )
    await flowButton.click()
    await previewRequest

    await expect(page.getByTestId("execute-button")).toBeEnabled()
    await expect(page.getByTestId("execute-warning-banner")).toBeVisible()
    await expect(page.getByTestId("execute-warning-banner")).toContainText("Warnings present; run allowed.")
    await page.screenshot({ path: screenshotPath("16-warning-only-execute-banner.png"), fullPage: true })
  } finally {
    await deleteFlowAfterSmoke(page, flowName)
  }
})

test("diagnostics transitions toggle execute blocking and warning state for item 7.2-03", async ({ page }) => {
  const projectPath = `/tmp/ui-smoke-project-diagnostic-transition-${Date.now()}`
  const errorToken = `diagnostic-error-${Date.now()}`
  const warningToken = `diagnostic-warning-${Date.now()}`
  const cleanToken = `diagnostic-clean-${Date.now()}`
  const errorFlowName = await createFlowForSmokeTest(page, "ui-smoke-diagnostic-error")
  const warningFlowName = await createFlowForSmokeTest(page, "ui-smoke-diagnostic-warning")
  const cleanFlowName = await createFlowForSmokeTest(page, "ui-smoke-diagnostic-clean")

  try {
    await page.route("**/attractor/preview", async (route) => {
      const body = route.request().postData() || ""
      if (body.includes(errorToken)) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            status: "ok",
            diagnostics: [
              {
                rule_id: "blocking_error_transition",
                severity: "error",
                message: "Transition error diagnostic",
              },
              {
                rule_id: "warning_with_error_transition",
                severity: "warning",
                message: "Transition warning diagnostic",
              },
            ],
          }),
        })
        return
      }
      if (body.includes(warningToken)) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            status: "ok",
            diagnostics: [
              {
                rule_id: "warning_only_transition",
                severity: "warning",
                message: "Transition warning diagnostic",
              },
            ],
          }),
        })
        return
      }
      if (body.includes(cleanToken)) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            status: "ok",
            diagnostics: [],
          }),
        })
        return
      }
      await route.continue()
    })

    const flowContentByName: Record<string, string> = {
      [errorFlowName]: `digraph diagnostic_error {
  start [label="Start", shape=Mdiamond]
  extract_declarations [label="Extract Testable Declarations", prompt="${errorToken}", shape=box]
  done [label="Done", shape=Msquare]
  start -> extract_declarations
  extract_declarations -> done
}`,
      [warningFlowName]: `digraph diagnostic_warning {
  start [label="Start", shape=Mdiamond]
  extract_declarations [label="Extract Testable Declarations", prompt="${warningToken}", shape=box]
  done [label="Done", shape=Msquare]
  start -> extract_declarations
  extract_declarations -> done
}`,
      [cleanFlowName]: `digraph diagnostic_clean {
  start [label="Start", shape=Mdiamond]
  extract_declarations [label="Extract Testable Declarations", prompt="${cleanToken}", shape=box]
  done [label="Done", shape=Msquare]
  start -> extract_declarations
  extract_declarations -> done
}`,
    }

    await page.route('**/attractor/api/flows/*', async (route) => {
      if (route.request().method() !== 'GET') {
        await route.continue()
        return
      }
      const flowName = decodeURIComponent(route.request().url().split('/attractor/api/flows/')[1] ?? '')
      const content = flowContentByName[flowName]
      if (!content) {
        await route.continue()
        return
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          name: flowName,
          content,
        }),
      })
    })

    await gotoWithRegisteredProject(page, projectPath)
    await page.getByTestId("nav-mode-execution").click()
    const executionFlowTree = page.getByTestId("execution-flow-tree")

    const waitForPreviewToken = (token: string) =>
      page.waitForRequest(
        (request) =>
          request.url().includes("/attractor/preview") &&
          request.method() === "POST" &&
          (request.postData() || "").includes(token),
      )

    const errorPreviewRequest = waitForPreviewToken(errorToken)
    await executionFlowTree.getByRole('button', { name: errorFlowName }).click()
    await errorPreviewRequest
    await expect(page.getByTestId("execute-button")).toBeDisabled()
    await expect(page.getByTestId("execute-button")).toHaveAttribute("title", "Fix validation errors before running.")
    await expect(page.getByTestId("execute-warning-banner")).toHaveCount(0)

    const warningPreviewRequest = waitForPreviewToken(warningToken)
    await executionFlowTree.getByRole('button', { name: warningFlowName }).click()
    await warningPreviewRequest
    await expect(page.getByTestId("execute-button")).toBeEnabled()
    await expect(page.getByTestId("execute-warning-banner")).toBeVisible()
    await expect(page.getByTestId("execute-warning-banner")).toContainText("Warnings present; run allowed.")
    await page.screenshot({ path: screenshotPath("17-diagnostic-transition-execute-state.png"), fullPage: true })

    const cleanPreviewRequest = waitForPreviewToken(cleanToken)
    await executionFlowTree.getByRole('button', { name: cleanFlowName }).click()
    await cleanPreviewRequest
    await expect(page.getByTestId("execute-button")).toBeEnabled()
    await expect(page.getByTestId("execute-warning-banner")).toHaveCount(0)
  } finally {
    await deleteFlowAfterSmoke(page, errorFlowName)
    await deleteFlowAfterSmoke(page, warningFlowName)
    await deleteFlowAfterSmoke(page, cleanFlowName)
  }
})

test("launch failures surface diagnostics and retry affordances for direct runs", async ({ page }) => {
  const projectPath = `/tmp/ui-smoke-project-launch-failure-${Date.now()}`
  const flowName = await createFlowForSmokeTest(page, "ui-smoke-launch-failure")
  let pipelineStartAttempts = 0

  try {
    await page.route("**/attractor/pipelines", async (route) => {
      pipelineStartAttempts += 1
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ detail: "forced smoke launch failure" }),
      })
    })

    await gotoWithRegisteredProject(page, projectPath)
    await page.getByTestId("nav-mode-execution").click()
    const flowButton = page.getByRole("button", { name: flowName })
    await expect(flowButton).toBeVisible()
    await flowButton.click()
    await expect(page.getByTestId("execution-launch-panel")).toBeVisible()
    await expect(page.getByTestId("execution-launch-flow-name")).toContainText(flowName)
    await page.getByTestId("execute-button").click()
    await expect(page.getByTestId("run-start-error-banner")).toContainText("forced smoke launch failure")
    await expect(page.getByTestId("launch-failure-diagnostics")).toBeVisible()
    await expect(page.getByTestId("launch-failure-message")).toContainText("forced smoke launch failure")
    await expect(page.getByTestId("launch-retry-button")).toBeEnabled()
    await expect.poll(() => pipelineStartAttempts).toBe(1)
    await page.screenshot({ path: screenshotPath("20-launch-failure-retry-enabled.png"), fullPage: true })

    await page.getByTestId("launch-retry-button").click()
    await expect.poll(() => pipelineStartAttempts).toBe(2)
  } finally {
    await deleteFlowAfterSmoke(page, flowName)
  }
})
