set shell := ["bash", "-lc"]

dev:
  docker compose up --build

stop:
  docker compose down

logs:
  docker compose logs -f

restart:
  docker compose down
  docker compose up --build

dot-lint:
  uv run pytest -q tests/integration/test_dot_format_lint.py

parser-unsupported-grammar:
  uv run pytest -q tests/dsl/test_parser.py -k unsupported_grammar_regression

test:
  uv run pytest -q

frontend-unit:
  npm --prefix frontend run test:unit

ui-smoke:
  npm --prefix frontend run ui:smoke

frontend-build:
  npm --prefix frontend run build

sync-ui-dist:
  ./scripts/sync_ui_dist.sh

wheel:
  uv build

build:
  npm --prefix frontend run build
  ./scripts/sync_ui_dist.sh
  uv build
