## Purpose

Lets patients and clinic staff reserve a consultation against remaining practitioner availability, lets staff book on behalf of a patient, and lets authorised people cancel with a durable record of who cancelled.

## ADDED Requirements

### Requirement: Patient self-booking
The system SHALL allow a logged-in patient to book a consultation with a practitioner in their tenant for a remaining available unit. On success the booking MUST belong to that patient and MUST consume that unit so it is no longer available.

#### Scenario: Patient books an open unit
- **WHEN** a patient confirms a remaining available consultation unit
- **THEN** the system creates a booked consultation for that patient and the unit is no longer offered

#### Scenario: Concurrent double-book refused
- **WHEN** two callers try to book the same remaining unit at the same time
- **THEN** exactly one booking succeeds and the other is refused as no longer available

### Requirement: Staff booking on behalf of a patient
The system SHALL allow a doctor or assistant to create a consultation booking for a patient in the same tenant without the patient using self-service. The booking MUST record that staff created it and MUST consume availability the same way as a patient self-booking.

#### Scenario: Assistant books for a patient
- **WHEN** an assistant selects a patient and a remaining available unit and confirms
- **THEN** the system creates a booked consultation for that patient and the unit is no longer offered

#### Scenario: Patient cannot book on behalf of another patient
- **WHEN** a patient attempts to create a booking for a different patient
- **THEN** the system refuses the booking

### Requirement: Cancel booking with actor log
The system SHALL allow the patient who owns the booking, a doctor, or an assistant in the same tenant to cancel a booking that is not already cancelled. The system MUST record who cancelled, their role, when, and an optional reason. A cancelled booking MUST free the consultation unit for new bookings unless the visit time has already passed (past visits remain history and MUST NOT become newly bookable in the past).

#### Scenario: Patient cancels upcoming booking
- **WHEN** the owning patient cancels an upcoming booking and optionally supplies a reason
- **THEN** the booking is cancelled, the actor and time are stored, and that future unit is available again

#### Scenario: Staff cancels
- **WHEN** a doctor or assistant cancels a patient’s upcoming booking
- **THEN** the booking is cancelled and the log shows that staff member as the cancelling actor

#### Scenario: Cancel history visible to authorised roles
- **WHEN** the owning patient, a doctor, or an assistant views the booking
- **THEN** they can see that it was cancelled, who cancelled it, when, and the reason if provided

#### Scenario: Already cancelled
- **WHEN** a caller cancels a booking that is already cancelled
- **THEN** the system refuses a second cancel and does not rewrite the original cancelling actor
