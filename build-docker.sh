#!/usr/bin/env bash
#
# Blocknet MCP Docker Deployment Script
#
# Builds and deploys Blocknet MCP servers via Docker.
# Modular: select which services to deploy.
#
# Usage:
#   ./build-docker.sh [options]
#
# Options:
#   --core         Deploy blocknet-core node
#   --xbridge      Deploy XBridge MCP server
#   --xrouter      Deploy XRouter MCP server
#   --all          Deploy all services (default)
#   --build        Build images without starting containers
#   --up           Build and start containers
#   --down         Stop and remove containers
#   --logs         View logs (use --follow for tail)
#   --help         Show this help
#
# Examples:
#   ./build-docker.sh --all --up              # Build and start all
#   ./build-docker.sh --xbridge --up         # Only XBridge
#   ./build-docker.sh --core --xbridge --up  # Core + XBridge
#   ./build-docker.sh --build                # Build only
#   ./build-docker.sh --down                 # Stop all

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Default: build all but don't start
SERVICES=()
ACTION=""

show_help() {
	sed -n '1,28p' "$0"
	exit 0
}

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Parse arguments
while [[ $# -gt 0 ]]; do
	case $1 in
	--core)
		SERVICES+=("blocknet-core")
		shift
		;;
	--xbridge)
		SERVICES+=("xbridge-mcp")
		shift
		;;
	--xrouter)
		SERVICES+=("xrouter-mcp")
		shift
		;;
	--all)
		SERVICES=("blocknet-core" "xbridge-mcp" "xrouter-mcp")
		shift
		;;
	--build)
		ACTION="build"
		shift
		;;
	--up)
		ACTION="up"
		shift
		;;
	--down)
		ACTION="down"
		shift
		;;
	--logs)
		ACTION="logs"
		shift
		;;
	--follow | -f)
		FOLLOW="yes"
		shift
		;;
	--help | -h)
		show_help
		;;
	*)
		log_error "Unknown option: $1"
		show_help
		;;
	esac
done

# Default to all services if none specified
if [[ ${#SERVICES[@]} -eq 0 ]]; then
	SERVICES=("blocknet-core" "xbridge-mcp" "xrouter-mcp")
fi

# Default action
if [[ -z "$ACTION" ]]; then
	ACTION="build"
fi

log_info "Docker Compose Project: blocknet-mcp"
log_info "Services: ${SERVICES[*]}"
log_info "Action: $ACTION"

# Check .env file
if [[ ! -f ".env" ]]; then
	log_warn ".env not found!"
	echo "Please copy config/.env.example to .env and configure:"
	echo "  cp config/.env.example .env"
	echo "  # Edit .env with your RPC credentials"
	exit 1
fi

cd docker

# Use --env-file to point to .env in parent directory
ENV_FILE="../.env"

case "$ACTION" in
build)
	log_info "Building Docker images..."
	docker compose --env-file "$ENV_FILE" build "${SERVICES[@]}"
	log_info "Build complete!"
	;;
up)
	log_info "Building and starting containers..."
	docker compose --env-file "$ENV_FILE" up --build -d "${SERVICES[@]}" --remove-orphans
	log_info "Containers started:"
	for svc in "${SERVICES[@]}"; do
		echo "  - $svc"
	done
	echo
	echo "View logs: ./build-docker.sh --logs"
	echo "Stop: ./build-docker.sh --down"
	;;
down)
	log_info "Stopping containers..."
	docker compose --env-file "$ENV_FILE" down --remove-orphans "${SERVICES[@]}"
	log_info "Containers stopped."
	;;
logs)
	FOLLOW_FLAG=""
	if [[ "${FOLLOW:-}" == "yes" ]]; then
		FOLLOW_FLAG="-f"
	fi
	docker compose --env-file "$ENV_FILE" logs --tail=50 $FOLLOW_FLAG "${SERVICES[@]}"
	;;
*)
	log_error "Unknown action: $ACTION"
	exit 1
	;;
esac
