#!/bin/bash
# Deploy Kxmeleon ERP — pull, restart containers, sync static files.
#
# Usage:
#   ./scripts/deploy.sh          # Full deploy
#   ./scripts/deploy.sh --quick  # Skip pull, just restart + sync

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Kxmeleon ERP Deploy ==="
echo "Project: $PROJECT_DIR"
echo ""

# Step 1: Pull latest code (unless --quick)
if [[ "${1:-}" != "--quick" ]]; then
    echo "→ Pulling latest code..."
    cd "$PROJECT_DIR"
    git pull --rebase
    echo ""
fi

# Step 2: Restart app container (stop+start for preload_app reload)
echo "→ Restarting app container..."
docker stop dotmac_erp_app
docker start dotmac_erp_app

# Step 3: Wait for health check
echo "→ Waiting for health check..."
for i in $(seq 1 60); do
    if curl -sf http://localhost:8003/health > /dev/null 2>&1; then
        echo "  App healthy after ${i}s"
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "  ERROR: App not healthy after 60s!"
        docker logs dotmac_erp_app --tail 20
        exit 1
    fi
    sleep 1
done

# Step 4: Sync static files to Nginx
echo "→ Syncing static files to Nginx..."
"$SCRIPT_DIR/sync-static.sh"

# Step 5: Restart worker + beat
echo "→ Restarting worker and beat..."
docker restart dotmac_erp_worker dotmac_erp_beat

echo ""
echo "=== Deploy complete ==="
echo "Verify: https://erp.dotmac.io/health"
