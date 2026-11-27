# local-dev-environment Specification

## Purpose

Lets any developer run the full RecliniQ stack locally with one command and configure it through documented environment variables, without committing secrets.

## Requirements

### Requirement: One-command local stack
The repository SHALL provide a single command that starts the database, backend, frontend, and a local mail catcher together for local development, applying database migrations automatically before the backend serves requests. The backend SHALL send email through the mail catcher. Developers SHALL be able to read sent emails in its web inbox, and no email SHALL leave the machine.

#### Scenario: Start the stack from a clean checkout
- **WHEN** a developer with Docker installed copies the example environment file and runs the documented start command
- **THEN** the database, backend, frontend, and mail catcher start, migrations are applied, the backend health endpoint returns 200, and the frontend is reachable in a browser

#### Scenario: Backend waits for database
- **WHEN** the stack starts and the database is not yet accepting connections
- **THEN** the backend does not start serving until the database is healthy

#### Scenario: Read sent emails locally
- **WHEN** the backend sends an email in the local stack, such as a verification email after sign-up
- **THEN** the email appears in the mail catcher's web inbox at the documented local URL and is not delivered externally

### Requirement: Live reload in development
The local stack SHALL reload backend and frontend automatically when source files change, without rebuilding containers.

#### Scenario: Edit backend source
- **WHEN** a developer saves a change to backend source code while the stack runs
- **THEN** the backend restarts and serves the updated code

### Requirement: Persistent local data
The local database SHALL keep its data across stack restarts until a developer explicitly removes it.

#### Scenario: Restart stack
- **WHEN** a developer stops and restarts the stack
- **THEN** previously stored data is still present

### Requirement: Documented configuration
Every configuration value used by the backend, frontend, and local stack SHALL be listed with a description and a safe placeholder or default in a committed example environment file.

#### Scenario: New config value added
- **WHEN** a configuration value is read by the application
- **THEN** it appears in the corresponding example environment file with a description

### Requirement: No committed secrets
The repository SHALL exclude real environment files from version control, and example files SHALL contain only placeholders or local-development defaults, never production credentials.

#### Scenario: Developer creates a local env file
- **WHEN** a developer creates a `.env` file with real values
- **THEN** version control ignores it
