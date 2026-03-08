# Docker Deployment Guide

This directory contains Docker configuration to run Blocknet MCP servers with a local Blocknet core node.

## Files

- `Dockerfile` - Multi-stage build that generates and runs MCP servers
- `docker-compose.yml` - Orchestrates blocknet-core, xbridge-mcp, xrouter-mcp
- `.dockerignore` - Excludes unnecessary files from build context

## Prerequisites

1. **Docker** and **Docker Compose** installed
2. **Blocknet blockchain data** at `/mnt/nvme/chains/blocknet_x3` (or modify the volume path)
3. RPC credentials (username/password) for the Blocknet node

## Quick Start

1. Set RPC credentials in environment or `.env` file:

```bash
# Create .env file
cp 
EOF
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

Make sure your blocknet.conf (mounted at `/opt/blockchain/config/blocknet.conf`) contains matching RPC settings:

```
rpcuser=${RPC_USER}
rpcpassword=${RPC_PASSWORD}
rpcport=41414
server=1
```

### MCP Server Settings

Configurable via environment variables in `docker-compose.yml`:

- `RPC_HOST` - Default: `localhost` (uses host network)
- `RPC_PORT` - Default: `41414`
- `MCP_ALLOW_WRITE` - Default: `false` (set to `true` to enable write operations)
- `MCP_LOG_LEVEL` - Default: `INFO` (DEBUG, INFO, WARNING, ERROR)

### Volumes

The `blocknet-core` service mounts your existing blockchain data:

```yaml
volumes:
  - /mnt/nvme/chains/blocknet_x3:/opt/blockchain
```

Modify this path if your data is elsewhere.

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

Ensure the Docker container has read/write access to `/mnt/nvme/chains/blocknet_x3`. The Blocknet image expects to write to this directory.

### Port already in use

With `network_mode: host`, services bind directly to host ports. Make sure port 41414 is not used by another process:

```bash
sudo lsof -i :41414
```

## Images

- `blocknetdx/blocknet:latest` - Official Blocknet Core node
- `xbridge-mcp:test` / `xrouter-mcp:test` - Built from local Dockerfile

## Advanced Usage

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

### Production Deployment

For production:

1. Use specific image tags instead of `latest`
2. Set `MCP_ALLOW_WRITE=false` unless write operations are needed
3. Configure log rotation appropriately
4. Use a secret manager for RPC credentials instead of `.env`
5. Consider using a private registry for custom images

## Notes

- Generated MCP servers are built inside the Docker image; no need to run `main.py` manually
- The `.env` file is NOT copied into the image; credentials are passed at runtime
- Both MCP servers run as non-root user `app` (UID created in image)
- The blocknet-core data directory persists on the host; no data loss on container removal
