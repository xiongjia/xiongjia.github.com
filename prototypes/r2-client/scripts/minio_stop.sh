#!/usr/bin/env bash
# Stop (and remove, --rm) the local MinIO container started by minio_start.sh.
# The named Docker volume `r2-client-minio-data` is kept — wipe it with
# `pnpm minio:clean-volumes` if you want a clean slate.
set -euo pipefail

CONTAINER=r2-client-minio

# Tailored error instead of docker's raw message when the daemon is down.
if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker is not reachable (is Docker Desktop / the daemon running?)." >&2
  exit 1
fi

if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
  docker stop "${CONTAINER}"
  echo "MinIO container '${CONTAINER}' stopped and removed (data volume kept)"
else
  echo "No running '${CONTAINER}' container"
fi
