# PermitPilot

PermitPilot is a review-first workspace for business setup research, candidate
compliance checks, tasks, documents, and preparation reports.

## Deployment scope and data warning

The included Render deployment is a **private pitch demo**, not a public
multi-user product. It has one shared workspace protected by one server-side
access code. Anyone with that code can see and change the same demo data. Use
synthetic information only; do not enter real identity documents, customer
records, or confidential business data.

The backend uses SQLite and local file storage on a persistent Render disk.
The deployment is intentionally single-instance and does not provide user
accounts, per-user tenant isolation, application-level backups, or production
data-retention controls. Render may provide platform disk snapshots subject to
its current service terms; do not treat them as a tested application backup.
DigiLocker, OCR, payments, and government filing are not connected. The demo
access code is not an account system.

## Run locally

Prerequisites: Windows PowerShell, Node.js 22.12+, Python 3.11+, and uv 0.13+.

Install the locked frontend dependencies from the repository root:

```powershell
Set-Location D:\PERMITPILOT
npm ci
```

Install the locked backend and test dependencies:

```powershell
Set-Location D:\PERMITPILOT\backend
uv sync --frozen --dev --no-install-project
if (-not (Test-Path .env)) { Copy-Item ..\.env.example .env }
```

The Gemini key is optional for local startup. If needed, put it in
`backend\.env`; never commit it.

Start the backend in one terminal:

```powershell
Set-Location D:\PERMITPILOT\backend
uv run --no-sync python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend in another:

```powershell
Set-Location D:\PERMITPILOT
npm run dev
```

Open http://127.0.0.1:5173. The local mode remains restricted to loopback
clients and keeps its SQLite database and uploads under `backend\`.

## Build and test

```powershell
Set-Location D:\PERMITPILOT
npm run lint
npm run build
```

Backend tests use an isolated temporary database so the local workspace is not
modified:

```powershell
Set-Location D:\PERMITPILOT\backend
$testRoot = Join-Path $env:TEMP ("permitpilot-tests-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $testRoot | Out-Null
$env:PYTHON_DOTENV_DISABLED = '1'
$env:APP_ENV = 'development'
$env:DATABASE_PATH = Join-Path $testRoot 'permitpilot.db'
$env:UPLOAD_DIR = Join-Path $testRoot 'uploads'
uv run --no-sync python -m pytest
Remove-Item -LiteralPath $testRoot -Recurse -Force
```

## Deploy the free private demo to Render

1. In Render, create a **Blueprint** from this GitHub repository and select the
   `main` branch. Render reads `render.yaml` and builds the root `Dockerfile`.
   The blueprint uses a Free web service and does not create a paid persistent
   disk. Free services sleep after 15 minutes without traffic and can take about
   a minute to wake. The local SQLite database and uploaded files are temporary:
   they can be lost whenever the service sleeps, restarts, or redeploys.
2. Set `DEMO_ACCESS_CODE` in the Render service environment to a generated
   secret of at least 20 characters. Generate one locally with:

   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(24))"
   ```

   Enter the generated value directly in Render; do not commit or share it
   publicly. Render generates `DEMO_SESSION_SECRET` for signed, HttpOnly sessions.
3. Optionally add `GEMINI_API_KEY` in Render's environment settings to enable
   live Gemini features. Do not put the key in this repository or frontend
   variables.
4. Open the Render URL, enter the access code, and use only synthetic data.
   Demo sessions expire after 12 hours; **Lock demo** ends the current session.
   Do not upgrade the service or add a persistent disk if you want to keep this
   deployment free. Render Free has usage limits; check the Render dashboard
   for current limits and usage.

The frontend and API are served from the same origin. The public health check
only returns service status; application API routes require a valid demo
session. Do not remove the access-code gate or convert this shared-workspace
setup into a public production service without implementing real user
authentication, tenant isolation, and managed database/object storage.
