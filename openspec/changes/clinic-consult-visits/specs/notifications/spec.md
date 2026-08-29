## Purpose

Notifies the people who need to know when a consultation booking or visit record changes, using in-app alerts and email for this release.

## ADDED Requirements

### Requirement: Booking lifecycle alerts
The system SHALL create an in-app alert and queue an email when a consultation is booked, when booking details that affect the visit time or practitioner change, and when a booking is cancelled. Recipients MUST include the owning patient and, for staff-created or staff-cancelled events, the acting staff member’s clinic as configured (patient always; assigned practitioner always for that practitioner’s bookings).

#### Scenario: Patient self-books
- **WHEN** a patient successfully books a consultation
- **THEN** the patient and the assigned practitioner receive an in-app alert and a queued email describing the booking

#### Scenario: Staff books on behalf
- **WHEN** an assistant books a consultation for a patient
- **THEN** the patient and the assigned practitioner receive an in-app alert and a queued email

#### Scenario: Booking cancelled
- **WHEN** a booking is cancelled
- **THEN** the owning patient and the assigned practitioner receive an in-app alert and a queued email that names the cancelling actor’s role (patient, doctor, or assistant)

### Requirement: Visit record and document alerts
The system SHALL create an in-app alert and queue an email when a visit record is updated or a supporting document is added. Recipients MUST include the owning patient and the assigned practitioner.

#### Scenario: Document uploaded
- **WHEN** a supporting document is attached to a visit
- **THEN** the owning patient and the assigned practitioner receive an in-app alert and a queued email

#### Scenario: Record updated
- **WHEN** a visit record is saved with changes
- **THEN** the owning patient and the assigned practitioner receive an in-app alert and a queued email

### Requirement: In-app alert inbox
The system SHALL allow an authenticated patient, doctor, or assistant to list unread and recent in-app alerts for their account in the tenant and to mark an alert as read. The system MUST NOT show another person’s alerts.

#### Scenario: Patient opens alerts
- **WHEN** a patient opens their alert list
- **THEN** they see alerts addressed to their account only

#### Scenario: Mark read
- **WHEN** the recipient marks an alert as read
- **THEN** the alert is no longer shown as unread
