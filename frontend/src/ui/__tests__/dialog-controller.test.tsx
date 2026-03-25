import { useState } from 'react'

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { DialogProvider, useDialogController } from '@/ui'

function DialogHarness() {
  const { confirm, prompt } = useDialogController()
  const [result, setResult] = useState('idle')

  return (
    <div>
      <button
        type="button"
        onClick={async () => {
          const confirmed = await confirm({
            title: 'Remove run?',
            description: 'This clears the local execution state.',
            confirmLabel: 'Remove',
            cancelLabel: 'Keep',
          })
          setResult(confirmed ? 'confirmed' : 'cancelled')
        }}
      >
        Open confirm
      </button>
      <button
        type="button"
        onClick={async () => {
          const value = await prompt({
            title: 'Rename flow',
            description: 'Provide a new flow path.',
            label: 'Flow path',
            confirmLabel: 'Save',
            cancelLabel: 'Cancel',
            requireInput: true,
          })
          setResult(value ?? 'cancelled')
        }}
      >
        Open prompt
      </button>
      <output data-testid="dialog-result">{result}</output>
    </div>
  )
}

describe('Dialog controller', () => {
  it('resolves confirm dialogs through the shared provider', async () => {
    const user = userEvent.setup()

    render(
      <DialogProvider>
        <DialogHarness />
      </DialogProvider>,
    )

    await user.click(screen.getByRole('button', { name: 'Open confirm' }))

    expect(screen.getByTestId('shared-dialog')).toBeVisible()
    expect(screen.getByTestId('shared-dialog-title')).toHaveTextContent('Remove run?')
    expect(screen.getByTestId('shared-dialog-description')).toHaveTextContent(
      'This clears the local execution state.',
    )

    await user.click(screen.getByTestId('shared-dialog-cancel'))
    expect(screen.getByTestId('dialog-result')).toHaveTextContent('cancelled')

    await user.click(screen.getByRole('button', { name: 'Open confirm' }))
    await user.click(screen.getByTestId('shared-dialog-confirm'))
    expect(screen.getByTestId('dialog-result')).toHaveTextContent('confirmed')
  })

  it('enforces required prompt input before resolving', async () => {
    const user = userEvent.setup()

    render(
      <DialogProvider>
        <DialogHarness />
      </DialogProvider>,
    )

    await user.click(screen.getByRole('button', { name: 'Open prompt' }))

    const confirmButton = screen.getByTestId('shared-dialog-confirm')
    const input = screen.getByTestId('shared-dialog-input')

    expect(confirmButton).toBeDisabled()
    await user.type(input, 'team/review/new-flow.dot')
    expect(confirmButton).toBeEnabled()

    await user.click(confirmButton)
    expect(screen.getByTestId('dialog-result')).toHaveTextContent('team/review/new-flow.dot')
  })
})
