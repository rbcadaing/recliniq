## Purpose

Protects RecliniQ's build and dependencies from supply-chain and secret-leak risks. Third-party workflow code is pinned and runs with least privilege, dependencies stay current and audited, and secrets and serious code-level vulnerabilities are caught before they reach `master`.

## ADDED Requirements

### Requirement: Pinned third-party actions
Every third-party action referenced by a repository workflow SHALL be pinned to a full commit SHA, with the release version recorded in a comment next to it.

#### Scenario: Workflow references an action
- **WHEN** a workflow file uses an action from another repository
- **THEN** the reference is a 40-character commit SHA, not a tag or branch

### Requirement: Least-privilege workflow permissions
Every workflow SHALL declare its token permissions explicitly. The default SHALL be read-only repository contents, and a job SHALL be granted more only where it needs it, such as writing security events for code scanning.

#### Scenario: Workflow without explicit permissions
- **WHEN** a workflow file is added or changed
- **THEN** it declares a `permissions` block, and no job has write access it doesn't use

### Requirement: Automated dependency updates
The repository SHALL be configured to open update pull requests every week for GitHub Actions, backend Python dependencies, frontend npm dependencies, and container base images.

#### Scenario: New dependency release
- **WHEN** a newer version of a tracked dependency is published
- **THEN** an update pull request is opened within a week and goes through the same CI gate

### Requirement: Dependency vulnerability audit
CI SHALL audit the locked backend dependencies and the locked frontend dependencies for known vulnerabilities. The frontend audit SHALL fail on high- or critical-severity findings. The backend audit SHALL fail on any known vulnerability not listed in a committed ignore list, where each entry records a reason and a review date.

#### Scenario: Vulnerable frontend package
- **WHEN** a locked frontend dependency has a known high- or critical-severity vulnerability
- **THEN** CI fails and names the package and the advisory

#### Scenario: Vulnerable backend package
- **WHEN** a locked backend dependency has a known vulnerability that isn't in the ignore list
- **THEN** CI fails and names the package and the advisory

### Requirement: Secret scanning
CI SHALL scan the repository's full git history for committed secrets and fail when it finds any, other than documented allow-listed test fixtures. Local pre-commit hooks SHALL run the same scan on staged changes.

#### Scenario: Secret committed
- **WHEN** a commit adds a credential such as a private key or an API token
- **THEN** CI fails and identifies the file and commit

#### Scenario: Known test fixture
- **WHEN** a test file contains a deliberately fake credential listed in the scanner's allowlist
- **THEN** the scan does not fail

### Requirement: Static security analysis
The backend and frontend source SHALL be analysed for security vulnerabilities on every pull request to `master`, on every push to `master`, and on a weekly schedule. A new high- or critical-severity finding SHALL block merging. The backend lint step SHALL keep its security rule set enabled.

#### Scenario: Injection vulnerability introduced
- **WHEN** a pull request introduces code that analysis rates as a high- or critical-severity vulnerability
- **THEN** the finding is reported on the pull request, and the pull request cannot be merged
