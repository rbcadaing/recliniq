## Context

See proposal.md (Why) for the motivation. The current state that shapes the approach:

- `.github/workflows/ci.yml` has two jobs, `backend` and `frontend`. It triggers on all pull requests and on `push` to `main`, and uses tag-pinned actions (`actions/checkout@v5`, `astral-sh/setup-uv@v7`, `actions/setup-node@v5`). Its permissions are already `contents: read` at the top level.
- The repo is **public**, `rbcadaing/recliniq`, with a single collaborator. Because it's public, rulesets, CodeQL, code-scanning merge protection, and GitHub secret scanning are all free.
- The backend already has ruff (including the `S`/Bandit rules), strict mypy over `app/`, and pytest with auto-marked integration tests.
  - `tests/integration/test_database.py` already checks migrations up and down, a single head, and that the models match the migrations (`compare_metadata`).
  - Unit tests already check that every model uses `SoftDeleteMixin`.
- The frontend already uses oxlint (`correctness` = error, `suspicious` = warn, run with `--deny-warnings`), Prettier, `tsc -b` with `strict` and `noUncheckedIndexedAccess`, and vitest.
- API types in `frontend/src/api/*.ts` are written by hand.
- There are two known layering violations: `presentation/api/v1/me.py` and `presentation/security.py` both import `SqlUserRepository` from infrastructure.
- `infrastructure/accounts/rate_limiter.py` has the one legitimate hard delete, on `rate_limit_counters`, the only table in `SOFT_DELETE_EXEMPT_TABLES`.
- The Compose stack (`db`, `backend`, `mailpit`, `frontend`) already has healthchecks. The backend healthcheck calls `/api/v1/health/ready`. Compose reads values from the root `.env`.

## Goals / Non-Goals

**Goals:**
- Every rule in the specs is enforced by a command that runs the same way in CI and locally.
- Keep a typical pull request's wall-clock CI time close to today's by running independent jobs in parallel and skipping areas a change doesn't touch.
- Keep the repo-settings part (the ruleset) declarative and reviewable as a file.

**Non-Goals:**
- Sticky pull request comments or third-party coverage services such as Codecov. Job summaries are enough.
- Mutation testing, end-to-end browser tests, and container image CVE scanning.
- Replacing the existing `compare_metadata` or soft-delete coverage tests. The new checks complement them.

## Decisions

### D1. Path filtering behind one aggregate required check
A `changes` job uses `dorny/paths-filter` to emit `backend`, `frontend`, and `ci` outputs. A backend-only job runs when `backend || ci`, and a frontend-only job runs when `frontend || ci`. Pushes to `master` run everything.

A final `ci-result` job (shown as **CI result**) runs with `if: always()` and `needs:` every other job. It fails if any needed job's result is `failure` or `cancelled`. This is the **only** CI check named in the ruleset.

- *Why:* GitHub treats a required check that never reports as pending forever. Workflow-level `paths:` filters cause exactly that. One aggregate check also means the ruleset doesn't need editing when jobs are added or renamed.
- *Alternatives:* list every job as a required check, which is brittle and doesn't work with skipped jobs; or skip path filtering, which wastes minutes on docs-only and frontend-only pull requests.

### D2. Job layout (ci.yml)
| Job | Runs when | Contents |
|---|---|---|
| `changes` | always | paths-filter |
| `backend` | backend/ci | uv sync → ruff check, ruff format --check → mypy → `lint-imports` → `alembic check` → migration round trip (`upgrade head`, `downgrade base`, `upgrade head`) → pytest with coverage and JUnit (`--cov=app --cov-fail-under=80`) → OpenAPI snapshot diff |
| `frontend` | frontend/ci | npm ci → lint → `api:generate` + `git diff --exit-code` → typecheck → `test:coverage` (thresholds in config) → build |
| `security` | always | gitleaks (full history, `fetch-depth: 0`) → `pip-audit` (backend/ci) → `npm audit --audit-level=high --omit=dev` and a full `npm audit` (frontend/ci) |
| `smoke` | backend/frontend/ci | `cp .env.example .env` → `docker compose up --build --wait --wait-timeout 180` → curl readiness and the frontend root → on failure, `docker compose logs` → always `down -v` |
| `ci-result` | always | aggregate (D1) |

