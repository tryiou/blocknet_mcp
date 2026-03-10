# Docker Deployment Guide

This repository contains Docker configuration to run Blocknet MCP servers with a local Blocknet core node.

## Files

- `Dockerfile` - Multi-stage build that generates and runs MCP servers
- `docker-compose.yml` - Orchestrates blocknet-core, xbridge-mcp, xrouter-mcp
- `.dockerignore` - Excludes unnecessary files from build context

## Prerequisites

1. **Docker** and **Docker Compose** installed
2. **Blocknet blockchain data** path configured via `BLOCKNET_CHAINDIR` (default: `~/.blocknet/`)
3. RPC credentials (username/password) for the Blocknet node

## Quick Start

1. Set RPC credentials in environment or `.env` file:

```bash
# Create .env file
cp .env.example .env

# edit/save the .env with your blocknet core rpc credentials/port
```

2. Start all services:

```bash
docker compose up -d
```

This will:
- Start `blocknet-core` (using your existing blockchain data)
- Build `xbridge-mcp` and `xrouter-mcp` images
- Start MCP servers after blocknet-core becomes healthy

3. Check status:

```bash
docker compose ps
docker compose logs -f xbridge-mcp
docker compose logs -f xrouter-mcp
```

4. Stop services:

```bash
docker compose down
```

## Configuration

### RPC Credentials

The Blocknet core node uses `RPC_USER` and `RPC_PASSWORD` environment variables. These are passed to the MCP servers as well.

### MCP Server Settings

Configurable via environment variables in `docker-compose.yml`:

- `RPC_HOST` - **Fixed**: `localhost` (hardcoded due to `network_mode: host`)
- `RPC_PORT` - Default: `41414`
- `MCP_ALLOW_WRITE` - Default: `false` (set to `true` to enable write operations)
- `MCP_LOG_LEVEL` - Default: `INFO` (DEBUG, INFO, WARNING, ERROR)
- `MCP_TRANSPORT` - Default: `stdio` (transport mode: `stdio` or `http`)
- `MCP_PORT` - Default: `8080` (HTTP port when `MCP_TRANSPORT=http`)

### Volumes

The `blocknet-core` service mounts your existing blockchain data:

```yaml
volumes:
  - ${BLOCKNET_CHAINDIR}:/opt/blockchain/blocknet
```

The path is taken from the `BLOCKNET_CHAINDIR` environment variable (set in `.env`). Default is `~/.blocknet/`.

### Network Mode

All services use `network_mode: "host"` because:
- blocknet-core needs to bind to host network interfaces
- MCP servers connect to RPC on `localhost:41414`

This means services share the host's network stack and can communicate via `localhost`.

## Healthcheck

`blocknet-core` has a healthcheck that runs `blocknet-cli getblockcount`. MCP servers wait for this to pass before starting (via `depends_on` with `condition: service_healthy`).

## Building Images

Images are built automatically by `docker compose up`. To build manually:

```bash
docker compose build
```

Or build individually:

```bash
docker build --build-arg SERVER_TYPE=xbridge -t xbridge-mcp .
docker build --build-arg SERVER_TYPE=xrouter -t xrouter-mcp .
```

## Logs

View logs for all services:

```bash
docker compose logs -f
```

View logs for a specific service:

```bash
docker compose logs -f xbridge-mcp
```

Log rotation is configured for blocknet-core:
- Max size: 2MB
- Max files: 10

## Troubleshooting

### MCP server fails to start

Check that blocknet-core RPC is accessible:

```bash
curl http://${RPC_USER}:${RPC_PASSWORD}@localhost:41414/
```

Check logs:

```bash
docker compose logs xbridge-mcp
```

### Healthcheck fails

Verify Blocknet node is running and synced:

```bash
docker compose exec blocknet-core blocknet-cli getblockcount
```

If the node is still starting, increase `start_period` in healthcheck.

### Permission errors on volume

Ensure the Docker container has read/write access to the path specified in `BLOCKNET_CHAINDIR`. The Blocknet image expects to write to this directory.

### Port already in use

With `network_mode: host`, services bind directly to host ports. Make sure port 41414 is not used by another process:

```bash
sudo lsof -i :41414
```

## Images

- `blocknetdx/blocknet:latest` - Official Blocknet Core node
- `xbridge-mcp` and `xrouter-mcp` - Built from local Dockerfile (no tag)

## Environment Variables

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `RPC_HOST` | localhost | No | localhost (fixed due to host network mode) |
| `RPC_PORT` | 41414 | Yes | Blocknet RPC port |
| `RPC_USER` | - | Yes | RPC username |
| `RPC_PASSWORD` | - | Yes | RPC password |
| `RPC_TIMEOUT` | 30 | No | RPC timeout in seconds |
| `MCP_ALLOW_WRITE` | false | No | Enable write operations (use with caution) |
| `MCP_LOG_LEVEL` | INFO | No | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `MCP_TRANSPORT` | stdio | No | Transport mode: `stdio` or `http` |
| `MCP_PORT` | 8080 | No* | HTTP port (only used if MCP_TRANSPORT=http) |
| `BLOCKNET_CHAINDIR` | ~/.blocknet/ | No | Path to blockchain data |

*Required if MCP_TRANSPORT=http

## Build Process

Images use a **multi-stage build** to keep runtime images small:

1. **Builder stage** (`python:3.11-slim`):
   - Clones the Blocknet API docs (`blocknet-api-docs`)
   - Installs Python dependencies
   - Runs `python main.py` to generate the MCP server code
   - Output stored in `/build/generated/`

