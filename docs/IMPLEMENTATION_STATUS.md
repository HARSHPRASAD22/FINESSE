# Implementation status

## Completed

- Local mode remains restricted to loopback requests; the hosted pitch mode requires a server-side access code and signed, HttpOnly sessions.
- Private pitch mode uses one shared workspace and SQLite on a configurable persistent disk; it is not multi-user authentication or tenant isolation.
- Render Blueprint and root Dockerfile serve the frontend and API on one origin, with a persistent upload/database disk and a minimal public health check.
- Root npm workspace and lockfile, plus a cross-platform Python `uv.lock`, cover deterministic dependency installation.
- Gemini and official-source adapters.
- Agent interview and PDF review package.
- Profile, assessment, task, document, report and simulator API foundations.
- Frontend production build.
- Private demo access flow, session expiry, explicit lock action, and backend access tests.
- Central profile-aware rules engine used for assessments and scenarios.
- Dynamic non-food versus food-business assessment behavior.
- Red Tape interview parses basic goal details, asks for missing facts, and marks goal-derived facts for confirmation.
- Agent research now excludes FSSAI for non-food goals, captures allowlisted official pages, and extracts candidate form links and relevant text.
- Optional AI source notes use captured public text only and retain a quote that is checked against the source excerpt; they remain unverified research leads, not legal interpretations.
- The persisted home-based food demo update is hidden from the dashboard without deleting its SQLite record.
- Review PDF is explicitly a preparation sheet; review acknowledgment is not presented as a signature or government submission.
- Workspace Settings now persist the workspace name, jurisdiction, and notification preference; user-initiated JSON export is available, while workspace deletion remains disabled to protect local records.
- Reports now load saved report history and export the selected business's saved assessment and matching confirmed profile revision.
- The Red Tape review checkpoint keeps links to captured or uncaptured official portals and allows source research to be retried.
- If the West Bengal Shops & Establishments portal fetch fails and Gemini is configured, research can use Google Search grounding and surface only HTTPS `.gov.in` citations as unverified leads.
- Red Tape source research retries transient connection timeouts once, extracts the start page plus up to two relevant same-host, allowlisted public pages per source, and checks candidate URLs live. HTTP 404/410 results are marked not found; connection/TLS failures are shown as unreachable or unverified rather than treated as valid.
- Downloadable official PDFs are cached locally for inline preview. Detectable PDF text fields can be prefilled from confirmed facts or user edits; the user reviews and downloads a draft, with no signing or submission.
- The landing page and all workspace screens translate their interface labels into English/Hindi. Browser speech synthesis reads the main content only; official source text, dynamic records, and user-entered content remain in their original language.
- A transparent PermitPilot logo is used on the landing page, sidebar, and report preview.
- Business DNA includes a clearly labeled DigiLocker identity preview; Documents includes a local-only scan preview. These are frontend demonstrations only: no identity data, DigiLocker redirect, OCR, Gemini request, or document upload is performed by either preview.
- Dynamic profile, dashboard and report data from stored records.
- Real source-scan trigger with official capture attempts.
- Compliance questions use the backend requirement-question endpoint and show an evidence-only summary when Gemini is unconfigured or unavailable.
- Business profile facts can be edited before confirmation and restored from saved profile history.
- Radar records link to the captured official page; the former fake source-version comparison was removed.
- Documents can be uploaded to local storage with basic metadata; the UI states that OCR and official-form mapping are not implemented.
- PDF report/download generation.
- Task creation and completion API handlers.
- New installs start with one empty local workspace; existing database records are retained.
- 3 focused rules-engine tests passing.
- Additive workspace, membership and business SQLite schema.
- Immutable business profile revision persistence.
- Profile confirmation creates and stores assessments and result rows.
- Gemini extraction reports provider/fallback state explicitly; assessment questions validate model output and fall back to a readable stored-evidence summary without returning raw provider exceptions.
- Assessment requests resolve the latest confirmed profile revision.
- Cross-workspace profile and document tests pass.
- Profile confirmation and profile revision tests pass.
- Frontend navigation reduced to core hackathon journey.
- A React landing page introduces the real review-first workflows and explains source coverage and review limitations.

## Remaining

- Real user accounts, workspace-level tenant isolation, and production authorization before onboarding external customers.
- Verified official form applicability, complete form schemas, and per-portal adapters.
- Current, legally verified regulatory summaries and reliable live portal coverage.
- Government portal account integration, electronic signature, and submission (intentionally not automated).
- Portal-specific interactive form adapters; the supported portals do not have a verified field map or stable integration contract yet.
- Broad jurisdiction/industry source coverage and legally verified summaries.
- Connected OCR for scanned/image-only forms, automatic filling of web portals, and live government portal operation.
- Translation of dynamic source text, backend records, and user-entered content (intentionally not sent to an external translation service).
- Managed private object storage and managed database for a multi-user product.
- Strict Gemini extraction schemas and retry behavior.
- Canonical approved-rule registry and human review lifecycle.
- Real source snapshots and change lifecycle.
- Complete profile-linked dashboard and requirement detail.
- Multi-workspace management and actual email/push notification delivery.
- Backend and end-to-end test suite.

## Blockers requiring project configuration

- Real account-based authentication, authorization, and tenant isolation before any public multi-user deployment. The current hosted access-code gate is only for a restricted pitch demo.
- Gemini API key.
- Real reviewed regulatory rules and sources.
