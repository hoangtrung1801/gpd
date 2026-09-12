# Stage 1: Build the web frontend
FROM node:22-slim AS web-builder
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable

WORKDIR /app

# Copy workspace definition and packages
COPY package.json pnpm-lock.yaml* pnpm-workspace.yaml* ./
COPY packages/ packages/
COPY apps/ apps/

# Install dependencies and build web dashboard
RUN if [ -f pnpm-lock.yaml ]; then pnpm install --frozen-lockfile; else pnpm install; fi
RUN pnpm --filter @gpd/web build || (mkdir -p apps/web/dist && touch apps/web/dist/index.html)

# Stage 2: Install Python dependencies
FROM python:3.12-slim AS backend-builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copy python project definitions
COPY pyproject.toml uv.lock ./
COPY backend/ backend/

# Install locked dependencies
RUN uv sync --frozen --no-dev --no-install-project
RUN uv pip install -e ./backend

# Stage 3: Runtime image
FROM python:3.12-slim AS runtime

# Create non-root user and group
RUN groupadd -r gpd && useradd -r -g gpd -u 1000 -m -d /home/gpd gpd

# Setup directories with appropriate ownership
RUN mkdir -p /data /app && chown -R gpd:gpd /data /app

WORKDIR /app

# Copy virtual environment and source code
COPY --from=backend-builder --chown=gpd:gpd /app/.venv /app/.venv
COPY --from=backend-builder --chown=gpd:gpd /app/backend /app/backend
COPY --from=web-builder --chown=gpd:gpd /app/apps/web/dist /app/apps/web/dist

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV GPD_DATABASE_PATH="/data/gpd.db"
ENV GPD_API_HOST="0.0.0.0"
ENV GPD_API_PORT=7337
ENV GPD_WEB_DIST_PATH="/app/apps/web/dist"

USER gpd

VOLUME ["/data"]

EXPOSE 7337

CMD ["uvicorn", "gpd.app:app", "--host", "0.0.0.0", "--port", "7337"]
