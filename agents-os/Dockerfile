FROM python:3.11-slim

LABEL org.opencontainers.image.title="Agentic OS Dashboard"
LABEL org.opencontainers.image.description="Dashboard de gestion des agents Hermes avec chat, kanban et memoire"

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install oc/kubectl for Hermes pod exec
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && \
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" && \
    chmod +x kubectl && mv kubectl /usr/local/bin/ && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /opt/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/

EXPOSE 8686

CMD ["python", "-m", "app.main"]
