import { mkdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import type { Page } from '@playwright/test'

const testDir = path.dirname(fileURLToPath(import.meta.url))
const screenshotDir = path.resolve(testDir, '..', '..', 'artifacts', 'ui-smoke')
const IMPLEMENT_SPEC_FLOW = 'implement-spec.dot'

export const ensureScreenshotDir = () => {
  mkdirSync(screenshotDir, { recursive: true })
}

export const screenshotPath = (name: string) => path.join(screenshotDir, name)

export async function cloneFlowForSmokeTest(page: Page, clonePrefix: string): Promise<string> {
  const cloneName = `${clonePrefix}-${Date.now()}.dot`
  const sourceResponse = await page.request.get(`/api/flows/${encodeURIComponent(IMPLEMENT_SPEC_FLOW)}`)
  if (!sourceResponse.ok()) {
    throw new Error(`Failed to load ${IMPLEMENT_SPEC_FLOW} for smoke clone: HTTP ${sourceResponse.status()}`)
  }

  const sourcePayload = (await sourceResponse.json()) as { content?: unknown }
  if (typeof sourcePayload.content !== 'string' || sourcePayload.content.length === 0) {
    throw new Error(`Source flow ${IMPLEMENT_SPEC_FLOW} returned empty content for smoke clone.`)
  }

  const saveResponse = await page.request.post('/api/flows', {
    data: { name: cloneName, content: sourcePayload.content },
  })
  if (!saveResponse.ok()) {
    throw new Error(`Failed to persist smoke clone ${cloneName}: HTTP ${saveResponse.status()}`)
  }
  return cloneName
}

export async function deleteFlowAfterSmoke(page: Page, flowName: string): Promise<void> {
  await page.request.delete(`/api/flows/${encodeURIComponent(flowName)}`)
}
