## Why

RecliniQ now stores real accounts, password hashes, and session tokens, and the medical-record features coming next will be covered by the Data Privacy Act (RA 10173). Today CI (from US-00.1) runs lint, types, and tests, but nothing makes it a gate. Anyone can push directly to `master`. The `push` trigger points at a `main` branch that is no longer used. Actions aren't pinned. Nothing scans for vulnerable dependencies or leaked secrets, and the clean-architecture and soft-delete rules exist only as conventions. US-00.4 (GitHub issue #5, P0) makes the pipeline the enforced gate for `master`, before the codebase grows.

## What Changes

- **Pipeline triggers and gating**
  - CI runs on pull requests targeting `master` and on pushes to `master`. This fixes the stale `main` trigger.
  - A `changes` job detects which areas a change touches (backend, frontend, CI config). Backend and frontend jobs run only when their files or the shared CI config change.
  - A final aggregate `CI result` job always runs. It fails if any job that ran failed. It is the single required status check, so a skipped job never blocks a merge.
- **Branch protection on `master`** (a GitHub repository ruleset, kept in the repo as JSON and applied with `gh api`):
  - Changes reach `master` only through a pull request. Direct pushes and force pushes are blocked, and so is branch deletion.
  - `CI result` must pass, and the branch must be up to date with `master`.
  - Required approvals: **0** for now, because the repo has a single collaborator and GitHub doesn't allow approving your own pull request. Raise it to 1 when a second maintainer joins. This deviates from the issue text, on purpose.
  - Code scanning results are required: a pull request with a new high or critical CodeQL alert can't merge.
- **Supply-chain hardening**
  - Every third-party action is pinned to a full commit SHA, with the version in a comment.
  - Each workflow declares minimal `permissions`. The default is `contents: read`.
  - Dependabot updates GitHub Actions, backend Python (`uv`), frontend npm, and the Docker base images every week.
- **Security checks**
  - `pip-audit` scans the locked backend dependencies, and `npm audit --audit-level=high` scans the frontend.
  - `gitleaks` scans the full git history for secrets.
  - CodeQL runs static analysis for Python and JavaScript/TypeScript, on pull requests and every week.
  - Ruff's `S` (Bandit) rules stay on for the backend.
- **Best-practice checks**: ruff lint and format, and strict mypy, stay as they are for the backend. The frontend **keeps oxlint** (`--deny-warnings`) instead of switching to ESLint, plus Prettier and `tsc` with `strict`, which is already on. This deviates from the issue text, on purpose. Issue #5 will be updated to match.
- **Pre-commit hooks**: a root `.pre-commit-config.yaml` runs the same lint, format, type, and gitleaks checks locally that CI runs.
- **Architecture conformance**
  - `import-linter` contracts enforce the layering: the domain is pure; application doesn't import infrastructure or presentation; only the composition roots (`presentation/dependencies.py`, `app/main.py`) import infrastructure; routers don't import SQLAlchemy.
  - Two existing violations get fixed. `presentation/api/v1/me.py` and `presentation/security.py` currently build `SqlUserRepository` directly; they will get it through `dependencies.py` instead.
- **Hard-delete static check**: a backend test scans `app/` and `alembic/versions/` and fails on any hard delete: a SQLAlchemy `delete()`, `session.delete()`, or a raw `DELETE` statement. The only exception is a line with an explicit `# hard-delete-ok: <reason>` marker, such as the `rate_limit_counters` cleanup. This complements the runtime guard and database trigger from US-00.2.
- **Migration checks**: CI runs `alembic check`, and runs migrations up, then all the way down, then up again, in addition to the existing tests that compare the models with the migrations.
- **API contract check**
  - The backend's OpenAPI schema is exported to a committed file, `frontend/src/api/generated/openapi.json`.
  - TypeScript types are generated from it by a small dependency-free in-repo generator (`frontend/scripts/generate-api-types.mjs`), and the hand-written API modules use those types.
  - CI fails if the committed schema doesn't match the app, if the generated types are stale, or if the client no longer type-checks against them.
- **Coverage and reports**
  - Coverage is measured with `pytest-cov` and `@vitest/coverage-v8`. The build fails below **80%** for the backend and **70%** for the frontend.
  - JUnit and coverage reports are uploaded as build artifacts and summarized in each job's summary, which is linked from the pull request's checks.
- **Compose smoke test**: CI builds the images, starts the stack with `docker compose up --wait`, and checks the backend readiness endpoint and the frontend page.
- **Contributor docs**: `docs/ci.md` explains each check, how to run it locally, and how to fix common failures. The README and `CLAUDE.md` link to it.

Out of scope: deployment and CD pipelines, end-to-end browser tests, performance testing, and container image vulnerability scanning beyond Dependabot base-image updates.

## Capabilities

### New Capabilities
- `supply-chain-security`: pinned and least-privilege workflows, automated dependency updates, dependency vulnerability audits, secret scanning, and static security analysis that block merges on serious findings.
- `architecture-conformance`: automated enforcement of clean-architecture layer boundaries and the static ban on hard deletes.

### Modified Capabilities
- `continuous-integration`: triggers target `master`; change-based job selection behind an always-reporting aggregate check; protection of `master`; coverage thresholds and published reports; migration round-trip and `alembic check`; OpenAPI contract check; and a Compose smoke test.
- `local-dev-environment`: pre-commit hooks that mirror CI checks, and contributor documentation for the pipeline.

## Impact

- **CI and repo settings**: `.github/workflows/ci.yml` is rewritten. New: `.github/workflows/codeql.yml`, `.github/dependabot.yml`, and `.github/rulesets/master.json`. Applying the ruleset changes repository settings on GitHub, which needs admin access.
- **Backend**
  - New dev dependencies: `pytest-cov` and `import-linter`. `pip-audit` runs via `uvx`.
  - New: `scripts/export_openapi.py` and the hard-delete scan test.
  - Refactor: `presentation/security.py` and `api/v1/me.py` get the user repository from `dependencies.py`. Behavior doesn't change.
- **Frontend**
  - New dev dependency: `@vitest/coverage-v8`. New `scripts/generate-api-types.mjs` (no dependencies).
  - New: the generated `src/api/generated/` files and `test:coverage` and `api:generate` scripts.
  - `src/api/auth.ts` and the other API modules switch to the generated types, without changing behavior.
- **Developer workflow**: contributors install `pre-commit` (`uvx pre-commit install`). Pull requests may now fail for coverage, audit, architecture, or contract reasons that were not checked before.
- **Downstream**: every later story inherits these gates. US-00.3, US-01.2, and US-01.4 must keep the architecture contracts and the OpenAPI snapshot passing.
