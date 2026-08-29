## Purpose

Gives each patient a consultation visit history in their clinic tenant and lets doctor, patient, and assistant view and update visit records, including supporting documents such as laboratory results and prescriptions.

## ADDED Requirements

### Requirement: Patient consultation history
The system SHALL allow a logged-in patient to list their own consultation visits in that tenant (upcoming, completed, and cancelled). The list MUST NOT include other patients’ visits.

#### Scenario: Patient lists own visits
- **WHEN** a patient opens consultation history
- **THEN** the system shows that patient’s visits only, including status

#### Scenario: Other patient’s visit hidden
- **WHEN** a patient requests a visit identifier that belongs to another patient
- **THEN** the system refuses the request

### Requirement: Staff can open a patient’s visits
The system SHALL allow a doctor or assistant in the tenant to list and open consultation visits for a chosen patient in that tenant.

#### Scenario: Assistant opens a patient’s history
- **WHEN** an assistant selects a patient in the clinic
- **THEN** the system shows that patient’s consultation visits for the tenant

### Requirement: View and update visit records
The system SHALL store a visit record per consultation (notes and structured fields as defined by the clinic’s consultation form). A doctor, the owning patient, and an assistant SHALL be able to view the record. A doctor, the owning patient, and an assistant SHALL be able to update allowed fields. The system MUST record who last updated the record and when.

#### Scenario: Doctor updates notes
- **WHEN** a doctor saves an update to a visit record
- **THEN** the new content is stored and the last-updated actor is that doctor

#### Scenario: Patient updates their visit record
- **WHEN** the owning patient saves an allowed update (for example a symptom note)
- **THEN** the record is updated and the last-updated actor is that patient

### Requirement: Supporting documents
The system SHALL allow a doctor, the owning patient, and an assistant to upload supporting files on a visit (laboratory results, prescriptions, and similar) and to view files already attached to that visit. The system MUST reject files that fail type or size policy. Files MUST NOT be visible to patients other than the owner.

#### Scenario: Patient uploads a lab result
- **WHEN** the owning patient uploads an allowed file to their visit
- **THEN** the file is attached to that visit and authorised roles can view it

#### Scenario: Doctor uploads a prescription scan
- **WHEN** a doctor uploads an allowed file to a visit
- **THEN** the file is attached and the owning patient can view it

#### Scenario: Disallowed file rejected
- **WHEN** a caller uploads a file that is not an allowed type or exceeds size limits
- **THEN** the system refuses the upload and does not attach a file
