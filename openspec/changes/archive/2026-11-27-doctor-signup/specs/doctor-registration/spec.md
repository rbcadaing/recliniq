## Purpose

Lets a doctor create a RecliniQ account with their professional details. The account starts unverified and with its PRC license pending review, ready for email verification, login, and admin approval in later stories.

## ADDED Requirements

### Requirement: Specialization list
The system SHALL publicly provide the list of medical specializations a doctor can choose at sign-up, sorted by name. Each entry SHALL have a stable identifier and a display name. The list SHALL be seeded with Philippine medical specializations.

#### Scenario: Fetch specializations
- **WHEN** a client requests the specialization list without being signed in
- **THEN** the response is 200 with a non-empty list of specializations, each with an identifier and a name, sorted by name

### Requirement: Doctor sign-up
The system SHALL let a visitor register as a doctor by submitting:
- first name, optional middle name, and last name
- email
- mobile number
- password
- specialization
- PRC license number
- acceptance of the privacy notice

On success, the system SHALL create a doctor account and respond with 202 and a generic "check your email" message, and SHALL send a verification email (see email-verification). The response SHALL NOT include the account's identifier or state.

#### Scenario: Successful sign-up
- **WHEN** a visitor submits valid details with an email, mobile number, and PRC license number not used by any active account
- **THEN** the response is 202 with a "check your email" message, a doctor account exists with those details, and a verification email is sent to the submitted address

#### Scenario: Missing required field
- **WHEN** a visitor submits sign-up without one of the required fields
- **THEN** the response is 422 in the standard error envelope, naming the missing field, and no account is created

### Requirement: Initial account state
A newly registered doctor account SHALL have:
- role `doctor`
- an unverified email
- PRC license status `pending`, shown to users as "Pending verification"

This change SHALL NOT enforce what these states permit. Login and schedule publishing enforce them in their own stories.

#### Scenario: New doctor account state
- **WHEN** a doctor completes sign-up
- **THEN** the account's role is `doctor`, its email is not verified, and its license status is `pending`

### Requirement: Philippine mobile number
The mobile number SHALL be a Philippine mobile number. Spaces and dashes SHALL be ignored, and the formats `09XXXXXXXXX`, `639XXXXXXXXX`, and `+639XXXXXXXXX` SHALL be accepted. The number SHALL be stored in E.164 form (`+639XXXXXXXXX`).

#### Scenario: Local format accepted
- **WHEN** a visitor signs up with mobile number `0917 123 4567`
- **THEN** sign-up succeeds and the stored mobile number is `+639171234567`

#### Scenario: Non-PH or malformed number rejected
- **WHEN** a visitor signs up with mobile number `+14155550100` or `0917123`
- **THEN** the response is 422 naming the mobile number field

### Requirement: PRC license number
The PRC license number SHALL consist of 1 to 7 digits, ignoring surrounding whitespace. It SHALL be stored left-padded with zeros to 7 digits, so `12345` and `0012345` are the same license.

#### Scenario: Short number normalized
- **WHEN** a visitor signs up with PRC license number `12345`
- **THEN** sign-up succeeds and the stored license number is `0012345`

#### Scenario: Non-numeric or too long rejected
- **WHEN** a visitor signs up with PRC license number `AB12345` or `12345678`
- **THEN** the response is 422 naming the PRC license number field

### Requirement: Valid specialization
The submitted specialization SHALL be one from the specialization list.

#### Scenario: Unknown specialization
- **WHEN** a visitor signs up with a specialization identifier that is not in the list
- **THEN** the response is 422 naming the specialization field

### Requirement: Email address
The email SHALL be a syntactically valid address of at most 254 characters. It SHALL be compared and stored case-insensitively, in lowercase.

#### Scenario: Mixed-case email normalized
- **WHEN** a visitor signs up with `Juan.DelaCruz@Example.COM`
- **THEN** the stored email is `juan.delacruz@example.com`

#### Scenario: Invalid email rejected
- **WHEN** a visitor signs up with `not-an-email`
- **THEN** the response is 422 naming the email field

