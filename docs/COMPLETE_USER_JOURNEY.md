# PermitPilot complete user journey

## 1. Authentication

1. Create or sign in to a Supabase account.
2. Establish the session and refresh it as needed.
3. Retrieve accessible workspaces.
4. Create or select a workspace.

## 2. Business DNA

1. Describe the business in natural language.
2. Extract candidate facts using Gemini with schema validation.
3. Edit, correct or mark facts unknown.
4. Confirm the immutable profile revision.
5. Start the first assessment.

## 3. Compliance

1. Evaluate only approved or clearly candidate rules.
2. Persist the profile revision, rule versions, engine version and evidence.
3. Display applicable, conditional, unresolved and not-applicable results.
4. Open requirement details and source evidence.
5. Generate tasks and required-document actions.

## 4. Documents

1. Validate and upload a PDF or image.
2. Store it privately.
3. Extract candidate fields.
4. Require user confirmation.
5. Link the document to requirements.
6. Update task state.

## 5. Navigator

1. Reuse confirmed Business DNA facts.
2. Ask only relevant missing questions.
3. Capture official source evidence.
4. Generate a review package.
5. Require explicit approval.
6. Provide manual official-submission instructions.

## 6. Observatory and simulator

1. Scan configured official sources.
2. Capture immutable snapshots.
3. Detect changes and queue human review.
4. Clone confirmed profile facts into a scenario.
5. Re-run the central engine.
6. Compare baseline and scenario results.

## 7. Reports and settings

1. Generate a report from a stored assessment.
2. Secure and download the report.
3. Persist workspace and notification settings.
4. Support logout and session control.
