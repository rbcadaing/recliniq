## Purpose

Provides the web frontend skeleton for RecliniQ: client-side routing, a single configurable way to call the backend API, and consistent handling of API errors.

## ADDED Requirements

### Requirement: Client-side routing
The frontend SHALL be a single-page application with client-side routing, including a home route and a not-found route for unknown paths.

#### Scenario: Navigate to home
- **WHEN** a user opens the application root URL
- **THEN** the home page renders

#### Scenario: Unknown path
- **WHEN** a user opens a URL that matches no route
- **THEN** a "page not found" view renders with a link back to the home page

### Requirement: Configurable API client
The frontend SHALL send all backend requests through a single API client whose base URL comes from build-time environment configuration, and SHALL NOT hard-code backend addresses elsewhere.

#### Scenario: Base URL from environment
- **WHEN** the frontend is built or run with an API base URL configured
- **THEN** every API request targets that base URL

### Requirement: Normalized API errors
The API client SHALL convert non-success responses and network failures into a single typed error carrying the HTTP status (when available), the backend error `code` and `message` from the standard error envelope, and the request ID.

#### Scenario: Backend returns an error envelope
- **WHEN** the backend responds with a non-2xx status and the standard error envelope
- **THEN** the API client raises a typed error exposing the status, code, message, and request ID

#### Scenario: Network failure
- **WHEN** the backend cannot be reached
- **THEN** the API client raises a typed error identifying a network failure instead of an unhandled exception

### Requirement: Backend status indicator
The home page SHALL display whether the backend is reachable, based on the backend liveness health check.

#### Scenario: Backend healthy
- **WHEN** the home page loads and the health check succeeds
- **THEN** the page shows the backend as online with its reported version

#### Scenario: Backend unavailable
- **WHEN** the home page loads and the health check fails
- **THEN** the page shows the backend as offline without crashing the application
