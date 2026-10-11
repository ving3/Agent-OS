FROM python:3.11-slim

LABEL org.opencontainers.image.title="Agentic OS Dashboard"
LABEL org.opencontainers.image.description="Dashboard de gestion des agents Hermes avec chat, kanban et memoire"

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ── Outils système ──────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates && \
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" && \
    chmod +x kubectl && mv kubectl /usr/local/bin/ && \
    rm -rf /var/lib/apt/lists/*

# ── Node.js pour le build frontend ──────────────────────────────────────────────
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g npm@latest

WORKDIR /opt/app

# ── Backend Python ──────────────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

# ── Frontend TypeScript ─────────────────────────────────────────────────────────
COPY frontend/package.json frontend/package-lock.json* frontend/tsconfig.json frontend/build.mjs ./frontend/
RUN cd frontend && npm install --production=false

COPY frontend/src/ ./frontend/src/
COPY frontend/dist/index.html ./frontend/dist/
RUN cd frontend && npm run build

EXPOSE 8686

WORKDIR /opt/app/backend
CMD ["python", "main.py"]
