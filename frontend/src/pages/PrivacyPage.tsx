// Must match the backend's PRIVACY_NOTICE_VERSION, which is stored with each consent.
export const PRIVACY_NOTICE_VERSION = '2026-11-draft'

/** Placeholder. The full notice is part of US-07.1 (Data Privacy Act compliance basics). */
export function PrivacyPage() {
  return (
    <section className="page page--narrow">
      <h1>Privacy notice</h1>
      <p className="page__muted">Version {PRIVACY_NOTICE_VERSION} (draft)</p>
      <p>
        RecliniQ collects the personal information you provide (such as your name, contact details,
        and professional license) to create and verify your account and to provide consultation
        services, in line with the Data Privacy Act of 2012 (Republic Act No. 10173).
      </p>
      <p>The complete privacy notice will be published here before launch.</p>
    </section>
  )
}