### Requirement: Password policy
The password SHALL be 12 to 128 characters long and SHALL NOT be on the system's list of common passwords or equal to the submitted email. No character-composition rules SHALL apply. The password SHALL be stored only as a salted, memory-hard hash and SHALL never appear in responses or logs.

#### Scenario: Too short
- **WHEN** a visitor signs up with an 11-character password
- **THEN** the response is 422 naming the password field

#### Scenario: Common password
- **WHEN** a visitor signs up with a password on the common-password list, such as `password1234`
- **THEN** the response is 422 naming the password field

#### Scenario: Long passphrase without symbols accepted
- **WHEN** a visitor signs up with `correct horse battery staple`
- **THEN** the password is accepted

#### Scenario: Password not stored in plain text
- **WHEN** a doctor account is created
- **THEN** the stored credential is a hash that does not contain the password, and the password does not appear in logs

### Requirement: Privacy consent
Sign-up SHALL require explicit acceptance of the privacy notice. The system SHALL store when consent was given and which version of the privacy notice was accepted.

#### Scenario: Consent not given
- **WHEN** a visitor submits sign-up without accepting the privacy notice
- **THEN** the response is 422 naming the consent field and no account is created

#### Scenario: Consent recorded
- **WHEN** a doctor completes sign-up
- **THEN** the account records the consent time and the current privacy notice version

### Requirement: Unique mobile and PRC license
Among accounts that are not deleted, the mobile number and the PRC license number SHALL each belong to at most one account. A sign-up that reuses either SHALL be rejected with 409 in the standard error envelope, naming the conflicting field. A soft-deleted account SHALL NOT block reuse.

#### Scenario: Mobile already registered
- **WHEN** a visitor signs up with a mobile number used by an active account
- **THEN** the response is 409 naming the mobile number field and no account is created

#### Scenario: PRC license already registered
- **WHEN** a visitor signs up with a PRC license number used by an active doctor account
- **THEN** the response is 409 naming the PRC license number field and no account is created

#### Scenario: Reuse after account deletion
- **WHEN** an account was soft-deleted and a visitor signs up with its email, mobile number, and PRC license number
- **THEN** sign-up succeeds

### Requirement: Sign-up does not reveal registered emails
If the submitted email already belongs to an active account, sign-up SHALL respond exactly as for a new account (202, same body) and SHALL NOT create a second account. The system SHALL email the existing address instead:
- if the existing account's email is not yet verified, a fresh verification link;
- otherwise, a notice that someone tried to register with it, with a pointer to sign in or reset the password.

#### Scenario: Email of a verified account
- **WHEN** a visitor signs up with the email of an active account whose email is verified
- **THEN** the response is identical to a successful sign-up, no new account is created, and the existing address receives an "account already exists" notice

#### Scenario: Email of an unverified account
- **WHEN** a visitor signs up with the email of an active account whose email is not yet verified
- **THEN** the response is identical to a successful sign-up, no new account is created, and the existing address receives a new verification link

### Requirement: Sign-up rate limiting
Sign-up attempts SHALL be limited per client IP address and per submitted email over a rolling time window, with configurable limits. Attempts over the limit SHALL be rejected with 429 in the standard error envelope and a `Retry-After` header, before any account is created or email sent.

#### Scenario: Too many attempts from one IP
- **WHEN** a client exceeds the per-IP sign-up limit within the window
- **THEN** further sign-up requests from that IP receive 429 with `Retry-After` until the window passes

#### Scenario: Too many attempts for one email
- **WHEN** sign-up is attempted for the same email more times than the per-email limit within the window
- **THEN** further attempts for that email receive 429, whatever the client IP

### Requirement: Doctor sign-up page
The frontend SHALL provide a public doctor sign-up page with all the sign-up fields, the specialization list, and a link to the privacy notice. It SHALL check field rules before submitting and show the backend's field errors next to the matching fields. On success it SHALL show a "check your inbox" page for the submitted email, where the user can request another verification email.

#### Scenario: Field error from backend
- **WHEN** the backend rejects a sign-up with a field error, such as a mobile number conflict
- **THEN** the page shows the error next to that field and keeps the other entered values

#### Scenario: Successful submission
- **WHEN** the backend accepts the sign-up
- **THEN** the user sees the "check your inbox" page with the submitted email and a button to resend the verification email
