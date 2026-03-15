import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach, vi } from 'vitest'

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

const createStorageMock = () => {
  const entries = new Map<string, string>()
  return {
    get length() {
      return entries.size
    },
    clear() {
      entries.clear()
    },
    getItem(key: string) {
      return entries.get(String(key)) ?? null
    },
    key(index: number) {
      return Array.from(entries.keys())[index] ?? null
    },
    removeItem(key: string) {
      entries.delete(String(key))
    },
    setItem(key: string, value: string) {
      entries.set(String(key), String(value))
    },
  } satisfies Storage
}

const localStorageMock = createStorageMock()
const sessionStorageMock = createStorageMock()

if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver
}

Object.defineProperty(globalThis, 'localStorage', {
  configurable: true,
  value: localStorageMock,
})

Object.defineProperty(globalThis, 'sessionStorage', {
  configurable: true,
  value: sessionStorageMock,
})

if (typeof window !== 'undefined') {
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: localStorageMock,
  })

  Object.defineProperty(window, 'sessionStorage', {
    configurable: true,
    value: sessionStorageMock,
  })
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
