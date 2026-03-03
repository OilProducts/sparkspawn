import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver
}

afterEach(() => {
  cleanup()
  if (typeof localStorage?.clear === 'function') {
    localStorage.clear()
  }
  if (typeof sessionStorage?.clear === 'function') {
    sessionStorage.clear()
  }
})
