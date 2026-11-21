# PermitPilot hackathon pitch runbook

## What the prototype does

PermitPilot is a review-first pitch demo for turning a plain-language business goal into a preparation workflow. The hosted demo has one shared workspace behind a server-side access code; it has no individual user accounts or tenant isolation. Anyone given the code can see and change the same demo data, so use synthetic information only.

The app can interview for missing facts, save a user-reviewed business profile, evaluate a small candidate ruleset, extract relevant text from selected public West Bengal government pages and up to two relevant same-host links, and produce a PDF fact sheet for human review. Candidate URLs are checked live: 404/410 links are marked not found, and network/TLS failures are shown as unavailable rather than valid. Up to four linked PDFs can be downloaded for inline preview; detectable text fields can be prefilled from confirmed facts or user edits and downloaded as a draft. Extraction reads static HTML; JavaScript-only, login-protected, legacy-TLS, and unreachable portals may still fail. If the selected West Bengal Shops & Establishments portal cannot be fetched directly and Gemini is configured, it can also use Google Search grounding and show HTTPS `.gov.in` citations as unverified research leads.

The PDF draft filler only writes detected text fields, uses confirmed or manually edited values, and never submits anything. It does **not** confirm that a candidate form applies to the business, fill a web portal, operate authenticated government portals, sign, or submit an application. Captured pages and rule results are research leads, not verified legal advice. Document upload stores the file and basic metadata; it does not OCR.

Compliance follow-up questions use validated Gemini output when available. If Gemini is not configured or a request fails, the app labels its response as an evidence-only summary of the saved assessment; it does not expose raw provider error details or turn candidate data into legal advice.

All interface screens have local English/Hindi translations. Browser speech reads the main content, while official source excerpts, dynamic records, and user-entered details stay in their original language.

Business DNA and Documents also contain DigiLocker and smart-scan UI previews. They are explicitly nonfunctional frontend demonstrations: no ID verification, DigiLocker redirect, OCR/Gemini processing, or preview-panel upload occurs. The selected scan is previewed locally in the browser only.

## Suggested 3-minute demo

Use this non-food goal: **“I want to open a clothing shop called ‘UrbanThread’ in Kolkata, commercial storefront.”** It exercises the prototype's known retail, business-name, location, and premises parsing without relying on a food-only path.

### Before judges arrive

- Confirm the Render service is live, the access-code gate works, and the shared demo workspace loads. The persistent disk is required for saved demo state.
- Share the access code privately; do not put it in slides or public chat. Generate a separate code if it has been widely shared.
- Use synthetic business/applicant details only. Do not enter real personal addresses.
- Confirm the saved Business DNA profile and current Compliance results are present.
- If you plan to demonstrate Gemini live-search fallback, confirm `GEMINI_API_KEY` and the configured model support Google Search grounding. If it is unavailable, use a previously captured source and state that live search is not configured; do not spend multiple calls retrying during the pitch.
- Keep the generated preparation-sheet PDF ready as a fallback in case a public portal is slow.

1. **0:00–0:25 — State the problem.** Explain that starting a business means piecing together fragmented requirements, forms, and local procedures. Enter the private demo code before presenting; all judges share one workspace.
2. **0:25–0:55 — Show Business DNA.** Open the saved profile and point out that the business facts are editable and must be confirmed. Briefly show the DigiLocker preview and explain that no identity service is connected. If using a fresh workspace, enter the synthetic goal, extract facts, review them, and save.
3. **0:55–1:25 — Show Compliance.** Open a result and ask one question about it. Point out its applicability status, missing facts, and source context; call the result a local candidate assessment, not legal advice.
4. **1:25–2:10 — Show Red Tape Agent.** Start the exact goal above. If it asks for the applicant or address, answer “skip” to avoid personal information. Trigger source discovery. Show the extracted page count and live status badges. If a link is marked not found, point out that it is not offered as a working form; expand a responding source page. If a downloadable PDF appears, preview it inline and show the user-reviewed text-field draft workflow. Explain that this is bounded extraction—not portal login, legal verification, signing, or submission. If Gemini search appears, identify its citations as leads.
5. **2:10–2:40 — Show the review sheet.** Generate or open the preparation PDF and inspect known facts, unconfirmed details, source status, and the human-review warning. If time allows, show the Documents scan preview and explain that OCR is not connected. Call the PDF a preparation sheet—not an official application or signature.
6. **2:40–3:00 — Close with the boundary and next step.** State that a downloaded PDF draft is not proof of applicability and nothing is submitted. The next milestone is validating one portal-specific form schema with the relevant authority.

