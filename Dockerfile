FROM node:22-bookworm-slim AS frontend-build

WORKDIR /workspace
COPY package.json package-lock.json ./
COPY frontend/package.json frontend/package.json
RUN npm ci --workspace frontend
COPY frontend frontend
ARG VITE_DEMO_MODE=true
ENV VITE_DEMO_MODE=${VITE_DEMO_MODE}
RUN npm run build --workspace frontend

FROM python:3.12-slim AS runtime

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FRONTEND_DIST_DIR=/app/static

COPY --from=ghcr.io/astral-sh/uv:0.13.9 /uv /uvx /bin/
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
ENV PATH="/app/.venv/bin:${PATH}"
COPY backend/app ./app
COPY --from=frontend-build /workspace/frontend/dist ./static

EXPOSE 10000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
