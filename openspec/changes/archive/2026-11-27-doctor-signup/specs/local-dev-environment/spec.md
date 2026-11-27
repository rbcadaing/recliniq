## MODIFIED Requirements

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