If live government pages are slow or unavailable, use an already captured source record or describe the retry behavior. Do not imply that a failed capture is a successful research result.

## 60-second pitch

“Starting a small business often means translating a simple goal into a maze of local rules, missing facts, and scattered government pages. PermitPilot turns that goal into a guided preparation workflow. It interviews for only the facts it needs, asks the user to review those facts, evaluates a local candidate ruleset, and captures selected public sources so the user can inspect the evidence. It then generates a transparent preparation sheet—not a signed or submitted application. Our differentiator is the review-first chain from user-confirmed facts to evidence and next steps, rather than a chatbot that gives unsupported legal answers. Today’s prototype is intentionally limited to selected West Bengal sources. The next step is to partner on one specific portal and build a verified form adapter before claiming direct filing.”

## Criteria coverage

This assessment uses the project criteria described in the request; no separate judging rubric or target application was provided.

| Requested capability | Current prototype | Honest status |
|---|---|---|
| Research unstructured government/municipal sources | Captures selected public pages; Gemini Google Search grounding is a fallback for the selected Shops & Establishments portal when direct fetch fails | Partial; narrow West Bengal coverage, requires a Gemini key for search fallback, and citations/findings need human verification |
| Conversational interview and memory | Goal-based interview asks for missing preparation facts and retains them in the session | Implemented for the prototype workflow; not a general legal interview engine |
| Fetch and fill official forms | Checks candidate link availability, marks 404/410 links not found, previews downloadable PDFs inline, and lets users review/edit detected text fields before downloading a local draft | Partial; no verified applicability/schema, scanned-form OCR, web-portal filling, or submission |
| DigiLocker identity and smart scan | Shows frontend-only identity and local file preview screens with clear nonconnection labels | Not connected; no identity verification, ID retrieval, OCR, or Gemini processing |
| Hosted pitch demo | Render single-instance service with a shared access code and persistent SQLite/upload disk | Restricted demo only; no individual accounts, tenant isolation, or production customer data |
| Transparent review and final signature/submission | Shows collected facts, missing/unconfirmed details, sources, and a human acknowledgment | Partial; acknowledgment is not a legal signature, and no government submission occurs |
| Broad industry and jurisdiction support | Profile and rules flow is not limited to food; food rules are conditional | Partial; live source coverage is narrow and must not be presented as nationwide |

## What can make it stand out

- **Evidence-first interaction:** show the source and uncertainty beside the result, not only an AI answer.
- **User-controlled facts:** demonstrate editing an extracted candidate before it affects the assessment.
- **Non-food example:** show that the workflow begins with the user's activity rather than assuming FSSAI.
- **Trustworthy restraint:** explicitly show what the system will not sign, submit, or claim to have verified.
- **Language access:** switch the landing page and core Agent workflow between English and Hindi, then use browser speech to read visible content aloud. Explain that source text remains in its published language.
- **A credible roadmap:** propose real account-based authentication, per-workspace isolation, and managed storage before onboarding customers; then validate one portal-specific adapter with a real authority.

## Judge-safe language

- Say “captured public source page” or “candidate source,” not “verified law.”
- Say “local ruleset assessment,” not “complete legal compliance.”
- Say “preparation sheet,” not “filled official application.”
- Say “human review acknowledgment,” not “signature” or “approval to submit.”
- Say “manual submission required”; no government portal submission occurs.
- Do not claim the prototype satisfies official form-filling or filing criteria.

## Next milestone

Select one exact application and jurisdiction with the hackathon team or a local business authority. Verify the official portal, form schema, allowed automation, required user evidence, and submission boundary. Then implement and test only that adapter, preserving user review before any irreversible action.
