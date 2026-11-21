# Product roadmap after the private pitch demo

The private, shared-workspace Render demo is configured in `render.yaml`.
This roadmap is for a real multi-user product; the demo access code is not
account authentication, and roadmap items are not claims of current support.

## Phase 0 - Audit and demo safety

- [x] Audit the implemented runtime and document current limitations.
- [x] Ignore local environment files, databases, and uploads.
- [x] Add a restricted demo gate and persistent-disk deployment configuration.
- [x] Lock frontend and backend dependencies.

## Phase 1 - Supabase foundation

- Complete PostgreSQL migration.
- Implement user/workspace/business records.
- Add JWT verification and workspace membership checks.
- Configure private Storage and signed downloads.

## Phase 2 - Business DNA

- Add strict Gemini structured extraction.
- Persist candidate and confirmed facts separately.
- Create immutable profile revisions.

## Phase 3 - Compliance engine

- Consolidate rule evaluation.
- Persist assessments and evidence.
- Generate tasks from assessment results.

## Phase 4 - Feature completion

- Documents, Navigator, Radar, simulator, graph, reports and settings.

## Phase 5 - Hardening

- Expand backend and browser test coverage.
- Validate RLS and private storage after the managed multi-user architecture is implemented.
- Add production alerting, backups, user-data retention controls, and tenant-isolation checks.
