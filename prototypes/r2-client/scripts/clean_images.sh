#!/usr/bin/env bash
# Remove the MinIO test image (and dangling leftovers). The next
# `minio:start` re-pulls it, i.e. a fresh first run.
#
# Usage:
#   pnpm minio:clean-images   # recommended
#   bash scripts/clean_images.sh # direct
set -euo pipefail

CONTAINER=r2-client-minio

# Tailored error instead of docker's raw message when the daemon is down —
# otherwise the checks below would just report "no images" and claim success.
if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker is not reachable (is Docker Desktop / the daemon running?)." >&2
  exit 1
fi

# Stop the container first — a running container holds its image in use and
# would make the removal fail. Force-remove it explicitly (the container was
# started with --rm; the automatic removal after stop is asynchronous, and a
# force-remove is idempotent when it is already gone).
echo "==> Stopping local MinIO container (if running) ..."
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
  docker stop "${CONTAINER}" >/dev/null
fi
docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true

echo "==> Pruning dangling images ..."
docker image prune -f

IMAGES=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep -E '^minio/minio' | sort -u || true)
if [ -z "$IMAGES" ]; then
  echo "==> No minio images to remove."
else
  echo "==> Removing minio images ..."
  for img in $IMAGES; do
    echo "    rmi $img"
    docker rmi -f "$img" >/dev/null 2>&1 || true
  done
fi

echo "==> Done. Images are gone; volumes are untouched."
