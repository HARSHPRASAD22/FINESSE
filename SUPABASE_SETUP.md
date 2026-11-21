# Supabase integration status

Supabase authentication is no longer used by the local single-user app.
No Supabase project or credentials are required to start PermitPilot.

The SQL migration files remain in the repository as historical artifacts and
are not applied by the local app. Do not run them to enable this local mode.
The backend uses its existing SQLite database and preserves existing records.
