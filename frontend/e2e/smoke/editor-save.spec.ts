import { expect, test } from '@playwright/test'
import {
  cloneFlowForSmokeTest,
  deleteFlowAfterSmoke,
  ensureScreenshotDir,
  screenshotPath,
  stubProjectMetadata,
} from '../fixtures/smoke-helpers'

test.beforeAll(() => {
  ensureScreenshotDir()
})

test.beforeEach(async ({ page }) => {
  await stubProjectMetadata(page)
})

test("semantic-equivalence save blocks mismatch and confirms no-op round-trip for item 5.3-03", async ({ page }) => {
  const projectPath = `/tmp/ui-smoke-project-semantic-equivalence-${Date.now()}`
  const semanticSaveBodies: string[] = []
  const semanticMismatchBodies: string[] = []
  const semanticEquivalentSavedBodies: string[] = []
  let mismatchInjected = false
  let mismatchTargetContent: string | null = null

  await page.route("**/api/flows", async (route) => {
    const request = route.request()
    if (request.method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(["semantic.dot"]),
      })
      return
    }

    if (request.method() === "POST") {
      const body = request.postData() || ""
      const hasSemanticEquivalenceGuard = body.includes('"expect_semantic_equivalence":true')
      let payload: { expect_semantic_equivalence?: boolean; content?: string } = {}
      try {
        payload = JSON.parse(body) as { expect_semantic_equivalence?: boolean; content?: string }
      } catch {
        payload = {}
      }

      if (payload.expect_semantic_equivalence === true || hasSemanticEquivalenceGuard) {
        semanticSaveBodies.push(body)
        if (
          mismatchTargetContent !== null
          && mismatchInjected === false
          && payload.content === mismatchTargetContent
        ) {
          mismatchInjected = true
          semanticMismatchBodies.push(body)
          await route.fulfill({
            status: 409,
            contentType: "application/json",
            body: '{"detail":{"status":"semantic_mismatch","error":"semantic equivalence check failed: output DOT would change flow behavior"}}',
          })
          return
        }
        semanticEquivalentSavedBodies.push(body)
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "saved", name: "semantic.dot" }),
      })
      return
    }

    await route.continue()
  })

  await page.route("**/api/flows/semantic.dot", async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue()
      return
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        name: "semantic.dot",
        content: [
          "digraph semantic {",
          '  start [shape=Mdiamond, label=label="Start"];',
          '  done [shape=Msquare, label="Done"];',
          "  start -> done;",
          "}",
        ].join("\n"),
      }),
    })
  })

  await page.route("**/preview", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "ok",
        graph: {
          nodes: [
            { id: "start", shape: "Mdiamond", label: "Start" },
            { id: "done", shape: "Msquare", label: "Done" },
          ],
          edges: [{ from: "start", to: "done" }],
        },
        diagnostics: [],
      }),
    })
  })

  await page.goto("/")
  await page.getByTestId("project-path-input").fill(projectPath)
  await page.getByTestId("project-register-button").click()
  await page.getByTestId("nav-mode-editor").click()

  const flowButton = page.getByRole("button", { name: "semantic.dot" })
  await expect(flowButton).toBeVisible()
  await flowButton.click()
  await expect(page.getByTestId("canvas-workspace-primary")).toBeVisible()
  await expect.poll(() => semanticSaveBodies.length).toBeGreaterThanOrEqual(1)

  await page.getByRole("button", { name: "Raw DOT" }).click()
  const rawDotEditor = page.getByTestId("raw-dot-editor")
  await expect(rawDotEditor).toBeVisible()
  const rawDotEntry = await rawDotEditor.inputValue()
  mismatchTargetContent = rawDotEntry
  await page.getByRole("button", { name: "Structured" }).click()
  await expect(rawDotEditor).toBeVisible()
  const rawHandoffError = page.getByTestId("raw-dot-handoff-error")
  if ((await rawHandoffError.count()) > 0) {
    await expect(rawHandoffError).toContainText("Safe handoff requires valid DOT.")
  }
  await expect(page.getByRole("button", { name: "Add Node" })).toHaveCount(0)
  await expect.poll(() => semanticMismatchBodies.length).toBeGreaterThanOrEqual(1)
  await page.screenshot({ path: screenshotPath("19a-semantic-equivalence-mismatch-blocked.png"), fullPage: true })

  const equivalentSavesBeforeRoundTrip = semanticEquivalentSavedBodies.length
  await rawDotEditor.fill(rawDotEntry)
  await page.getByRole("button", { name: "Structured" }).click()
  await expect(page.getByRole("button", { name: "Add Node" })).toBeVisible()
  await expect.poll(() => semanticEquivalentSavedBodies.length).toBeGreaterThan(equivalentSavesBeforeRoundTrip)
  await page.screenshot({ path: screenshotPath("19b-semantic-equivalence-round-trip-saved.png"), fullPage: true })
})
