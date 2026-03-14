from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence

import httpx

from workspace.project_chat_common import normalize_spec_edit_proposal_payload


DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
SPEC_PROPOSAL_CREATE_EXAMPLE = """{
  "summary": "Clarify the approval gate before planning begins.",
  "changes": [
    {
      "path": "specs/sparkspawn-workspace.md#proposal-review",
      "before": "Planning begins immediately after a proposal is drafted.",
      "after": "Planning begins only after the user approves the proposal."
    }
  ],
  "rationale": "Ground the workflow in an explicit user approval step."
}"""
SPEC_PROPOSAL_CREATE_STDIN_EXAMPLE = """cat <<'EOF' | sparkspawn spec-proposal create --json -
{
  "summary": "Clarify the approval gate before planning begins.",
  "changes": [
    {
      "path": "specs/sparkspawn-workspace.md#proposal-review",
      "before": "Planning begins immediately after a proposal is drafted.",
      "after": "Planning begins only after the user approves the proposal."
    }
  ],
  "rationale": "Ground the workflow in an explicit user approval step."
}
EOF"""
SPEC_PROPOSAL_CREATE_TEMPFILE_EXAMPLE = '''payload_file=$(mktemp)
cat >"$payload_file" <<'EOF'
{
  "summary": "Clarify the approval gate before planning begins.",
  "changes": [
    {
      "path": "specs/sparkspawn-workspace.md#proposal-review",
      "before": "Planning begins immediately after a proposal is drafted.",
      "after": "Planning begins only after the user approves the proposal."
    }
  ]
}
EOF
sparkspawn spec-proposal create --conversation amber-otter --json "$payload_file"'''


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sparkspawn",
        description="Sparkspawn runtime CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command")

    serve = subparsers.add_parser(
        "serve",
        help="Start the Sparkspawn API server",
    )
    serve.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    serve.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    serve.add_argument("--reload", action="store_true", help="Enable auto-reload (development only)")
    serve.add_argument("--data-dir", type=Path, default=None, help="Runtime data directory root")
    serve.add_argument("--flows-dir", type=Path, default=None, help="Flow storage directory")
    serve.add_argument("--ui-dir", type=Path, default=None, help="Built UI directory (contains index.html)")

    spec_proposal = subparsers.add_parser(
        "spec-proposal",
        help="Create or inspect spec proposal artifacts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    spec_proposal_subparsers = spec_proposal.add_subparsers(dest="spec_proposal_command")

    spec_proposal_create = spec_proposal_subparsers.add_parser(
        "create",
        help="Create a pending spec proposal artifact in a conversation",
        description=(
            "Create a pending spec proposal artifact and inline conversation segment.\n\n"
            "The payload must include:\n"
            "  summary: short description of the proposed spec change\n"
            "  changes: minimal grounded before/after edits\n"
            "  rationale: optional explanation for the proposal\n\n"
            "The command requires a conversation handle supplied with --conversation.\n"
            "The command resolves the target assistant turn automatically.\n"
            "Do not include turn_id in the payload.\n"
            "This command does not approve or apply the proposal.\n\n"
            "Prefer piping the payload with --json - so no proposal file is left behind.\n"
            "If stdin is not practical, write the payload to a temporary file outside the project repository."
        ),
        epilog=(
            "Preferred stdin example:\n"
            + SPEC_PROPOSAL_CREATE_STDIN_EXAMPLE
            + "\n\nFallback temp-file example:\n"
            + SPEC_PROPOSAL_CREATE_TEMPFILE_EXAMPLE
            + "\n\nExample JSON payload:\n"
            + SPEC_PROPOSAL_CREATE_EXAMPLE
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    spec_proposal_create.add_argument(
        "--json",
        dest="json_path",
        required=True,
        help="Path to a JSON payload file, or '-' to read the payload from stdin.",
    )
    spec_proposal_create.add_argument(
        "--conversation",
        required=True,
        help="Conversation handle in adjective-noun form, for example 'amber-otter'.",
    )
    spec_proposal_create.add_argument(
        "--base-url",
        default=os.environ.get("SPARKSPAWN_API_BASE_URL", DEFAULT_API_BASE_URL),
        help=f"Sparkspawn server base URL (default: {DEFAULT_API_BASE_URL}).",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "command", None):
        parser.print_help()
        return 0

    if args.command == "serve":
        return _run_serve(args)
    if args.command == "spec-proposal":
        return _run_spec_proposal(args)

    parser.error(f"Unknown command: {args.command}")
    return 2


def _run_spec_proposal(args: argparse.Namespace) -> int:
    if not getattr(args, "spec_proposal_command", None):
        print("Usage: sparkspawn spec-proposal <command>\n")
        print("Commands:")
        print("  create   Create a pending spec proposal artifact in a conversation")
        print("\nRun `sparkspawn spec-proposal create --help` for the full payload contract.")
        return 0
    if args.spec_proposal_command == "create":
        return _run_spec_proposal_create(args)
    raise ValueError(f"Unknown spec-proposal command: {args.spec_proposal_command}")


def _run_spec_proposal_create(args: argparse.Namespace) -> int:
    try:
        raw_payload = _read_json_input(str(args.json_path))
        payload = json.loads(raw_payload)
    except FileNotFoundError:
        print(json.dumps({"ok": False, "error": f"JSON file not found: {args.json_path}"}), file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": (
                        f"Invalid JSON in {args.json_path} at line {exc.lineno}, column {exc.colno}: {exc.msg}. "
                        "Fix the JSON syntax and try again."
                    ),
                }
            ),
            file=sys.stderr,
        )
        return 1

    if not isinstance(payload, dict):
        print(json.dumps({"ok": False, "error": "Proposal payload must be a JSON object."}), file=sys.stderr)
        return 1

    unexpected_keys = sorted(set(payload.keys()) - {"summary", "changes", "rationale"})
    if unexpected_keys:
        if "conversation_id" in unexpected_keys:
            error = (
                "Do not include conversation_id in the JSON payload. "
                "Pass the target thread with --conversation adjective-noun instead."
            )
        elif "turn_id" in unexpected_keys:
            error = (
                "Do not include turn_id in the JSON payload. "
                "Spark Spawn places the proposal on the correct assistant turn automatically."
            )
        elif "project_path" in unexpected_keys:
            error = (
                "Do not include project_path in the JSON payload. "
                "The conversation handle already determines the owning project."
            )
        else:
            keys = ", ".join(unexpected_keys)
            error = (
                f"Unexpected payload field(s): {keys}. "
                "Allowed fields are summary, changes, and optional rationale."
            )
        print(json.dumps({"ok": False, "error": error}), file=sys.stderr)
        return 1

    conversation_handle = str(args.conversation or "").strip()
    if not conversation_handle:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "Missing required --conversation handle. Use the adjective-noun handle shown for the thread, for example 'amber-otter'.",
                }
            ),
            file=sys.stderr,
        )
        return 1

    try:
        payload = normalize_spec_edit_proposal_payload(
            payload,
            source_name="sparkspawn spec-proposal create",
        )
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1

    base_url = str(args.base_url).rstrip("/")
    request_url = f"{base_url}/workspace/api/conversations/by-handle/{conversation_handle}/spec-edit-proposals"

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(request_url, json=payload)
    except httpx.HTTPError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": f"Request failed: {exc}",
                }
            ),
            file=sys.stderr,
        )
        return 1

    try:
        response_payload = response.json()
    except ValueError:
        response_payload = {"detail": response.text}

    if response.is_error:
        error_detail: object
        if isinstance(response_payload, dict):
            error_detail = response_payload.get("detail")
        else:
            error_detail = response.text
        if isinstance(error_detail, list):
            message = "; ".join(_format_validation_error(entry) for entry in error_detail)
        elif isinstance(error_detail, str):
            message = error_detail
        else:
            message = response.text
        print(
            json.dumps(
                {
                    "ok": False,
                    "status_code": response.status_code,
                    "error": message,
                }
            ),
            file=sys.stderr,
        )
        return 1

    print(json.dumps(response_payload, indent=2, sort_keys=True))
    return 0


