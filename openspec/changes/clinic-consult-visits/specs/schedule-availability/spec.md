## Purpose

Lets a doctor or assistant publish when a practitioner is available for consultations so patients and staff only see remaining bookable time for that clinic tenant.

## ADDED Requirements

### Requirement: Plot recurring clinic hours
The system SHALL allow a doctor or assistant to set a practitioner’s recurring weekly clinic hours for consultations in that tenant. Hours MUST be stored in the clinic’s local timezone as declared for the tenant.

#### Scenario: Assistant publishes a practitioner week
- **WHEN** an assistant saves recurring hours for a practitioner (for example weekday mornings)
- **THEN** those hours become the base availability used to derive bookable times

#### Scenario: Patient cannot plot hours
- **WHEN** a patient attempts to change a practitioner’s clinic hours
- **THEN** the system refuses the change

### Requirement: Exceptions and blocks
The system SHALL allow a doctor or assistant to close a date or block an interval so it is not bookable (leave, procedure block, or clinic closed). Bookable times MUST exclude those exceptions.

#### Scenario: Closed date
- **WHEN** staff marks a date closed for a practitioner
- **THEN** patients and staff MUST NOT be offered consultation times on that date for that practitioner

### Requirement: Remaining availability is conflict-free
The system SHALL expose only remaining bookable consultation units (slots or remaining session capacity) after hours, exceptions, and existing non-cancelled bookings. Two successful bookings MUST NOT occupy the same remaining unit for the same practitioner.

#### Scenario: Open slot listed
- **WHEN** a patient requests availability for a practitioner on a day with unused bookable time
- **THEN** the system lists only times that are still free

#### Scenario: Taken unit not listed
- **WHEN** a consultation unit is already booked and not cancelled
- **THEN** that unit MUST NOT appear as available
