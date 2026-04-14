## Remote Project Picker for SSH-Tunneled Spark

### Summary

Replace the current Add Project picker flow with a browser-based remote directory browser that navigates the Spark host filesystem. Remove both the backend native picker path and the
browser-local directory input fallback. The new flow should always browse the server filesystem, start in the Spark service user’s home directory, allow navigation anywhere on the host
filesystem, and register the selected directory through the existing project registration flow.

### Key Changes

- Add a new workspace API for remote directory browsing.
    - Introduce GET /workspace/api/projects/browse?path=<abs-path> (or equivalent GET shape) under the existing workspace router.
    - If path is omitted, browse starts at the Spark service user’s home directory.
    - Response shape should be decision-complete and directory-focused:
        - current_path: string
        - parent_path: string | null
        - entries: Array<{ name: string; path: string; is_dir: true }>
    - Only directories are returned. Files are not listed.
    - Paths must be normalized on the server and required to be absolute after normalization.
    - Invalid or non-directory paths return a clear 400/404.
    - Root / must be browsable.
- Replace the Add Project UI flow with a remote browser modal.
    - Clicking Add opens a modal, not a native picker and not a hidden file input.
    - Modal contents:
        - breadcrumb/path display for the current server path
        - parent navigation
        - directory list for the current path
        - explicit “Select this folder” action for the current directory
    - Selecting a directory row navigates into it.
    - Registration happens only when the operator confirms the current folder.
    - Default open location is the Spark host user’s home directory.
    - Full filesystem navigation is allowed; no scoped-root restriction.
- Remove legacy picker behavior from the Add flow.
    - Frontend stops calling /workspace/api/projects/pick-directory.
    - Remove the browser webkitdirectory fallback and hidden file input from the navbar flow.
    - Remove or retire the backend native picker endpoint and its dependency wiring so Add Project is consistently remote-friendly.
- Preserve existing project registration semantics.
    - Keep using the existing metadata validation and /workspace/api/projects/register path after a folder is chosen.
    - Do not add a new Git requirement; non-Git directories should continue to behave the same way they do today.
    - Duplicate-path handling stays as-is through existing client/server validation.

### Implementation Notes

- Backend should reuse the existing path normalization approach used for project paths so returned paths are canonical and stable.
- Directory listing should be sorted predictably, case-insensitive by name.
- Hidden directories should remain visible; user explicitly chose full-filesystem browsing.
- The modal can reuse the existing dialog system and tree/list styling patterns already present in the frontend, but this should be a dedicated project-browser surface rather than
  repurposing the browser file input.
- The navbar remains the primary entry point for Add Project; no secondary local-desktop/native picker action is retained.

### Test Plan

- Backend tests:
    - browsing with no path starts at the service user home directory
    - browsing / works
    - browsing a valid absolute directory returns normalized current_path, correct parent_path, and directory-only entries
    - non-absolute, missing, and file paths return the correct error
- Frontend tests:
    - Add Project opens the remote browser modal instead of invoking native picker logic or browser file input
    - navigating into directories updates the displayed current path and entries
    - parent navigation and root/home traversal work
    - selecting the current folder runs the existing metadata + registration flow and updates the project registry
    - duplicate registration still surfaces the existing duplicate-path error
    - backend browse errors surface a clear project-add error state
- Regression coverage:
    - existing project switcher, registration, and delete flows remain intact
    - no test should rely on browser-local directory selection for project add

### Assumptions

- Add Project should now always mean “pick a directory on the Spark host,” not on the browser client.
- Full filesystem browsing is intentionally allowed.
- Default browser start directory is the Spark service user’s home directory.
- Directory selection is explicit via “Select this folder”; entering a directory does not auto-register it.
