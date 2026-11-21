# PermitPilot implementation audit

Date: 2026-11-21

## Repository structure

- React 19 + TypeScript + Vite frontend in `frontend/`
- FastAPI backend in `backend/app/`
- Supabase migration in `supabase/migrations/`
- Gemini and official-source adapters in `backend/app/integrations/`
- Primary application UI in `frontend/src/App.tsx`
- Primary backend implementation in `backend/app/main.py`

## Current state

### Working foundations

- English/Hindi React interface with body-only browser speech.
- FastAPI health and feature endpoints.
- Gemini and official-source provider adapters.
- Local SQLite persistence for development.
- Private document files stored locally, with configurable database/upload paths.
- PDF generation for review/report packages.
- A restricted Render pitch deployment with one same-origin frontend/API service, persistent disk, and server-side access-code sessions.
- npm and Python dependency lockfiles.

### Current limitations

- SQLite remains the application database; the hosted demo has one shared workspace.
- The hosted access-code session is not account authentication. It does not provide per-user identity, multi-tenant workspace isolation, or production customer data protections.
- Supabase migrations are historical scaffolding and are not used by the current runtime.
- The demo's disk-backed files are not managed object storage.
- The compliance rule list is candidate data, not independently reviewed legal rules.
- Business profile extraction combines Gemini and local parsing but needs a strict Pydantic contract.
- Source scans capture pages but do not persist immutable snapshots or create review records.
- Reports are not tied to an assessment snapshot.
- The dependency graph is derived, but relationship storage is incomplete.
- The simulator invokes a separate endpoint rather than the central rules engine.
- Some settings are browser-local.
- Real account registration, password recovery, user-specific sessions, and workspace membership management are not implemented.

## Security

- `.env`, `.env.local`, local databases, and uploads must remain untracked; the root ignore rules exclude them.
- Set the demo code and any Gemini key only in the hosting provider's secret environment settings.
- The hosted demo is intentionally limited to synthetic data. Anyone with the shared code can access the same workspace.
- Do not expose the current shared-workspace backend as a public multi-user product; real authentication, workspace authorization, managed storage, and tenant-isolation tests are required first.
