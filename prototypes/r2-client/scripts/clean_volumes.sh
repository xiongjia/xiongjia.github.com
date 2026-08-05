#!/usr/bin/env bash
# Remove this prototype's MinIO Docker named volume — where the local test
# objects and buckets actually live (see minio_start.sh).
#
# Usage:
#   pnpm minio:clean-volumes   # recommended
#   bash scripts/clean_volumes.sh # direct
set -euo pipefail

CONTAINER=r2-client-minio
VOLUME=r2-client-minio-data

# Tailored error instead of docker's raw message when the daemon is down —
# otherwise the checks below would just report "none found" and claim success.
if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker is not reachable (is Docker Desktop / the daemon running?)." >&2
  exit 1
fi

# Stop the container first so nothing holds the volume open. The container
# was started with --rm, so stopping it normally removes it — but that
# removal is asynchronous, so force-remove it explicitly first (idempotent;
# errors are ignored when it is already gone).
echo "==> Stopping local MinIO container (if running) ..."
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
  docker stop "${CONTAINER}" >/dev/null
fi
docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true

echo "==> Removing Docker volume (${VOLUME}) ..."
if docker volume ls --format '{{.Name}}' | grep -q "^${VOLUME}$"; then
  docker volume rm -f "${VOLUME}" >/dev/null && echo "    rm ${VOLUME}" \
    || echo "    FAILED: ${VOLUME} (still in use?)"
else
  echo "    none found."
fi

echo "==> Done. Volumes are gone; images are untouched."
