from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from typing import Sequence

import spark.starter_assets as starter_assets


def _build_runtime_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spark",
        description="Spark operator CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command")

    serve = subparsers.add_parser(
        "serve",
        help="Start the Spark API server",
    )
    serve.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    serve.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    serve.add_argument("--reload", action="store_true", help="Enable auto-reload (development only)")
    serve.add_argument("--data-dir", type=Path, default=None, help="Runtime data directory root")
    serve.add_argument("--flows-dir", type=Path, default=None, help="Flow storage directory")
    serve.add_argument("--ui-dir", type=Path, default=None, help="Built UI directory (contains index.html)")

    init = subparsers.add_parser(
        "init",
        help="Initialize Spark runtime directories and seed starter flows",
    )
    init.add_argument("--data-dir", type=Path, default=None, help="Runtime data directory root")
    init.add_argument("--flows-dir", type=Path, default=None, help="Flow storage directory")
    init.add_argument("--force", action="store_true", help="Overwrite existing starter flows")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_runtime_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "command", None):
        parser.print_help()
        return 0

    if args.command == "serve":
        return _run_serve(args)
    if args.command == "init":
        return _run_init(args)
    parser.error(f"Unknown command: {args.command}")
    return 2


def _run_serve(args: argparse.Namespace) -> int:
    import uvicorn

    import attractor.api.server as server
    import spark_app.app as product_app
    from spark_common.settings import ENV_FLOWS_DIR, ENV_HOME_DIR, ENV_UI_DIR

    def _set_path_env(name: str, value: Path | None) -> None:
        if value is None:
            return
        os.environ[name] = str(value.expanduser().resolve(strict=False))

    server.configure_runtime_paths(
        data_dir=args.data_dir,
        runs_dir=None,
        flows_dir=args.flows_dir,
        ui_dir=args.ui_dir,
    )
    server.validate_runtime_paths()
    _set_path_env(ENV_HOME_DIR, args.data_dir)
    _set_path_env(ENV_FLOWS_DIR, args.flows_dir)
    _set_path_env(ENV_UI_DIR, args.ui_dir)

    uvicorn.run(
        "spark_app.app:app" if args.reload else product_app.app,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


def _run_init(args: argparse.Namespace) -> int:
    from spark_common.settings import resolve_settings, validate_settings

    settings = resolve_settings(
        data_dir=args.data_dir,
        flows_dir=args.flows_dir,
    )
    validate_settings(settings)

    try:
        result = starter_assets.seed_starter_flows(
            settings.flows_dir,
            force=args.force,
            project_root=settings.project_root,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Initialized Spark at {settings.data_dir}")
    print(f"Starter flows: {result.flows_dir}")
    print(
        "created={created} updated={updated} skipped={skipped}".format(
            created=len(result.created),
            updated=len(result.updated),
            skipped=len(result.skipped),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
