# Free Gemini setup

1. Open https://aistudio.google.com/apikey.
2. Sign in and create an API key.
3. Set `GEMINI_API_KEY` in `backend/.env` or the backend process environment.
4. Set `GEMINI_MODEL=gemini-2.5-flash`.
5. Set `LLM_PROVIDER=gemini`.

PermitPilot uses Gemini only for evidence extraction and interview assistance. Structured results must validate against a Pydantic schema, and Gemini cannot publish rules or submit applications. A missing key returns a configuration error instead of fake legal conclusions.
