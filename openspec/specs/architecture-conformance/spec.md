# architecture-conformance Specification

## Purpose

Enforces RecliniQ's clean-architecture layering and soft-delete-only data policy automatically, so violations fail the build instead of depending on code review.

## Requirements

### Requirement: Layer dependency rules
The backend SHALL have automated checks that fail the build when code breaks these layer boundaries:
- The domain layer imports nothing from the application, infrastructure, or presentation layers, and nothing from the web framework or the ORM.
- The application layer imports nothing from the infrastructure or presentation layers.
- Infrastructure is imported only by the composition roots, namely the dependency-wiring module and the app factory.
- API route modules don't import the ORM or database session APIs directly.

#### Scenario: Domain imports infrastructure
- **WHEN** a module in the domain layer imports from the infrastructure layer
- **THEN** the architecture check fails and names the import

#### Scenario: Router builds a repository directly
- **WHEN** an API route or security module imports an infrastructure repository, instead of receiving it through dependency wiring
- **THEN** the architecture check fails and names the import

#### Scenario: Conforming code
- **WHEN** all modules follow the layer rules
- **THEN** the architecture check passes

### Requirement: Static hard-delete ban
The backend SHALL have an automated check that scans application code and migrations, and fails the build on any hard delete: an ORM bulk delete statement, a session-level entity delete, or a raw SQL `DELETE` statement. The only exception SHALL be a line carrying an explicit marker that states the reason, as used for tables exempt from soft delete.

#### Scenario: Hard delete introduced
- **WHEN** application code adds an ORM or raw SQL delete without an exemption marker
- **THEN** the check fails and reports the file and line

#### Scenario: Exempt table cleanup
- **WHEN** a delete on a soft-delete-exempt table carries the exemption marker with a reason
- **THEN** the check passes

#### Scenario: Soft delete used
- **WHEN** code removes a record using the soft-delete repository operation
- **THEN** the check passes
