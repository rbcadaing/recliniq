# continuous-integration Specification

## Purpose

Automatically verifies code quality of the backend and frontend on every pull request so that broken or unlinted code is caught before merge.

## Requirements

### Requirement: Pull request checks
The CI pipeline SHALL run on every pull request and on pushes to the default branch, executing lint, static type checks, and automated tests for both the backend and the frontend.

#### Scenario: Pull request opened
- **WHEN** a pull request is opened or updated
- **THEN** CI runs backend lint, backend type check, backend tests, frontend lint, frontend type check, frontend tests, and a frontend production build

### Requirement: Failing checks block success
The CI pipeline SHALL report failure when any lint rule, type check, test, or build step fails.

#### Scenario: Test failure
- **WHEN** any backend or frontend test fails
- **THEN** the CI run is reported as failed on the pull request

#### Scenario: Lint violation
- **WHEN** code violates the configured lint or formatting rules
- **THEN** the CI run is reported as failed on the pull request

### Requirement: Tests run against a real database
Backend tests in CI SHALL run against a PostgreSQL database of the same major version used locally, with migrations applied.

#### Scenario: Backend test job
- **WHEN** the backend test job runs
- **THEN** a PostgreSQL service is available, migrations are applied, and readiness and migration tests execute against it
