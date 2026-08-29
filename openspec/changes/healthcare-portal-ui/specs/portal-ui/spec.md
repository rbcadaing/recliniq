## Purpose

Gives visitors, patients, doctors, and clinic assistants one RecLinq React portal: a public landing with Get Care actions, shared header and footer branding, and role-aware in-app chrome after sign-in.

## ADDED Requirements

### Requirement: Public landing without authentication
The system SHALL present a public RecLinq home at `/` that a visitor can view without signing in. The landing MUST include RecLinq brand (logo mark and wordmark), a hero with a primary call to get care, a Get Care card set, a short why-RecLinq section, and a footer of in-app quick links. The landing MUST NOT require a desktop-only control on a phone-width viewport. The landing MUST NOT display another clinic’s tenant data or another product’s trademarks.

#### Scenario: Visitor opens the site
- **WHEN** an unauthenticated visitor opens `/`
- **THEN** the React client shows the RecLinq landing (hero, Get Care cards, footer) without prompting for credentials first

#### Scenario: Phone-width landing
- **WHEN** a visitor opens `/` on a phone-width viewport
- **THEN** they can read the hero, activate Get Care cards, and use header Sign in / Register without a desktop-only control

### Requirement: Header actions for visitors and signed-in users
The system SHALL show a persistent RecLinq header on public and authenticated React screens. For a visitor the header MUST offer Register and Sign in. For a signed-in patient, doctor, or assistant the header MUST show display name (or role label) and Log out, plus a way to open the in-app home. Header brand MUST navigate to `/`.

#### Scenario: Visitor uses header auth
- **WHEN** a visitor chooses Sign in or Register from the header
- **THEN** the React client opens the corresponding auth screen

#### Scenario: Signed-in patient uses header
- **WHEN** a patient session is active
- **THEN** the header shows that they are signed in and Log out, and MUST NOT offer public Register as the primary action

### Requirement: Get Care cards deep-link to RecLinq actions
The system SHALL offer Get Care cards that only start RecLinq capabilities already in the product: book a consultation, visit history (queue and past visits), alerts, and (for staff after sign-in) plot schedule. Choosing a card MUST NOT create a booking, cancel a booking, or write visit records. If the action requires a session, the system MUST send the visitor to Sign in and, after success, continue to that action. Conflict-free booking remains the existing booking flow: the portal MUST NOT present a second path that can confirm a slot without that flow.

#### Scenario: Visitor chooses Book
- **WHEN** an unauthenticated visitor activates the Book Get Care card
- **THEN** the system requires Sign in (or Register then Sign in) before the patient booking screen, and MUST NOT confirm a consultation from the landing itself

#### Scenario: Patient chooses History
- **WHEN** a signed-in patient activates History
- **THEN** the React client opens that patient’s consultation history only

#### Scenario: Assistant chooses Schedule
- **WHEN** a signed-in assistant or doctor activates Schedule
- **THEN** the React client opens staff schedule for their tenant

#### Scenario: Patient cannot use staff Get Care
- **WHEN** a patient session follows a staff-only Get Care target such as plot schedule
- **THEN** the system refuses that action and does not show another tenant’s schedule

### Requirement: Authenticated in-app home
The system SHALL provide an authenticated RecLinq home distinct from public `/`, reachable after Sign in. That home MUST summarize role-appropriate next actions (patient: book, history, alerts; doctor or assistant: schedule, book for patient, history, alerts) using the same card language as Get Care. The system MUST still isolate data to the session tenant.

#### Scenario: Patient after sign-in
- **WHEN** a patient completes Sign in
- **THEN** the React client shows the in-app home with patient actions and MUST NOT show staff-only schedule or book-for-patient as available actions

#### Scenario: Doctor after sign-in
- **WHEN** a doctor completes Sign in
- **THEN** the React client shows the in-app home with staff actions including schedule and book for patient

### Requirement: Auth screens match portal chrome
The system SHALL present Sign in and patient Register on RecLinq-branded React screens (logo, wordmark, primary action) usable on a phone-width viewport. Patient Register MUST remain patient-only. Staff MUST sign in with existing staff credentials and MUST NOT self-register as doctor or assistant from these screens.

#### Scenario: New patient registers from landing
- **WHEN** a visitor completes Register with a valid email, password, and display name for the clinic
- **THEN** they can Sign in as a patient and reach the in-app home

#### Scenario: Staff sign in from landing
- **WHEN** a doctor or assistant submits valid staff credentials on Sign in
- **THEN** the system starts a session with that role and shows the in-app home
