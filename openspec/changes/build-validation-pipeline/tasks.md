## 1. Architecture refactor and contracts

- [x] 1.1 Add a user-repository provider (`UserRepositoryDep`) to `presentation/dependencies.py`. Switch `presentation/security.py` and `presentation/api/v1/me.py` to use it, and remove their imports of `app.infrastructure`. If `me.py` no longer needs `SessionDep`, remove that too. Verify that `uv run mypy`, `uv run pytest`, and the integration suite (`test_session_api.py`, the `/me` tests) all pass unchanged.
- [x] 1.2 Add `import-linter` to the backend dev dependencies and create `backend/.importlinter` with the five contracts from design D6. Verify that `uv run lint-imports` passes. Then temporarily add `from app.infrastructure.clock import SystemClock` to a domain module, confirm the command fails and names the import, and revert.
- [x] 1.3 Add `tests/unit/test_no_hard_deletes.py` (design D7). It scans `app/` and `alembic/versions/` for SQLAlchemy `delete()`, session `.delete(`, and raw `DELETE FROM` strings, and requires a `# hard-delete-ok: <reason>` marker for exceptions. Stale markers fail too. Add the marker to the `rate_limit_counters` cleanup in `infrastructure/accounts/rate_limiter.py`. Verify with unit cases on fixture source strings (unmarked ORM delete fails, raw SQL fails, marked delete passes, a marker with no reason fails, a stale marker fails), and confirm the scan passes on the real tree.

## 2. API contract snapshot

- [x] 2.1 Add `backend/scripts/export_openapi.py`. It builds the app with dummy settings and writes sorted, indented JSON to `frontend/src/api/generated/openapi.json`; `--check` makes it exit 1 with a regeneration hint when they differ. Generate and commit the snapshot. Verify with a unit test that runs the check mode and passes, and confirm that editing a response model makes `--check` fail.
- [x] 2.2 Add the dependency-free generator `scripts/generate-api-types.mjs` with vitest tests (replacing `openapi-typescript`; see design D8), and an `api:generate` script that writes `src/api/generated/schema.ts`. Exclude `src/api/generated/` from oxlint, Prettier, and coverage. Verify that `npm run api:generate && git diff --exit-code src/api/generated` is clean right after generation, and that `npm run lint` passes.
- [x] 2.3 Switch `src/api/auth.ts`, `health.ts`, and `specializations.ts` to type aliases over `components['schemas'][…]`, keeping their exported type names. Verify that `npm run typecheck` and `npm test -- --run` pass. Then temporarily rename a field in `openapi.json`, regenerate, confirm `typecheck` fails, and revert.

## 3. Coverage and reports

- [x] 3.1 Add `pytest-cov` to the backend dev dependencies. Run `uv run pytest --cov=app --cov-report=term-missing` with `TEST_DATABASE_URL` set and record the baseline. If it's below 80%, add tests for the uncovered paths until it reaches 80%. Verify that `--cov-fail-under=80` passes locally against the test database.
- [x] 3.2 Add `@vitest/coverage-v8`, a `test:coverage` script, and coverage settings in `vite.config.ts` (v8 provider, 70% line threshold, text-summary, cobertura, and HTML reporters, a JUnit reporter, and exclusions for tests, `src/test/`, and `src/api/generated/`). Record the baseline, and add tests if it's below 70%. Verify that `npm run test:coverage` passes and writes `coverage/cobertura-coverage.xml`.

## 4. Security tooling

- [x] 4.1 Add a root `.gitleaks.toml` that extends the default rules, with an allowlist for the test-fixture paths and the local-only Compose defaults. Verify that `gitleaks detect --source . --log-opts="--all"` reports no leaks on the full history. Also verify that a scratch file with a fake AWS key is detected, then delete the file.
- [x] 4.2 Add `backend/.pip-audit-ignore` (empty, with a header comment explaining the `ID  # reason, review-by YYYY-MM-DD` format), plus the audit commands from design D5. Verify that `uv export --frozen --no-hashes --no-emit-project > /tmp/req.txt && uvx pip-audit -r /tmp/req.txt --strict` passes, and that `npm audit --audit-level=high` passes. If either finds something, upgrade the dependency, or add a justified ignore entry.