CodeQL lives in its own `codeql.yml` (python and javascript-typescript, `build-mode: none`, pull requests to `master`, pushes to `master`, and a weekly cron). It runs separately because it needs `security-events: write` and has its own schedule. Its alerts gate merges through the ruleset's **code scanning** rule (D4), not through `ci-result`.

- *`alembic check` and a CI round-trip step in addition to the existing pytest tests:* the pytest tests can be skipped locally when `TEST_DATABASE_URL` isn't set. The explicit CI steps can't be skipped, and their output is clearer in the log.
- *Coverage threshold on the CI command line, not in `pyproject.toml`:* local `uv run pytest` without a database skips the integration tests, and would fail an 80% threshold for no real reason. The frontend has no such split, so its thresholds live in `vite.config.ts`.

### D3. Pin actions to SHAs and let Dependabot maintain them
Every `uses:` becomes `owner/repo@<40-char sha> # vX.Y.Z`. Dependabot's `github-actions` ecosystem updates SHA pins and keeps the version comment. `dependabot.yml` covers `github-actions` (/), `uv` (/backend), `npm` (/frontend), and `docker` (/backend, /frontend), weekly, with grouped minor and patch updates to reduce noise.

- *Alternative:* Renovate. It's more capable, but it's another GitHub App to install. Dependabot is built in.

### D4. Branch protection as a repository ruleset stored in git
`.github/rulesets/master.json` targets `refs/heads/master` and contains these rules:
- `pull_request` (`required_approving_review_count: 0`, dismiss stale reviews)
- `required_status_checks` (context `CI result`, `strict_required_status_checks_policy: true`)
- `code_scanning` (CodeQL, security alerts `high_or_higher`, alerts `errors`)
- `non_fast_forward`
- `deletion`

`docs/ci.md` documents the command that applies it (`gh api repos/{owner}/{repo}/rulesets --method POST --input …`, or `PUT …/rulesets/{id}` to update). There are **no bypass actors**, so the admin can't push directly either.

- *Why a ruleset instead of classic branch protection:* only rulesets support the code scanning merge gate, and they're stored as plain JSON that can be reviewed.
- *Why 0 approvals:* chosen by the user (single maintainer). The value sits in one JSON field, ready to be raised.
- *Bootstrap order:* the ruleset is applied **after** this branch's first CI run has produced a `CI result` check, so the check name exists when the ruleset refers to it.

### D5. Security tooling choices
- **Secrets:** use the `gitleaks` CLI (a pinned release binary) instead of `gitleaks-action`, which needs a license key for organisations and adds a dependency. A root `.gitleaks.toml` extends the default rules and allow-lists the test-fixture paths and the local-only Compose defaults, such as `local-compose-jwt-secret-not-for-production-use`. GitHub's own secret scanning and push protection are also enabled in the repo settings, which is free for public repos.
- **Python audit:** `uv export --frozen --no-hashes --no-emit-project > requirements.txt`, then `uvx pip-audit -r requirements.txt --strict`. pip-audit uses OSV data, which has no consistent severity, so the build fails on **any** known vulnerability. Accepted risks go into `backend/.pip-audit-ignore` (an ID, reason, and review date per line), which is turned into `--ignore-vuln` flags. This is stricter than "high/critical only", intentionally.
- **npm audit:** `npm audit --audit-level=high`.
- **SAST:** CodeQL (D2) plus ruff `S`. A separate Bandit run isn't added, because ruff's `S` rules are Bandit's rules.

