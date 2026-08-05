#!/usr/bin/env bash
# Remove the Supabase stack's Docker images (dangling leftovers + stack
# images: `supabase/*` and `public.ecr.aws/supabase/*`).
# The next `supabase start` re-pulls them, i.e. a fresh first run.
#
# Usage:
#   pnpm supabase:clean-images   # recommended
#   bash scripts/clean_images.sh # direct
set -euo pipefail

# Stop the stack first — running containers hold their images in use and
# would make the removal fail. Ignore errors when nothing is running.
echo "==> Stopping local Supabase stack (if running) ..."
pnpm exec supabase stop 2>/dev/null || true

echo "==> Pruning dangling images ..."
docker image prune -f

IMAGES=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep -iE '/?supabase/' | sort -u || true)
if [ -z "$IMAGES" ]; then
  echo "==> No supabase stack images to remove."
else
  echo "==> Removing supabase stack images ..."
  for img in $IMAGES; do
    echo "    rmi $img"
    docker rmi -f "$img" >/dev/null 2>&1 || true
  done
fi

echo "==> Done. Images are gone; volumes are untouched."