2. **Runtime stage** (`python:3.11-slim`):
   - Creates non-root user `app`
   - Copies generated server from builder stage
   - Installs runtime dependencies
   - Runs the server with `CMD python -m ${SERVER_TYPE}_mcp.main`

The `SERVER_TYPE` build argument (`xbridge` or `xrouter`) determines which server is generated. Both images are built with a single `docker compose build` command.

## How to Test Docker Setup

After `docker compose up -d`, verify everything is working:

1. **Check blocknet-core health**:
   ```bash
   docker compose exec blocknet-core blocknet-cli getblockcount
   ```
   Should return a block height (node is synced).

2. **Test RPC connection from MCP container**:
   ```bash
   docker compose exec xbridge-mcp curl http://localhost:41414/
   ```
   Should return a JSON response (e.g., `{"result":null,"error":null,"id":0}`).

3. **View logs**:
   ```bash
   docker compose logs -f xbridge-mcp
   docker compose logs -f xrouter-mcp
   ```
   Look for "Server started" or any error messages.

4. **Test MCP servers** (if `MCP_TRANSPORT=http`):
   ```bash
   # Test XBridge (port 8081)
   SESSION=$(curl -s -X POST http://localhost:8081/mcp \
     -H "Content-Type: application/json" \
     -H "Accept: application/json, text/event-stream" \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}}' \
     -D - 2>/dev/null | grep -i 'mcp-session-id:' | awk '{print $2}' | tr -d '\r')
   curl -s -X POST http://localhost:8081/mcp \
     -H "Content-Type: application/json" \
     -H "Accept: application/json, text/event-stream" \
     -H "mcp-session-id: $SESSION" \
     -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | head -c 5000
   
   # Test XRouter (port 8082) - replace 8081 with 8082 in the commands above
   ```
   The MCP endpoint is `/mcp` and requires proper session management. The command initializes the connection, retrieves a session ID, then lists available tools. Note that `tools/list` does not require a `params` field in the request body.

If any service fails, check the logs and verify your `.env` configuration.

## Updating Images

When the API documentation or generator code changes:

1. **Rebuild images** (clears cache):
   ```bash
   docker compose build --no-cache
   ```

2. **Update base Blocknet image** (if needed):
   ```bash
   docker compose pull blocknet-core
   ```

3. **Restart services**:
   ```bash
   docker compose up -d
   ```

4. **Clean up old images** (optional):
   ```bash
   docker image prune -f
   ```

## Volume Permissions

The `blocknet-core` container runs as UID/GID 1000:1000 by default (from `docker-compose.yml:5`). If your
`BLOCKNET_CHAINDIR` has different ownership, you may see permission errors.

Fix permissions:

```bash
# Change ownership to match container UID/GID
sudo chown -R 1000:1000 ~/.blocknet/

# Or modify docker-compose.yml to match your user's UID/GID
# environment:
#   - UID=$(id -u)
#   - GID=$(id -g)
```

## Production Deployment

For production environments:

- **Secrets**: Use Docker secrets (Swarm) or an external secret manager (HashiCorp Vault, AWS Secrets Manager) instead of `.env`. Pass secrets via `environment:` or `secrets:`.
- **Resource limits**: Add `mem_limit`, `cpus` in `docker-compose.yml` to prevent resource exhaustion:
  ```yaml
  services:
    xbridge-mcp:
      deploy:
        resources:
          limits:
            cpus: '0.5'
            memory: 512M
  ```
- **Logging**: Set `MCP_LOG_LEVEL=WARNING` or `ERROR` to reduce log volume. Use `docker log` driver with rotation or external log aggregation (ELK, Loki).
- **Networking**: Host mode is simplest but limits isolation. Consider user-defined bridge networks if you need isolation and can configure `RPC_HOST` accordingly (requires code changes).
- **Updates**: Pin image tags (`blocknetdx/blocknet:vX.Y.Z`) instead of `latest`. Test updates in staging first.
- **Monitoring**: Set up health checks for MCP servers (currently only blocknet-core has healthcheck). Consider adding a `/health` endpoint and monitoring ports 8081/8082.

## Transport Mode Configuration

The MCP servers support two transport modes:

- **stdio** (default): Server communicates via stdin/stdout. Suitable for launching as a subprocess.
  ```yaml
  environment:
    - MCP_TRANSPORT=stdio
  ```

- **http**: Server runs as an HTTP service on `MCP_PORT`. Suitable for network-based MCP clients.
  ```yaml
  environment:
    - MCP_TRANSPORT=http
    - MCP_PORT=8081  # XBridge; XRouter uses 8082
  ```

The `docker-compose.yml` already sets `MCP_TRANSPORT=http` for both servers. To switch back to stdio, remove those lines or set to `stdio`.

## Notes

- Generated MCP servers are built inside the Docker image; no need to run `main.py` manually
- The `.env` file is NOT copied into the image; credentials are passed at runtime
- Both MCP servers run as non-root user `app` (UID created in image)
- The blocknet-core data directory persists on the host; no data loss on container removal

---

For general usage instructions, see [README.md](../README.md).

### Override Settings

Create `docker-compose.override.yml` to customize:

```yaml
services:
  xbridge-mcp:
    environment:
      - MCP_LOG_LEVEL=DEBUG
```

Then run:

```bash
docker compose -f docker-compose.yml -f docker-compose.override.yml up -d
```

