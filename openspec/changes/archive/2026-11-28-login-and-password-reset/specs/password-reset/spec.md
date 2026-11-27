## Purpose

Lets a user who forgot their password regain access with a single-use, expiring link sent to their email. It never reveals which emails are registered, and it signs the account out everywhere after the reset.

## ADDED Requirements

### Requirement: Requesting a reset link
A user SHALL be able to request a password reset by submitting an email address. The response SHALL always be 202 with the same body. If the address belongs to an active account, the system SHALL email it a link to the frontend's reset-password page carrying a random, unguessable token. Only a hash of the token SHALL be stored, and the link SHALL expire after a configurable period (60 minutes by default).

#### Scenario: Registered email
- **WHEN** a user requests a reset for the email of an active account
- **THEN** the response is 202 and the address receives an email with a reset link

#### Scenario: Unknown email
- **WHEN** someone requests a reset for an email with no active account
- **THEN** the response is 202 with the same body, and no email is sent

### Requirement: Newest reset link wins
Requesting a new reset link SHALL invalidate all earlier unused reset links for that account.

#### Scenario: Older link after a new request
- **WHEN** a user requests two reset links and uses the first one
- **THEN** the first link is rejected as invalid

### Requirement: Reset request rate limiting
Reset requests SHALL be limited per client IP and per submitted email over a rolling window, with configurable limits. Requests over the limit SHALL receive 429 in the standard error envelope with a `Retry-After` header, and no email is sent.

#### Scenario: Too many requests
- **WHEN** reset requests for one email exceed the per-email limit within the window
- **THEN** further requests for that email receive 429 with `Retry-After`

### Requirement: Setting a new password
Submitting a valid reset token with a new password SHALL replace the account's password. The new password SHALL meet the same password policy as sign-up, and a policy violation SHALL be rejected with 422 naming the password field, without using up the token. A successful reset SHALL use up the token and respond 200.

#### Scenario: Successful reset
- **WHEN** a user submits a valid, unused, unexpired reset token and a new password that meets the policy
- **THEN** the response is 200, the user can log in with the new password, and the old password no longer works

#### Scenario: Weak new password
- **WHEN** a user submits a valid token with a password on the common-password list
- **THEN** the response is 422 naming the password field, and the token can still be used

#### Scenario: Used, expired, or unknown token
- **WHEN** a user submits a reset token that was already used, has expired, or was never issued
- **THEN** the response is 400 with code `invalid_token` (used or unknown) or `token_expired` (expired), and the password is unchanged

### Requirement: Reset signs out everywhere
A successful password reset SHALL revoke every refresh token of the account, so other sessions must sign in again with the new password.

#### Scenario: Other session after reset
- **WHEN** a user resets their password while another device holds a refresh token
- **THEN** that refresh token can no longer be exchanged

### Requirement: Reset proves email ownership
A successful password reset SHALL mark the account's email as verified if it was not already, because using the link proves the user controls the address.

#### Scenario: Unverified account resets password
- **WHEN** a user whose email was never verified completes a password reset
- **THEN** their email is marked verified and they can log in with the new password

### Requirement: Forgot and reset password pages
The frontend SHALL provide a forgot-password page that requests a reset link and always shows the same confirmation. It SHALL also provide a reset-password page that reads the token from the link and accepts a new password, checking the password length before submitting. On success the reset page SHALL tell the user to sign in with the new password. For an invalid or expired link it SHALL offer to request a new one.

#### Scenario: Request a link
- **WHEN** a user submits their email on the forgot-password page
- **THEN** the page shows "If an account exists for this email, we've sent a reset link", whatever the outcome

#### Scenario: Expired link
- **WHEN** a user submits a new password with an expired reset link
- **THEN** the page says the link has expired and links to the forgot-password page
