## Purpose

Identifies people in a clinic tenant, lets patients register and sign in, lets doctors and assistants sign in with staff credentials, and restricts each React surface to the caller’s role.

## ADDED Requirements

### Requirement: Clinic tenant isolation
The system SHALL associate every authenticated session with exactly one clinic tenant. The system MUST NOT return users, schedules, bookings, or records that belong to a different tenant.

#### Scenario: Same-tenant access
- **WHEN** an authenticated patient requests their profile
- **THEN** the system returns only data for the tenant on that session

#### Scenario: Cross-tenant denied
- **WHEN** a caller presents an identifier that belongs to another tenant
- **THEN** the system rejects the request without leaking whether the identifier exists

### Requirement: Patient registration and login
The system SHALL allow a patient to register with email and password for a clinic tenant and SHALL allow that patient to log in. The system MUST reject registration with an email already used in that tenant. The system MUST NOT allow patients to self-register as doctor or assistant.

#### Scenario: New patient registers
- **WHEN** a visitor submits a valid email, password, and display name for the clinic
- **THEN** the system creates a patient account in that tenant and the visitor can log in

#### Scenario: Duplicate email
- **WHEN** a visitor registers with an email already used by a patient in that tenant
- **THEN** the system refuses the registration and does not create a second account

#### Scenario: Patient logs in
- **WHEN** a registered patient submits correct credentials
- **THEN** the system starts an authenticated session with the patient role

### Requirement: Staff login
The system SHALL allow a doctor or assistant who already has a staff account in the tenant to log in. The system MUST NOT offer public self-registration for doctor or assistant roles.

#### Scenario: Doctor logs in
- **WHEN** a doctor submits valid staff credentials
- **THEN** the system starts an authenticated session with the doctor role

#### Scenario: Assistant logs in
- **WHEN** an assistant submits valid staff credentials
- **THEN** the system starts an authenticated session with the assistant role

#### Scenario: Patient cannot use staff-only actions
- **WHEN** a patient session calls an action reserved for doctor or assistant
- **THEN** the system refuses the action

### Requirement: Mobile viewport access
The system SHALL present patient and staff React screens so that register, login, booking, history, records, and cancel can be completed on a phone-width viewport without requiring a desktop-only control.

#### Scenario: Patient books on a phone-width viewport
- **WHEN** a logged-in patient opens booking on a phone-width viewport
- **THEN** they can select availability and confirm a consultation without a desktop-only control
