# Reset Copy Success Feedback

## Summary

Update the delivered `TranscriptCopyButton` so a successful copy shows the checkmark and “copied” accessible label for two seconds, then returns to the normal copy state.

## Implementation

- In `TranscriptCopyButton`, schedule `status` to return from `copied` to `idle` after 2,000 ms.
- Clear any existing reset timer before scheduling another copy result, so repeated clicks restart the two-second window.
- Clear the timer on component unmount to avoid state updates after unmount.
- Preserve the current failure behavior and all message/code-block eligibility rules.
- Apply the correction to the run’s feature branch before integrating it into `main`.

## Tests

- Use fake timers to verify successful copy changes the button to “copied.”
- Verify it remains copied before two seconds and resets at two seconds.
- Verify a second successful click restarts the timer.
- Verify unmounting clears the pending timer.
- Run the focused project conversation tests and frontend typecheck/build.

## Assumptions

- The requested fix concerns only persistent success feedback.
- The reset duration is two seconds.
- Tooltip and unrelated commit-cleanup concerns are separate from this correction.
