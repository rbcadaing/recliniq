## ADDED Requirements

### Requirement: Local pre-commit checks
The repository SHALL provide pre-commit hooks that run the same checks CI runs: backend lint, format, and strict type checks; frontend lint, format, and type checks; and secret scanning. The hooks SHALL use the same tool versions and configuration as CI, so a commit that passes locally doesn't fail CI on these checks.

#### Scenario: Developer commits a lint violation
- **WHEN** a developer with the hooks installed commits code that breaks a lint or format rule
- **THEN** the commit is blocked locally, with the same message CI would report

#### Scenario: Developer commits a secret
- **WHEN** a developer with the hooks installed stages a file containing a credential
- **THEN** the commit is blocked locally

### Requirement: Documented pipeline
The repository SHALL include contributor documentation that lists every CI check, explains how to run it locally, and explains how to fix its common failures. That includes coverage thresholds, contract snapshot regeneration, architecture contracts, audit ignore entries, and the hard-delete exemption marker.

#### Scenario: Contributor sees a failing check
- **WHEN** a contributor's pull request fails a CI check
- **THEN** the documentation tells them the local command that reproduces it and how to fix it