def _read_json_input(json_path: str) -> str:
    if json_path == "-":
        return sys.stdin.read()
    return Path(json_path).read_text(encoding="utf-8")


def _format_validation_error(value: object) -> str:
    if not isinstance(value, dict):
        return str(value)
    location = value.get("loc")
    message = str(value.get("msg") or "Invalid request.")
    if isinstance(location, (list, tuple)) and location:
        path = ".".join(str(part) for part in location if part != "body")
        if path:
            return f"{path}: {message}"
    return message


def _run_serve(args: argparse.Namespace) -> int:
    import uvicorn

    import attractor.api.server as server
    from attractor.config import ENV_FLOWS_DIR, ENV_HOME_DIR, ENV_UI_DIR

    def _set_path_env(name: str, value: Path | None) -> None:
        if value is None:
            return
        os.environ[name] = str(value.expanduser().resolve(strict=False))

    server.configure_runtime_paths(
        data_dir=args.data_dir,
        flows_dir=args.flows_dir,
        ui_dir=args.ui_dir,
    )
    server.validate_runtime_paths()
    _set_path_env(ENV_HOME_DIR, args.data_dir)
    _set_path_env(ENV_FLOWS_DIR, args.flows_dir)
    _set_path_env(ENV_UI_DIR, args.ui_dir)

    uvicorn.run(
        "attractor.api.server:app" if args.reload else server.app,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
