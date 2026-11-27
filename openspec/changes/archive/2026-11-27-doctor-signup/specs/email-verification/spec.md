## Purpose

Proves that a user controls their email address before the account is considered active. Uses single-use, expiring links that can be resent, and is shared by every sign-up flow.

## ADDED Requirements

### Requirement: Verification email
When a verification is issued for an account, the system SHALL email the account's address a link to the frontend's verify-email page carrying a random, unguessable token. Only a hash of the token SHALL be stored. The link SHALL expire after a configurable period, 24 hours by default.

#### Scenario: Email sent with link
- **WHEN** a verification is issued for an account
- **THEN** the account's address receives an email containing a link to the verify-email page with a token, and the stored record contains only a hash of that token

### Requirement: Confirming a token
Confirming a valid token SHALL mark the account's email as verified, record when that happened, and use up the token. Confirmation SHALL happen through an explicit request from the verify-email page, not by merely fetching the link, so automated link scanners can't use up the token.

#### Scenario: Valid token
- **WHEN** the verify-email page confirms an unexpired, unused token
- **THEN** the response is 200, the account's email is verified with the verification time recorded, and the token can't be used again

#### Scenario: Token reused
- **WHEN** a token that was already used is confirmed again
- **THEN** the response is 400 with error code `invalid_token`

#### Scenario: Expired token
- **WHEN** a token is confirmed after its expiry time
- **THEN** the response is 400 with error code `token_expired` and the email stays unverified

#### Scenario: Unknown token
- **WHEN** a token that was never issued is confirmed
- **THEN** the response is 400 with error code `invalid_token`

### Requirement: Resending verification
A user SHALL be able to request a new verification email by submitting their email address. If the address belongs to an active account with an unverified email, the system SHALL issue a new token and invalidate all earlier unused tokens for that account. The response SHALL be the same 202 whether or not the address belongs to such an account.

#### Scenario: Resend for unverified account
- **WHEN** a user requests a new verification email for an unverified account
- **THEN** the response is 202, a new link is emailed, and earlier links for that account no longer work

#### Scenario: Resend for unknown or verified address
- **WHEN** a user requests a verification email for an address that has no active account, or whose email is already verified
- **THEN** the response is 202 with the same body, and no verification email is sent

### Requirement: Resend rate limiting
Resend requests SHALL be limited per client IP address and per submitted email over a rolling window, with configurable limits. Requests over the limit SHALL receive 429 in the standard error envelope with a `Retry-After` header, and no email is sent.

#### Scenario: Too many resends
- **WHEN** resends for one email exceed the per-email limit within the window
- **THEN** further resend requests for that email receive 429 with `Retry-After`

### Requirement: Verify-email page
The frontend SHALL provide a verify-email page that reads the token from the link, confirms it with the backend, and shows the outcome:
- verified;
- link expired, offering to send a new email;
- link invalid or already used, offering to send a new email.

#### Scenario: Successful verification
- **WHEN** a user opens a valid verification link
- **THEN** the page confirms the token and tells the user their email is verified

#### Scenario: Expired link
- **WHEN** a user opens an expired verification link
- **THEN** the page says the link has expired and lets the user request a new verification email

### Requirement: Email delivery failures do not fail the request
If sending an email fails, the sign-up or resend request SHALL still succeed. The failure SHALL be logged without the token or the full email address, and the user can request a resend.

#### Scenario: Mail server unavailable
- **WHEN** the mail server is unreachable during sign-up
- **THEN** the response is still 202, the account exists, and the failure is logged
