## Purpose

Lets users of any role sign in with email and password and stay signed in securely through short-lived access tokens and rotating refresh tokens. Lets them sign out, and gives the rest of the system a trustworthy "current user".

## ADDED Requirements

### Requirement: Login with email and password
The system SHALL let an active account sign in with its email (compared case-insensitively) and password. A successful login SHALL respond 200 with:
- an access token and its lifetime in seconds;
- a refresh token and its lifetime in seconds;
- the token type `bearer`.

#### Scenario: Successful login
- **WHEN** a user with a verified email submits the correct email and password
- **THEN** the response is 200 with an access token, a refresh token, token type `bearer`, and both lifetimes

#### Scenario: Email is matched case-insensitively
- **WHEN** a user registered as `juan@example.com` logs in with `Juan@Example.COM` and the correct password
- **THEN** the login succeeds

### Requirement: Login failures do not reveal accounts
A wrong password, an unknown email, and a soft-deleted account SHALL all produce the same 401 response with error code `invalid_credentials`. These cases SHALL take comparable time: a password hash check is performed even when no account matches.

#### Scenario: Wrong password
- **WHEN** a user submits a registered email with the wrong password
- **THEN** the response is 401 with code `invalid_credentials`

#### Scenario: Unknown email
- **WHEN** someone submits an email that has no active account
- **THEN** the response is identical to the wrong-password response

### Requirement: Verified email required to sign in
An account whose email is not verified SHALL NOT receive tokens. When the password is correct, the response SHALL be 403 with error code `email_not_verified`. Because this happens only after a correct password, it reveals the account only to someone who knows the password.

#### Scenario: Unverified email with correct password
- **WHEN** a user whose email is not verified submits the correct email and password
- **THEN** the response is 403 with code `email_not_verified` and no tokens

#### Scenario: Unverified email with wrong password
- **WHEN** a user whose email is not verified submits a wrong password
- **THEN** the response is 401 with code `invalid_credentials`

### Requirement: Pending doctors can sign in
A doctor's PRC license status SHALL NOT block login. Doctors whose license is pending or rejected SHALL be able to sign in once their email is verified.

#### Scenario: Pending doctor signs in
- **WHEN** a doctor with a verified email and a pending license submits the correct credentials
- **THEN** the login succeeds

### Requirement: Login rate limiting
Login attempts SHALL be limited per client IP and per submitted email over a rolling window, with configurable limits. Attempts over the limit SHALL receive 429 in the standard error envelope with a `Retry-After` header. Over-limit attempts SHALL NOT check the password.

#### Scenario: Too many attempts for one email
- **WHEN** login attempts for one email exceed the per-email limit within the window
- **THEN** further attempts for that email receive 429 with `Retry-After`, even with the correct password

### Requirement: Access tokens
Access tokens SHALL be signed, identify the user and their role, and expire after a configurable lifetime (15 minutes by default). Requests SHALL present them as `Authorization: Bearer <token>`. A missing, malformed, expired, or tampered token, or one for an account that is no longer active, SHALL be rejected with 401 and a `WWW-Authenticate: Bearer` header.

#### Scenario: Valid token
- **WHEN** a request presents a valid, unexpired access token
- **THEN** it is treated as coming from that user

#### Scenario: Expired or tampered token
- **WHEN** a request presents an expired access token, or one whose signature does not match
- **THEN** the response is 401 with a `WWW-Authenticate: Bearer` header

#### Scenario: Account deleted after login
- **WHEN** a request presents a valid access token for an account that has since been soft-deleted
- **THEN** the response is 401

### Requirement: Refresh token rotation
A refresh token SHALL be usable once. Exchanging a valid refresh token SHALL return a new access token and a new refresh token, and retire the presented one. Refresh tokens SHALL expire after a configurable lifetime (30 days by default). Only hashes of refresh tokens SHALL be stored.

#### Scenario: Refresh
- **WHEN** a client exchanges a valid, unused refresh token
- **THEN** the response is 200 with a new access token and a new refresh token, and the presented refresh token can no longer be used