### D6. Architecture contracts with import-linter
`backend/.importlinter` (root package `app`) defines these contracts:
1. **layers:** `app.presentation` > `app.application` > `app.domain`, with `app.infrastructure` handled separately.
2. **forbidden:** `app.domain` must not import `app.application`, `app.infrastructure`, `app.presentation`, `fastapi`, `sqlalchemy`, or `starlette`.
3. **forbidden:** `app.application` must not import `app.infrastructure` or `app.presentation`.
4. **forbidden:** `app.presentation` must not import `app.infrastructure`, with an `ignore_imports` exception for `app.presentation.dependencies -> app.infrastructure.**`.
5. **forbidden:** `app.presentation.api` must not import `sqlalchemy` (`include_external_packages = true`).

`app.main` and `app.core` aren't part of the presentation contracts; `app.main` is the app factory and composition root. `app.infrastructure` importing `app.domain`/`app.application` (ports) is allowed.

**Refactor:** `dependencies.py` gains a `UserRepositoryDep` (or `get_user_repository`) provider. `security.py` and `me.py` consume it instead of building `SqlUserRepository(session)`. If `me.py` uses `SessionDep` only to build the repository, that dependency goes too, which satisfies contract 5.

- *Alternative:* pytest-archon. It's expressive, but the rules would be Python test code. import-linter's declarative config is easier to review, and `lint-imports` gives clear error messages.

### D7. Hard-delete scan as a unit test
`tests/unit/test_no_hard_deletes.py` walks `app/**/*.py` and `alembic/versions/*.py`. It flags:
- an AST `Call` to `delete`/`sa.delete`/`sqlalchemy.delete`;
- any `<expr>.delete(` call whose receiver looks like a session (`session`, `self._session`, `db`, `self.session`);
- any string constant that matches `\bDELETE\s+FROM\b` (case-insensitive).

A flagged line passes only if it, or the line directly above it, carries `# hard-delete-ok: <non-empty reason>`. The test also verifies that every marker is still attached to a delete, so stale markers fail too. It has its own unit tests, run on fixture source strings, in the same style as `test_soft_delete_coverage.py`.

- *Why a pytest test instead of a ruff plugin or Semgrep:* no new tooling, it runs in CI and in local `pytest`, and the logic is about 60 lines.
- *Limitation:* the receiver heuristic can miss creative aliasing. The runtime guard and the database trigger from US-00.2 remain the real backstop. This check is an early warning.

### D8. OpenAPI contract via committed snapshot and generated types
- `backend/scripts/export_openapi.py` builds the app with `create_app(Settings(...))` using dummy settings; no database connection is needed. It writes `app.openapi()` as sorted, indented JSON to `frontend/src/api/generated/openapi.json`. The `--check` flag compares the output with the file instead, and exits 1 with a "run `uv run python -m scripts.export_openapi`" hint if they differ. It runs as a module (`backend/scripts/` is a package) so it can import `app`, and mypy checks it.
- `npm run api:generate` runs `frontend/scripts/generate-api-types.mjs`, which writes `src/api/generated/schema.ts` in openapi-typescript's `components['schemas'][Name]` shape. The generated folder is excluded from oxlint, Prettier, and coverage.
- **Revised during implementation:** the original plan used the `openapi-typescript` package. Version 7 needs the TypeScript 5 JS compiler API, which TypeScript 7 (the native compiler this repo uses) no longer ships. Version 6 pulls in `undici@5`, which fails `npm audit --audit-level=high`. The user chose a small in-repo generator: about 120 lines, no dependencies, covering `$ref`, `anyOf`/`oneOf`/`allOf`, `enum`/`const`, nullable unions, arrays, objects, and maps. It throws on anything else, so unsupported schemas fail loudly. It's written in Node, so the frontend job and `npm run api:generate` don't need Python. It has its own vitest tests, including one that the committed `schema.ts` matches its output. Revisit `openapi-typescript` if a release supports TypeScript 7.
- The hand-written modules (`auth.ts`, `health.ts`, `specializations.ts`) replace their interfaces with aliases such as `export type TokenResponse = components['schemas']['TokenResponse']`. The type names exported to the rest of the app stay the same. Narrower client-side unions, such as `Role`, come from the schema's enums.
- The backend job runs `python -m scripts.export_openapi --check`. The frontend job runs `api:generate`, then fails if `git status --porcelain src/api/generated` isn't empty (this also catches a missing file), then runs `typecheck`. A schema change in a backend pull request therefore touches `frontend/`, which triggers the frontend job.

