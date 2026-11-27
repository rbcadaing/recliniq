# backend-foundation Specification

## Purpose

Provides the backend service skeleton that all RecliniQ features build on: configuration, database schema migrations, a versioned HTTP API with consistent errors, health checks, and request traceability.

## Requirements

### Requirement: Versioned API namespace
The backend SHALL expose all application endpoints under the `/api/v1` path prefix and SHALL publish a machine-readable OpenAPI description of those endpoints.

#### Scenario: OpenAPI description available
- **WHEN** a client requests the OpenAPI document
- **THEN** the backend returns a valid OpenAPI 3 JSON document listing the `/api/v1` endpoints

#### Scenario: Unknown route
- **WHEN** a client requests a path under `/api/v1` that does not exist
- **THEN** the backend responds with HTTP 404 using the standard error envelope

### Requirement: Liveness health check
The backend SHALL provide a liveness endpoint at `GET /api/v1/health` that reports the process is running without depending on external services.

#### Scenario: Service is running
- **WHEN** a client calls `GET /api/v1/health`
- **THEN** the backend responds with HTTP 200 and a JSON body containing `status: "ok"`, the application name, and its version

### Requirement: Readiness health check
The backend SHALL provide a readiness endpoint at `GET /api/v1/health/ready` that verifies database connectivity.

#### Scenario: Database reachable
- **WHEN** a client calls `GET /api/v1/health/ready` and the database accepts connections
- **THEN** the backend responds with HTTP 200 and a JSON body indicating the database check passed

#### Scenario: Database unreachable
- **WHEN** a client calls `GET /api/v1/health/ready` and the database cannot be reached
- **THEN** the backend responds with HTTP 503 using the standard error envelope and does not expose connection strings or credentials

### Requirement: Standard error envelope
The backend SHALL return every error response (validation, not found, application, and unexpected errors) as JSON in a single consistent shape containing an error `code`, a human-readable `message`, optional `details`, and the `request_id`.

#### Scenario: Request validation failure
- **WHEN** a client sends a request whose body or parameters fail schema validation
- **THEN** the backend responds with HTTP 422 and the standard error envelope whose `details` identify the invalid fields

#### Scenario: Unexpected server error
- **WHEN** an unhandled exception occurs while processing a request
- **THEN** the backend responds with HTTP 500 and the standard error envelope with a generic message, and no stack trace or internal detail is included in the response

### Requirement: Request correlation
The backend SHALL assign every request a request ID, accept a client-supplied `X-Request-ID` header when present, return the ID in the `X-Request-ID` response header, and include it in every log entry produced while handling that request.

#### Scenario: Client supplies request ID
- **WHEN** a client sends a request with header `X-Request-ID: abc-123`
- **THEN** the response carries `X-Request-ID: abc-123`

#### Scenario: No request ID supplied
- **WHEN** a client sends a request without an `X-Request-ID` header
- **THEN** the response carries a newly generated unique `X-Request-ID`

### Requirement: Structured logging
The backend SHALL emit logs as structured records (JSON outside local development) including timestamp, level, message, and request ID, and SHALL NOT log secrets such as passwords, tokens, or database credentials.

#### Scenario: Request is logged
- **WHEN** the backend handles any request
- **THEN** a log record is written with method, path, status code, duration, and request ID

### Requirement: Environment-based configuration
The backend SHALL read all configuration (database URL, environment name, CORS origins, log level, secrets) from environment variables, SHALL validate it at startup, and SHALL refuse to start when required values are missing or invalid.

#### Scenario: Missing required setting
- **WHEN** the backend starts without a required setting such as the database URL
- **THEN** startup fails with an error naming the missing setting, without printing secret values

### Requirement: Cross-origin access control
The backend SHALL allow browser cross-origin requests only from origins listed in configuration.

#### Scenario: Allowed origin
- **WHEN** a browser at a configured origin makes a cross-origin request
- **THEN** the response includes CORS headers permitting that origin

#### Scenario: Disallowed origin
- **WHEN** a browser at an origin not in the configured list makes a cross-origin request
- **THEN** the response does not include CORS headers permitting that origin

### Requirement: Versioned database migrations
The backend SHALL manage the PostgreSQL schema exclusively through versioned migration scripts that can be applied to upgrade an empty database to the latest schema and reverted step by step.

#### Scenario: Fresh database
- **WHEN** migrations are applied to an empty database
- **THEN** the database schema reaches the latest revision without errors

#### Scenario: Schema drift check
- **WHEN** the automated test suite runs
- **THEN** it fails if the ORM models define schema changes that no migration captures
