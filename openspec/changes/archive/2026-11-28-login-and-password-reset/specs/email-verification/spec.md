## MODIFIED Requirements

### Requirement: Verify-email page
The frontend SHALL provide a verify-email page that reads the token from the link, confirms it with the backend, and shows the outcome:
- verified, with a link to sign in;
- link expired, offering to send a new email;
- link invalid or already used, offering to send a new email.

#### Scenario: Successful verification
- **WHEN** a user opens a valid verification link
- **THEN** the page confirms the token, tells the user their email is verified, and offers a link to sign in

#### Scenario: Expired link
- **WHEN** a user opens an expired verification link
- **THEN** the page says the link has expired and lets the user request a new verification email