#### Scenario: Expired or unknown refresh token
- **WHEN** a client exchanges an expired or never-issued refresh token
- **THEN** the response is 401 with code `invalid_refresh_token`

### Requirement: Refresh token reuse revokes the session
If an already-used refresh token is presented again, the system SHALL treat the session as compromised. It SHALL revoke every refresh token issued in that session's chain, including the newest one, and respond 401 with code `invalid_refresh_token`.

#### Scenario: Stolen token replayed
- **WHEN** a refresh token that was already exchanged is presented again
- **THEN** the response is 401, and the latest refresh token of that session also stops working

### Requirement: Logout
Logging out with a refresh token SHALL revoke that session's refresh tokens and respond 204. Logging out with an unknown, expired, or already-revoked refresh token SHALL also respond 204. Access tokens already issued remain valid until they expire.

#### Scenario: Logout
- **WHEN** a signed-in user logs out with their refresh token
- **THEN** the response is 204 and that refresh token can no longer be exchanged

#### Scenario: Logout is idempotent
- **WHEN** a client logs out with a refresh token that was already revoked
- **THEN** the response is 204

### Requirement: Current user
An authenticated request SHALL be able to fetch the current user's profile: identifier, names, email, role, and whether the email is verified. For doctors it SHALL also include the specialization and the license status. An unauthenticated request SHALL receive 401.

#### Scenario: Doctor profile
- **WHEN** a signed-in doctor with a pending license requests their profile
- **THEN** the response includes role `doctor` and license status `pending`

#### Scenario: Not signed in
- **WHEN** a request without an access token asks for the current user
- **THEN** the response is 401

### Requirement: Password hashes stay current
When a user logs in successfully and their stored password hash uses outdated hashing parameters, the system SHALL replace it with a hash using the current parameters.

#### Scenario: Outdated hash upgraded
- **WHEN** a user whose stored hash uses weaker parameters logs in successfully
- **THEN** their stored hash is replaced with one using the current parameters, and they can still log in with the same password

### Requirement: Login page
The frontend SHALL provide a login page. On success it SHALL sign the user in and take them to their account page, or to the page they were trying to reach. It SHALL show:
- a generic error for invalid credentials;
- a "verify your email first" message, with the option to resend the verification email, for `email_not_verified`;
- a wait message for rate limiting.

It SHALL link to the forgot-password page and to doctor sign-up.

#### Scenario: Unverified email
- **WHEN** the backend answers a login with `email_not_verified`
- **THEN** the page tells the user to verify their email first and offers to resend the verification email to the entered address

#### Scenario: Successful login
- **WHEN** the user logs in successfully
- **THEN** they are taken to their account page, and the header shows that they are signed in

### Requirement: Frontend session handling
The frontend SHALL keep the access token in memory only and send it on API requests as a bearer token. It SHALL persist the refresh token so a page reload keeps the user signed in. When an API request fails with 401, the frontend SHALL try one token refresh and retry the request once. If the refresh fails, it SHALL sign the user out locally. Logging out SHALL call the backend and then clear the stored tokens.

#### Scenario: Access token expired during use
- **WHEN** an API request returns 401 because the access token expired, and the refresh token is still valid
- **THEN** the frontend refreshes the tokens and the original request succeeds without user action

#### Scenario: Session ended
- **WHEN** both the access token and the refresh token are no longer valid
- **THEN** the user is signed out locally and asked to log in again

### Requirement: Account page
The frontend SHALL provide an account page for signed-in users that shows their name, email, and role. For doctors it SHALL show the license status, with an explanation while the status is "Pending verification" or rejected. Visiting it while signed out SHALL redirect to the login page.

#### Scenario: Pending doctor
- **WHEN** a doctor with a pending license opens the account page
- **THEN** the page shows "Pending verification" and explains that their PRC license is being reviewed

#### Scenario: Signed out
- **WHEN** a signed-out visitor opens the account page
- **THEN** they are redirected to the login page, and after logging in they return to the account page
