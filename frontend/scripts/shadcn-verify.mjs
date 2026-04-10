import { createHash } from 'node:crypto'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const cwd = process.cwd()
const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const manifestPath = path.join(scriptDir, 'shadcn-baseline.json')
const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'))
const failures = []

function sha256(source) {
  return createHash('sha256').update(source).digest('hex')
}

function addFailure(message, details) {
  failures.push({ message, details })
}

function readText(relativePath) {
  const absolutePath = path.join(cwd, relativePath)
  if (!existsSync(absolutePath)) {
    addFailure(`Missing required file: ${relativePath}`)
    return null
  }

  return readFileSync(absolutePath, 'utf8')
}

function verifyWorkspace() {
  const workspace = manifest.workspace
  const componentsJsonSource = readText(workspace.componentsConfigPath)
  if (!componentsJsonSource) {
    return
  }

  const componentsConfig = JSON.parse(componentsJsonSource)

  if (componentsConfig.$schema !== workspace.expectedSchema) {
    addFailure(
      'components.json schema does not match the pinned shadcn baseline.',
      `Expected ${workspace.expectedSchema}, received ${JSON.stringify(componentsConfig.$schema)}.`,
    )
  }

  if (componentsConfig.style !== workspace.expectedStyle) {
    addFailure(
      'components.json style does not match the pinned shadcn baseline.',
      `Expected ${workspace.expectedStyle}, received ${JSON.stringify(componentsConfig.style)}.`,
    )
  }

  if (componentsConfig.tailwind?.css !== workspace.expectedCssPath) {
    addFailure(
      'components.json tailwind.css does not match the pinned shadcn baseline.',
      `Expected ${workspace.expectedCssPath}, received ${JSON.stringify(componentsConfig.tailwind?.css)}.`,
    )
  }

  if (componentsConfig.aliases?.ui !== workspace.expectedUiAlias) {
    addFailure(
      'components.json aliases.ui does not match the pinned shadcn baseline.',
      `Expected ${workspace.expectedUiAlias}, received ${JSON.stringify(componentsConfig.aliases?.ui)}.`,
    )
  }

  if (componentsConfig.aliases?.components !== workspace.expectedComponentsAlias) {
    addFailure(
      'components.json aliases.components does not match the pinned shadcn baseline.',
      `Expected ${workspace.expectedComponentsAlias}, received ${JSON.stringify(componentsConfig.aliases?.components)}.`,
    )
  }

  if (componentsConfig.aliases?.utils !== workspace.expectedUtilsAlias) {
    addFailure(
      'components.json aliases.utils does not match the pinned shadcn baseline.',
      `Expected ${workspace.expectedUtilsAlias}, received ${JSON.stringify(componentsConfig.aliases?.utils)}.`,
    )
  }

  const managedDirectoryPath = path.join(cwd, workspace.managedDirectory)
  if (!existsSync(managedDirectoryPath)) {
    addFailure(`Missing managed UI directory: ${workspace.managedDirectory}`)
    return
  }

  const expectedPaths = manifest.components.map((component) => component.path).sort()
  const actualPaths = readdirSync(managedDirectoryPath, { withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith('.tsx'))
    .map((entry) => path.posix.join(workspace.managedDirectory, entry.name))
    .sort()

  const missingPaths = expectedPaths.filter((expectedPath) => !actualPaths.includes(expectedPath))
  const unexpectedPaths = actualPaths.filter((actualPath) => !expectedPaths.includes(actualPath))

  if (missingPaths.length > 0) {
    addFailure(
      'Managed UI directory is missing pinned shadcn primitives.',
      `Missing: ${missingPaths.join(', ')}.`,
    )
  }

  if (unexpectedPaths.length > 0) {
    addFailure(
      'Managed UI directory contains unexpected files outside the pinned baseline.',
      `Unexpected: ${unexpectedPaths.join(', ')}.`,
    )
  }
}

function verifyComponents() {
  for (const component of manifest.components) {
    const source = readText(component.path)
    if (!source) {
      continue
    }

    const actualHash = sha256(source)
    if (actualHash !== component.sha256) {
      addFailure(
        `${component.name} is out of sync with the pinned shadcn baseline.`,
        `Expected sha256 ${component.sha256}, received ${actualHash} for ${component.path}.`,
      )
    }
  }
}

verifyWorkspace()
verifyComponents()

if (failures.length > 0) {
  console.error('shadcn verification failed.')
  for (const failure of failures) {
    console.error(`- ${failure.message}`)
    if (failure.details) {
      console.error(`  ${failure.details}`)
    }
  }
  process.exit(1)
}

console.log(
  `Verified ${manifest.components.length} shadcn-managed primitives against the pinned repo-local baseline. native-select is verified locally because this repo does not use an upstream registry override for that component.`,
)
