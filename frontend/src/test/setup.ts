import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach, vi } from 'vitest'

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver
}

beforeEach(() => {
  vi.stubGlobal('confirm', vi.fn(() => true))
})

afterEach(() => {
  cleanup()
  if (typeof localStorage?.clear === 'function') {
    localStorage.clear()
  }
  if (typeof sessionStorage?.clear === 'function') {
    sessionStorage.clear()
  }
  if (typeof globalThis.confirm === 'function' && 'mockClear' in globalThis.confirm) {
    ;(globalThis.confirm as unknown as { mockClear: () => void }).mockClear()
  }
})
