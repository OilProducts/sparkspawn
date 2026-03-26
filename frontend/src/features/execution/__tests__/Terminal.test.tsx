import { Terminal } from '@/features/execution/components/Terminal'
import { useStore } from '@/store'
import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

const resetTerminalState = () => {
  useStore.setState((state) => ({
    ...state,
    viewMode: 'execution',
    selectedRunId: null,
    runtimeStatus: 'idle',
    logs: [
      {
        time: '12:00:00',
        msg: 'First log line',
        type: 'info',
      },
    ],
  }))
}

describe('Execution terminal footer', () => {
  beforeEach(() => {
    resetTerminalState()
  })

  it('supports resizing from the top drag handle', () => {
    render(<Terminal />)

    const footer = screen.getByTestId('execution-footer-stream')
    const handle = screen.getByTestId('execution-footer-resize-handle')

    expect(footer).toHaveStyle({ height: '288px' })

    fireEvent.mouseDown(handle, { clientY: 400 })
    fireEvent.mouseMove(window, { clientY: 320 })
    fireEvent.mouseUp(window)

    expect(footer).toHaveStyle({ height: '368px' })
  })
})
