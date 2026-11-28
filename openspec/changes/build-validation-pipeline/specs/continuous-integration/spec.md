## MODIFIED Requirements

### Requirement: Pull request checks
The CI pipeline SHALL run on every pull request that targets `master` and on every push to `master`. Depending on what the change touches, it SHALL run backend lint, format check, strict static type check, and tests; and frontend lint, format check, strict type check, tests, and a production build.

#### Scenario: Pull request opened
- **WHEN** a pull request targeting `master` is opened or updated
- **THEN** CI runs the backend and frontend checks that apply to the changed files

#### Scenario: Push to master
- **WHEN** a commit is pushed to `master`, for example by merging a pull request
- **THEN** CI runs all backend and frontend checks

### Requirement: Failing checks block success
The CI pipeline SHALL report failure when any lint rule, format check, type check, test, coverage threshold, migration check, contract check, security check, smoke test, or build step fails.

#### Scenario: Test failure
- **WHEN** any backend or frontend test fails
- **THEN** the CI run is reported as failed on the pull request

#### Scenario: Lint violation
- **WHEN** code violates the configured lint or formatting rules
- **THEN** the CI run is reported as failed on the pull request

## ADDED Requirements

### Requirement: Change-based job selection
The CI pipeline SHALL skip the backend checks when a change touches no backend files and no shared CI configuration, and SHALL likewise skip the frontend checks when a change touches no frontend files and no shared CI configuration. A single aggregate check SHALL always report a result. It SHALL fail when any check that ran failed or was cancelled, and pass when every check either passed or was skipped as not applicable.

#### Scenario: Frontend-only change
- **WHEN** a pull request changes only files under `frontend/`
- **THEN** the frontend checks run, the backend checks are skipped, and the aggregate check reports success once the frontend checks pass

#### Scenario: Shared CI configuration changed
- **WHEN** a pull request changes the CI workflow or other shared pipeline configuration
- **THEN** both the backend and frontend checks run

#### Scenario: A selected job fails
- **WHEN** any job that ran fails
- **THEN** the aggregate check reports failure

### Requirement: Protected default branch
The `master` branch SHALL accept changes only through pull requests, and SHALL reject direct pushes, force pushes, and deletion. A pull request SHALL be mergeable only when the aggregate CI check has passed against a branch that is up to date with `master`, and when code scanning reports no new high- or critical-severity alerts. The number of required approving reviews SHALL be configurable and set to zero while the repository has a single maintainer.

#### Scenario: Direct push rejected
- **WHEN** anyone pushes a commit directly to `master`
- **THEN** the push is rejected

#### Scenario: Failing checks block merge
- **WHEN** a pull request's aggregate CI check is failing or pending
- **THEN** the pull request cannot be merged

#### Scenario: Out-of-date branch blocks merge
- **WHEN** a pull request's branch is behind `master`
- **THEN** the pull request cannot be merged until it is updated and the checks pass again

### Requirement: Coverage thresholds
CI SHALL measure test coverage, and SHALL fail when line coverage drops below 80% for the backend application code or below 70% for the frontend source. Backend coverage SHALL include both unit and integration tests run against the real database.

#### Scenario: Backend coverage below threshold
- **WHEN** backend line coverage is below 80%
- **THEN** the backend job fails and reports the measured coverage

#### Scenario: Frontend coverage below threshold
- **WHEN** frontend line coverage is below 70%
- **THEN** the frontend job fails and reports the measured coverage

### Requirement: Published test reports
Each job that runs tests SHALL upload its test results and coverage report as downloadable build artifacts. It SHALL also publish a summary of test counts and coverage that can be reached from the pull request's checks.

#### Scenario: Reports available after a run
- **WHEN** a backend or frontend test job finishes, whether it passed or failed
- **THEN** its test results and coverage report are available as build artifacts, and a summary appears on the run

### Requirement: Migration integrity checks
CI SHALL fail when ORM models have schema changes that no migration captures, when there is more than one migration head, or when migrations cannot be applied from an empty database, fully reverted, and applied again.

#### Scenario: Model change without migration
- **WHEN** a pull request changes a model without adding a matching migration
- **THEN** CI fails and names the missing schema change

#### Scenario: Broken downgrade
- **WHEN** a migration's downgrade fails or leaves the schema unable to upgrade again
- **THEN** CI fails

### Requirement: API contract check
The repository SHALL contain a committed snapshot of the backend's OpenAPI schema, and frontend API types generated from it. CI SHALL fail when the snapshot differs from the schema the backend produces, when the generated frontend types are out of date with the snapshot, or when the frontend API client doesn't type-check against the generated types.

#### Scenario: Backend schema changed without updating the snapshot
- **WHEN** a pull request changes a backend request or response model but not the committed schema snapshot
- **THEN** CI fails, with instructions to regenerate the snapshot

#### Scenario: Frontend client out of sync with the API
- **WHEN** the schema snapshot changes in a way the frontend API client doesn't match, such as a renamed or removed field
- **THEN** the frontend type check fails

### Requirement: Compose smoke test
CI SHALL build the container images and start the full local stack from the committed Compose file with the example environment. It SHALL fail unless the backend readiness endpoint reports ready and the frontend serves its page.

#### Scenario: Stack starts healthy
- **WHEN** the smoke test starts the stack
- **THEN** the backend readiness endpoint returns success, and the frontend root URL returns the app's HTML

#### Scenario: Stack fails to start
- **WHEN** a container fails to build or never becomes healthy
- **THEN** the smoke test fails and prints the service logs
