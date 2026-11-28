# CI and the `master` gate

Every change reaches `master` through a pull request, and the pull request can merge only when the **CI result** check is green on a branch that's up to date with `master`, and CodeQL reports no new high- or critical-severity alert. This page lists every check, the command that reproduces it locally, and how to fix the usual failures.

Workflows: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) (the gate) and [`.github/workflows/codeql.yml`](../.github/workflows/codeql.yml) (static security analysis). Branch protection: [`.github/rulesets/master.json`](../.github/rulesets/master.json).

## Quick reference

All backend commands run from `backend/`; frontend commands run from `frontend/`. Integration tests and migration checks need the test database (see the [README](../README.md#running-checks-locally-same-as-ci)): `export TEST_DATABASE_URL=postgresql+asyncpg://recliniq:recliniq@localhost:5432/recliniq_test` (the Alembic steps use `DATABASE_URL` pointed at the same database).

| Job → step | Local command |
|---|---|
| Backend → Lint | `uv run ruff check .` (auto-fix: `--fix`) |
| Backend → Format check | `uv run ruff format --check .` (fix: `uv run ruff format .`) |
| Backend → Type check | `uv run mypy` |
| Backend → Architecture contracts | `uv run lint-imports` |
| Backend → Migrations | `uv run alembic upgrade head && uv run alembic check && uv run alembic downgrade base && uv run alembic upgrade head` |
| Backend → OpenAPI snapshot | `uv run python -m scripts.export_openapi --check` |
| Backend → Tests with coverage | `uv run pytest --cov=app --cov-report=term-missing --cov-fail-under=80` |
| Frontend → Lint and format | `npm run lint` (fix formatting: `npm run format`) |
| Frontend → Generated API types | `npm run api:generate`, then `git status src/api/generated` |
| Frontend → Type check | `npm run typecheck` |
| Frontend → Tests with coverage | `npm run test:coverage` |
| Frontend → Build | `npm run build` |
| Security → Secret scan | `docker run --rm -v "$PWD:/repo" -w /repo zricethezav/gitleaks:v8.30.0 git --config .gitleaks.toml --log-opts="--all"` (repo root) |
| Security → Backend audit | `uv export --frozen --no-emit-project --quiet > /tmp/req.txt && uvx pip-audit -r /tmp/req.txt --strict --require-hashes --disable-pip` |
| Security → Frontend audit | `npm audit --audit-level=high` |
| Compose smoke test | `docker compose up --build --wait`, then open the backend readiness URL and the frontend |
| CodeQL | Runs only on GitHub; see alerts under **Security → Code scanning** |

Most of the fast checks also run on every commit through [pre-commit hooks](#pre-commit-hooks).

## How the pipeline is organised

- **Detect changes** decides which jobs a pull request needs. Changes under `backend/` run the backend job, changes under `frontend/` run the frontend job, and changes to shared pipeline files (the CI workflow, `.github/scripts/`, `docker-compose.yml`, `.env.example`, `.pre-commit-config.yaml`, `.gitleaks.toml`) run both. Pushes to `master` always run everything.
- **Security** always runs the secret scan; the dependency audits follow the backend/frontend selection.
- **Compose smoke test** runs when either app changed.
- **CI result** always runs last. It fails if any job failed or was cancelled, and passes when every job passed or was skipped as not applicable. It's the only CI check branch protection requires, so adding or renaming jobs never needs a ruleset change, and a docs-only pull request still gets a green check.

## Backend checks

### Lint, format, and types
ruff runs with the rule set in `backend/pyproject.toml`, including the `S` (Bandit) security rules. mypy runs in strict mode over `app/` and `scripts/`.

### Architecture contracts
`backend/.importlinter` enforces the clean-architecture layering:

| Contract | Rule |
|---|---|
| Layers | `presentation` may import `application` and `domain`; `application` may import `domain`; never upwards |
| Pure domain | `app.domain` imports no other layer and none of `fastapi`, `starlette`, `sqlalchemy` |
| Application ports | `app.application` doesn't import `infrastructure` or `presentation` |
| Composition root | in `app.presentation`, only `dependencies.py` imports `app.infrastructure` |
| Routers without ORM | `app.presentation.api` doesn't import `sqlalchemy` directly |

**Fixing a failure:** the output names the offending import chain. Don't build adapters in routers or security code: add a provider to `presentation/dependencies.py` (like `UserRepositoryDep`) and depend on the port (a Protocol in `application/<feature>/ports.py`). If a domain type needs a framework feature, keep the framework part in presentation or infrastructure.

### Hard-delete ban
`tests/unit/test_no_hard_deletes.py` scans `app/` and `alembic/versions/` and fails on SQLAlchemy `delete()`, `session.delete(...)`, `query(...).delete()`, or a raw `DELETE FROM` string. Records are removed with `SoftDeleteRepository.soft_delete()` (see `backend/README.md` → Soft delete).

The only exemption is a table in `SOFT_DELETE_EXEMPT_TABLES` (today: `rate_limit_counters`). Mark the line, or the line directly above it, with a reason:

```python
# hard-delete-ok: rate_limit_counters is exempt from soft delete (expired windows)
delete(RateLimitCounterModel).where(...)
```

A marker without a reason, or one left behind after its delete was removed, also fails.

### Migrations
CI applies all migrations, runs `alembic check` (fails if a model change has no migration), then downgrades to base and upgrades again. The integration tests additionally check for a single head.

**Fixing a failure:** `uv run alembic revision --autogenerate -m "describe change"`, review the generated file (remember `protect_from_hard_delete(table)` for new tables), and make sure `downgrade()` reverses `upgrade()` exactly.

### Tests and coverage
The backend job runs unit and integration tests against PostgreSQL 16 and fails below **80%** line coverage of `app/`. Baseline when the gate was introduced: **97%**. The threshold is set on the CI command line (not in `pyproject.toml`) because a local run without `TEST_DATABASE_URL` skips the integration tests and would read low.

**Fixing a failure:** run the coverage command above and add tests for the lines listed under `Missing`. Don't lower the threshold to get a pull request through.

## API contract

The backend's OpenAPI schema is committed as `frontend/src/api/generated/openapi.json`, and the frontend's API types are generated from it into `frontend/src/api/generated/schema.ts`. Hand-written modules in `frontend/src/api/` alias the generated types (`components['schemas']['TokenResponse']`) and type request bodies with `satisfies`, so a backend change the frontend doesn't match fails `npm run typecheck`.

CI fails when:
- the snapshot differs from what the backend produces (backend job), or
- `schema.ts` is stale compared with the snapshot (frontend job), or
- the frontend no longer type-checks against the generated types (frontend job).

**After changing a request or response model:**

```bash
cd backend && uv run python -m scripts.export_openapi
cd ../frontend && npm run api:generate && npm run typecheck
```

Commit both generated files together with the backend change. Never edit them by hand.

The types are generated by `frontend/scripts/generate-api-types.mjs`, a small dependency-free generator. `openapi-typescript` 7 needs the TypeScript 5 compiler API, which TypeScript 7 no longer ships, and `openapi-typescript` 6 fails the npm audit. If you need a JSON Schema feature the generator doesn't support, it throws `Unsupported …`. Extend it and its tests in `generate-api-types.test.mjs`.

## Frontend checks

- **Lint and format:** oxlint with `--deny-warnings` (`frontend/.oxlintrc.json`: correctness errors and suspicious warnings, plus React, TypeScript, import, vitest, and jsx-a11y plugins), and Prettier.
- **Type check:** `tsc -b` with `strict` and `noUncheckedIndexedAccess`.
- **Tests and coverage:** vitest, failing below **70%** line coverage of `src/` (tests, test helpers, and generated files excluded). Baseline when the gate was introduced: **96%**. Thresholds live in `frontend/vite.config.ts`.
- **Build:** `vite build`.

## Security checks

### Secret scanning
gitleaks scans the **full git history** in CI and the staged changes in the pre-commit hook, with the default rules plus `.gitleaks.toml`. GitHub secret scanning and push protection are also enabled on the repository.

**Fixing a failure:** if the secret is real, **rotate it first**. Removing it from the branch doesn't remove it from history. Then remove it from the code and load it from configuration (`app/core/config.py` + `.env.example`). If it's a deliberately fake value, add the exact value (never a whole path) to the allowlist in `.gitleaks.toml` with a description.

### Dependency audits
- **Backend:** `pip-audit` checks the locked dependencies (including dev tools) and fails on **any** known vulnerability, because its advisory data has no consistent severity.
- **Frontend:** `npm audit` fails on high or critical advisories.

**Fixing a failure:** upgrade the package (`uv lock --upgrade-package <name>` / `npm update <name>`, or bump the version). If no fixed version exists yet and the vulnerable code path isn't reachable, add the advisory ID to `backend/.pip-audit-ignore` as `<ID>  # <reason>, review-by YYYY-MM-DD`, and remove it by that date. Ignoring npm advisories isn't supported; use an `overrides` entry in `package.json` to force a patched transitive version.

### CodeQL
`codeql.yml` analyses Python and JavaScript/TypeScript with the `security-extended` queries on every pull request to `master`, on pushes to `master`, and weekly. Alerts appear on the pull request and under **Security → Code scanning**. A new **high or critical** alert blocks merging. Fix the code, or, if it's a false positive, dismiss the alert with a reason in the GitHub UI.

### Supply chain
- Every third-party action is pinned to a full commit SHA with the version in a comment (`uses: owner/action@<sha> # vX.Y.Z`). Never use a tag or branch.
- Each workflow declares `permissions`. The default is `contents: read`; only CodeQL's analyze job gets `security-events: write`.
- Dependabot (`.github/dependabot.yml`) opens weekly update pull requests for GitHub Actions, backend (`uv`), frontend (`npm`), and the Docker base images. Minor and patch updates are grouped.

## Compose smoke test

CI builds the images, starts the stack from `docker-compose.yml` with the values in `.env.example` (file polling off), waits for the healthchecks, and checks that `GET /api/v1/health/ready` succeeds and the frontend serves its page. On failure, the job prints all service logs.

**Fixing a failure:** reproduce with `docker compose up --build`, then read `docker compose logs backend` (migrations run at startup, so a broken migration shows up here).

## Reports

Each test job uploads its JUnit results and coverage (`backend-reports`, `frontend-reports`) as build artifacts, including when tests fail, and writes test counts and coverage to the job summary. Open the run from the pull request's checks to see them.

## Pre-commit hooks

`.pre-commit-config.yaml` runs the same commands as CI, with the same tools and config:
- gitleaks on staged changes;
- for backend changes: ruff, the format check, mypy, the architecture contracts, and the OpenAPI snapshot check;
- for frontend changes: `npm run lint` and `npm run typecheck`.

```bash
uvx pre-commit install                        # once per clone
uvx pre-commit install --hook-type pre-push   # optional: run backend and frontend tests before push
uvx pre-commit run --all-files                # run every hook by hand
```

Hooks check what's **staged**: unstaged edits are set aside while they run. To skip one slow hook for a single commit, use `SKIP=mypy git commit …`; CI still runs it.

## Branch protection (ruleset)

`.github/rulesets/master.json` is the source of truth for protecting `master`:
- pull requests only;
- **CI result** must pass on an up-to-date branch;
- no new high or critical CodeQL alerts;
- no force pushes and no deletion;
- no bypass actors.

Required approvals are **0** because the repository has a single maintainer, and GitHub doesn't allow approving your own pull request. Raise `required_approving_review_count` to `1` when a second maintainer joins.

Applying it requires admin access:

```bash
# Create (first time)
gh api repos/rbcadaing/recliniq/rulesets --method POST --input .github/rulesets/master.json

# Update after editing the file
id=$(gh api repos/rbcadaing/recliniq/rulesets --jq '.[] | select(.name=="master") | .id')
gh api "repos/rbcadaing/recliniq/rulesets/$id" --method PUT --input .github/rulesets/master.json

# Emergency: CI itself is broken and a fix can't merge. Disable, merge the fix, re-enable.
gh api "repos/rbcadaing/recliniq/rulesets/$id" --method PUT -F enforcement=disabled
gh api "repos/rbcadaing/recliniq/rulesets/$id" --method PUT -F enforcement=active
```

Edit the file and apply it in the same pull request, so the repository settings never drift from what's committed.
