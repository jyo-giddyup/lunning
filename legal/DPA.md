# Data Processing Addendum (DPA) — TEMPLATE

**This is a template, not legal advice.** Cross-border data transfer law (Schrems II, UK IDTA, EU SCCs) changes frequently. Have counsel review before signing this with any customer.

This DPA is incorporated into the Terms of Service between lunning ("Processor") and the Customer ("Controller") whose users use the Service.

## 1. Definitions

Terms used (Personal Data, Processing, Data Subject, Controller, Processor, Subprocessor) have the meanings given in EU GDPR Art. 4 / UK GDPR.

## 2. Subject matter and duration

Processor will process Personal Data on behalf of Controller for the duration of the Services and as further described in `legal/PRIVACY.md`.

## 3. Subprocessors

Controller authorizes the use of the following Subprocessors:

| Subprocessor | Purpose | Location |
|---|---|---|
| Supabase, Inc. | Managed PostgreSQL hosting | TODO (region depends on project setup) |
| Vercel, Inc. | Application hosting and edge network | Global |

Processor will give Controller 30 days notice before adding or replacing Subprocessors. Controller may object on reasonable grounds.

## 4. Security measures

Processor implements technical and organizational measures including:

- Encryption in transit (TLS 1.2+) and at rest (provider-managed).
- Append-only event log at the application layer.
- Service-role credentials kept outside source control.
- Access on a need-to-know basis.
- Vulnerability disclosure process per `legal/SECURITY.md`.

More detailed measures will be provided on request and reviewed annually.

## 5. International transfers

Where Personal Data is transferred outside the EEA/UK/Switzerland, the parties will rely on the EU Standard Contractual Clauses (Decision 2021/914) and the UK International Data Transfer Addendum, attached as Annex II (TODO).

## 6. Data subject rights

Processor will assist Controller in responding to data subject requests within 10 business days of receipt.

## 7. Breach notification

Processor will notify Controller of a Personal Data breach without undue delay, and in any event within 48 hours of becoming aware.

## 8. Audit

Controller may audit Processor's compliance with this DPA no more than once per year, at Controller's expense, on reasonable notice.

## 9. Return or deletion

On termination, Processor will delete or return Personal Data within 30 days, except where retention is required by law.

## 10. Liability

Liability under this DPA is subject to the limitations in the Terms of Service.