- *Why not an openapi-fetch typed client:* the existing `client.ts` handles request IDs, auth refresh, and error normalization. Swapping it out is a larger change than the story needs. Types alone catch the drift the story is about.
- *Alternative:* comparing the schema at runtime in tests. Rejected, because a committed snapshot also makes API changes visible in pull request diffs.

### D9. Pre-commit framework
The root `.pre-commit-config.yaml` uses `repo: local` hooks that call the project's own toolchains, so versions match CI exactly:
- `uv run --directory backend ruff check`, `ruff format --check`, `mypy`, and `lint-imports`, for `^backend/`;
- `npm --prefix frontend run lint` and `typecheck`, for `^frontend/`;
- `gitleaks protect --staged`.

Tests aren't run on commit, because they're too slow. They're available as an opt-in `pre-push` stage. Developers install the hooks with `uvx pre-commit install`. CI doesn't run pre-commit itself; it runs the underlying commands directly, so there is only one definition of each check.

- *Alternative:* husky and lint-staged. Rejected, because they're Node-only, and the backend checks need uv.

### D10. Reports
pytest writes `junit.xml` and `coverage.xml` (with `--cov-report=term-missing`). vitest writes JUnit and `coverage/` (text-summary, cobertura, html). The files are uploaded with `actions/upload-artifact` under `if: always()`. A small shell step appends the totals (tests passed, failed, and skipped, and line coverage %) to `$GITHUB_STEP_SUMMARY`. No `pull-requests: write` permission is needed, so it also works for pull requests from forks and Dependabot.

## Risks / Trade-offs

- [Current coverage might already be below 80% or 70%, so the first run fails] → Measure on this branch first. If coverage is short, add tests for the gaps in this change; don't lower the threshold. Record the measured baseline in `docs/ci.md`.
- [The ruleset locks out a broken master, for example if CI itself breaks] → An admin can temporarily disable the ruleset via the UI or `gh api` (documented). There are no standing bypass actors.
- [The code-scanning rule blocks merges if CodeQL doesn't run for a pull request, for example because of path ignores] → CodeQL runs on every pull request to `master`, with no path filters.
- [pip-audit fails on low-severity advisories that have no fix] → Use the ignore file, which requires a reason and a review date. `docs/ci.md` describes the process.
- [The OpenAPI export depends on settings, such as a required `JWT_SECRET`] → The script passes explicit dummy values. A unit test runs the export in `--check` mode, so a missing setting shows up locally too.
- [paths-filter misclassifies a file, for example a root `docker-compose.yml` change] → The `ci` filter includes the workflows, `docker-compose.yml`, `.env.example`, and the pre-commit and gitleaks configs, all of which trigger every job.
- [Running the smoke test with `docker compose` on GitHub runners adds about 2–4 minutes] → It runs in parallel with the other jobs and uses BuildKit's GHA cache.
- [Pinned SHAs are harder to read] → Version comments, and Dependabot keeps them current.
- [Pre-commit mypy and tsc are slow on large commits] → Accepted for parity. Developers can skip a single run with `SKIP=mypy`, and CI still enforces it.

## Migration Plan

1. Land the workflow, configs, refactor, snapshot, and docs on `feature/us-00.4-build-validation-pipeline`. Iterate until CI is green; the `CI result` check now exists.
2. Merge the pull request. There's no ruleset yet, so the merge works as today.
3. Apply `.github/rulesets/master.json` with `gh api`, and enable secret scanning and push protection. Confirm a test direct push to `master` is rejected.
4. Update GitHub issue #5 to record the two agreed changes (oxlint, 0 approvals).

**Rollback:** delete or disable the ruleset (`gh api -X DELETE repos/{owner}/{repo}/rulesets/{id}`) and revert the workflow commit. Nothing at runtime depends on this change.
