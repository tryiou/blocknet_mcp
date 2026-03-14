# Multi-stage Docker build for Blocknet MCP servers
# Usage: docker compose -f docker/docker-compose.yml build xbridge-mcp
#   Or:  docker build --build-arg SERVER_TYPE=xbridge -t xbridge-mcp -f docker/Dockerfile ..

ARG SERVER_TYPE=xbridge

# ---------- Builder Stage ----------
FROM python:3.11-slim AS builder

# Install git for cloning API docs
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Clone Blocknet API docs (shallow)
RUN git clone --depth 1 https://github.com/blocknetdx/api-docs blocknet-api-docs

# Copy generator code and dependencies
COPY requirements.txt .
COPY main.py .
COPY src/ src/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Generate the specified MCP server (output goes to generated/<server_type>_mcp/)
# Map xbridge->dx, xrouter->xr for generator prefix
ARG SERVER_TYPE
RUN case "$SERVER_TYPE" in \
    xbridge) PREFIX="dx" ;; \
    xrouter) PREFIX="xr" ;; \
    *) PREFIX="$SERVER_TYPE" ;; \
    esac && \
    python main.py $PREFIX

# ---------- Runtime Stage ----------
FROM python:3.11-slim

WORKDIR /app

# Install netcat for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

# Add local bin to PATH for installed scripts
ENV PATH=/home/app/.local/bin:$PATH

# Copy generated server from builder
ARG SERVER_TYPE
ENV SERVER_TYPE=${SERVER_TYPE}
COPY --from=builder /build/generated /app/

# Install runtime dependencies (reuse requirements)
COPY --from=builder /build/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