## 5. Workflows

- [x] 5.1 Rewrite `.github/workflows/ci.yml` according to design D1, D2, and D10:
  - triggers: `pull_request` and `push` on `master`;
  - jobs: `changes` (paths-filter with `backend`, `frontend`, and `ci` filters), `backend`, `frontend`, `security`, `smoke`, and the always-running `ci-result` aggregate;
  - every action pinned to a SHA with a version comment;
  - explicit minimal `permissions`;
  - JUnit and coverage artifacts uploaded with `if: always()`, and totals written to `$GITHUB_STEP_SUMMARY`.

  Verify that `actionlint` reports nothing, and that `grep -E "uses: [^@]+@(v|main|master)" .github/workflows/*.yml` finds no tag- or branch-pinned actions.
- [x] 5.2 Add `.github/workflows/codeql.yml` (python and javascript-typescript, `build-mode: none`, pull requests and pushes to `master`, a weekly cron, `security-events: write` only on the analyze job, and SHA-pinned actions). Verify with `actionlint`, and on the pull request's first run, check that both CodeQL analyses complete and upload results.
- [ ] 5.3 Add `.github/dependabot.yml` covering `github-actions` (/), `uv` (/backend), `npm` (/frontend), and `docker` (/backend, /frontend), weekly, with grouped minor and patch updates. Verify that the file parses against the Dependabot schema, and that after merging the repo's Insights → Dependency graph → Dependabot tab lists all five ecosystems.

## 6. Local hooks and docs

- [x] 6.1 Add a root `.pre-commit-config.yaml` with local hooks (design D9): backend ruff check, ruff format --check, mypy, and lint-imports; frontend lint and typecheck; gitleaks on staged changes; and opt-in tests on `pre-push`. Verify that `uvx pre-commit run --all-files` passes, and that staging a file with a lint violation makes `git commit` fail with the ruff message.
- [x] 6.2 Add `.github/rulesets/master.json` (design D4: pull request with 0 approvals, required `CI result` with strict up-to-date, code scanning at `high_or_higher`, non-fast-forward, and deletion; no bypass actors). Verify that the JSON is valid (`python -m json.tool`), and that its fields match the GitHub rulesets REST schema (`gh api` dry review of the field names against the docs).
- [x] 6.3 Write `docs/ci.md`. It covers:
  - every check, with the local command that reproduces it and the common fixes;
  - the coverage baselines and thresholds;
  - snapshot regeneration;
  - import-linter contracts and the `# hard-delete-ok:` marker;
  - pip-audit ignore entries and the gitleaks allowlist;
  - installing pre-commit;
  - applying, updating, and temporarily disabling the ruleset with `gh api`.

  Link it from `README.md`, and update the Commands and conventions in `CLAUDE.md` (pre-commit, lint-imports, `api:generate`, coverage commands). Verify that every check in `ci.yml` has a section in `docs/ci.md`.

## 7. Rollout and verification

- [x] 7.1 Push the branch and open a pull request to `master`. Verify that every job in `ci.yml` and `codeql.yml` passes, that `CI result` reports success, and that the job summaries show test counts and coverage.
- [ ] 7.2 Check path filtering with a pull request whose whole diff touches neither app, such as the OpenSpec archive pull request for this change (only `openspec/` files). On pull requests, the filter compares the entire pull request with `master`, not the latest commit. A docs-only commit pushed to this pull request still ran every job, which is correct, because the whole pull request is what merges. Confirm that the backend, frontend, and smoke jobs are skipped while `CI result` still reports success.
- [ ] 7.3 After merging, ask for confirmation, then apply the ruleset (`gh api repos/rbcadaing/recliniq/rulesets --method POST --input .github/rulesets/master.json`) and enable secret scanning and push protection. Verify that `gh api repos/rbcadaing/recliniq/rulesets` lists it as active, and that a direct `git push origin master` of a no-op commit is rejected.
- [ ] 7.4 Update GitHub issue #5 to record the agreed deviations (oxlint instead of ESLint; 0 required approvals until a second maintainer joins), and confirm that the issue text matches what was shipped.
