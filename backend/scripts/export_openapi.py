"""Export the backend's OpenAPI schema to the committed snapshot the frontend types are built from.

    uv run python -m scripts.export_openapi          # rewrite the snapshot
    uv run python -m scripts.export_openapi --check  # exit 1 if the snapshot is out of date (CI)

The app is built with fixed settings (no .env, no database connection), so the output depends
only on the code. See docs/ci.md → "API contract".
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.core.config import Settings, load_settings
from app.main import create_app

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = BACKEND_ROOT.parent / "frontend" / "src" / "api" / "generated" / "openapi.json"
REGENERATE_HINT = "cd backend && uv run python -m scripts.export_openapi"


def _default(field: str) -> Any:
    return Settings.model_fields[field].default


def build_schema() -> dict[str, Any]:
    # Pin every setting that appears in the schema so environment variables can't leak into it.
    settings = load_settings(
        _env_file=None,
        app_env="test",
        app_name=_default("app_name"),
        app_version=_default("app_version"),
        database_url="postgresql+asyncpg://openapi:openapi@127.0.0.1:1/openapi",
    )
    schema: dict[str, Any] = create_app(settings).openapi()
    return schema


def render_schema() -> str:
    return json.dumps(build_schema(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--check", action="store_true", help="fail if the snapshot is stale")
    parser.add_argument("--output", type=Path, default=SNAPSHOT_PATH)
    args = parser.parse_args(argv)

    rendered = render_schema()
    if args.check:
        current = args.output.read_text(encoding="utf-8") if args.output.exists() else ""
        if current != rendered:
            print(
                f"OpenAPI snapshot {args.output} is out of date with the backend.\n"
                f"Regenerate it with `{REGENERATE_HINT}`, then run "
                "`npm run api:generate` in frontend/ and commit both.",
                file=sys.stderr,
            )
            return 1
        print(f"OpenAPI snapshot {args.output.name} is up to date.")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
