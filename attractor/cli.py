from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sparkspawn",
        description="Sparkspawn runtime CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser(
        "serve",
        help="Start the Sparkspawn API server",
    )
    serve.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    serve.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    serve.add_argument("--reload", action="store_true", help="Enable auto-reload (development only)")
    serve.add_argument("--data-dir", type=Path, default=None, help="Runtime data directory root")
    serve.add_argument("--runs-dir", type=Path, default=None, help="Run records directory")
    serve.add_argument("--flows-dir", type=Path, default=None, help="Flow storage directory")
    serve.add_argument("--ui-dir", type=Path, default=None, help="Built UI directory (contains index.html)")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "serve":
        return _run_serve(args)

    parser.error(f"Unknown command: {args.command}")
    return 2


def _run_serve(args: argparse.Namespace) -> int:
    import uvicorn

    import attractor.api.server as server

    server.configure_runtime_paths(
        data_dir=args.data_dir,
        runs_dir=args.runs_dir,
        flows_dir=args.flows_dir,
        ui_dir=args.ui_dir,
    )
    server.validate_runtime_paths()

    uvicorn.run(
        server.app,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
