#!/usr/bin/env bash
# Remove this Supabase project's Docker named volumes
# (where Storage objects and Postgres data actually live).
#
# Usage:
#   pnpm supabase:clean-volumes   # recommended
#   bash scripts/clean_volumes.sh # direct
set -euo pipefail

PROJECT_ID="supabase-storage-client"

# Stop the stack first so no container holds a volume open — ignore
# errors when it isn't running.
echo "==> Stopping local Supabase stack (if running) ..."
pnpm exec supabase stop 2>/dev/null || true

echo "==> Removing project Docker volumes (supabase_*_${PROJECT_ID}) ..."
VOLUMES=$(docker volume ls --format '{{.Name}}' | grep -E "^supabase_.*_${PROJECT_ID}$" || true)
if [ -z "$VOLUMES" ]; then
  echo "    none found."
else
  for v in $VOLUMES; do
    echo "    rm $v"
    docker volume rm -f "$v" >/dev/null || echo "    FAILED: $v (still in use?)"
  done
fi

echo "==> Done. Volumes are gone; images are untouched."
