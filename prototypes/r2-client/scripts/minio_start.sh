#!/usr/bin/env bash
# Start a local MinIO server (S3-compatible) for testing this prototype
# without a Cloudflare account. R2 exposes the same S3 API, so the demo runs
# unchanged — just point it at this endpoint (see README → Local test).
#
# Data lives in the named Docker volume `r2-client-minio-data` and survives
# `minio:stop`; wipe it with `minio:clean-volumes`.
set -euo pipefail
cd "$(dirname "$0")/.."

CONTAINER=r2-client-minio
VOLUME=r2-client-minio-data

# Tailored error instead of docker's raw message when the daemon is down.
if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker is not reachable (is Docker Desktop / the daemon running?)." >&2
  exit 1
fi

# Already-running detection checks the image too, so a foreign container that
# happens to use this name is not mistaken for our MinIO instance.
if docker ps --format '{{.Names}} {{.Image}}' | grep -q "^${CONTAINER} minio/minio"; then
  echo "MinIO container '${CONTAINER}' is already running"
  echo "  S3 API:   http://127.0.0.1:9000"
  echo "  Console:  http://127.0.0.1:9001 (minioadmin / minioadmin)"
  exit 0
fi

# A container with this name exists but is not a running minio/minio (e.g. a
# foreign service squatting on the name) — fail loudly instead of claiming
# success or leaving `docker run` to die on a name clash.
if docker ps -a --format '{{.Names}} {{.Image}} {{.Status}}' | grep -q "^${CONTAINER} "; then
  echo "ERROR: container '${CONTAINER}' exists but is not a running minio/minio:" >&2
  docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' | grep -E "^(NAMES|${CONTAINER} )" >&2
  echo "Rename or remove it, then re-run; or change CONTAINER in this script." >&2
  exit 1
fi

# Local dev only: bind to loopback so the S3 API / console (default creds
# minioadmin) are not exposed on the LAN.
docker run --rm -d \
  --name "${CONTAINER}" \
  -v "${VOLUME}:/data" \
  -p 127.0.0.1:9000:9000 \
  -p 127.0.0.1:9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address :9001

# Wait until MinIO answers its health endpoint — the first run also has to
# pull the image, so the container can take a while to come up (and the demo
# would otherwise race it).
echo "Waiting for MinIO to be ready ..."
for i in $(seq 1 60); do
  if curl -sf http://127.0.0.1:9000/minio/health/live >/dev/null 2>&1; then
    echo "  ready after ${i}s"
    break
  fi
  if [ "$i" -eq 60 ]; then
    echo "ERROR: MinIO did not become ready in 60s (see: docker logs ${CONTAINER})" >&2
    exit 1
  fi
  sleep 1
done

echo "MinIO started:"
echo "  S3 API:   http://127.0.0.1:9000"
echo "  Console:  http://127.0.0.1:9001 (minioadmin / minioadmin)"
echo "  Data:     Docker volume '${VOLUME}' (persists across restarts; wipe with pnpm minio:clean-volumes)"
echo "Demo config (see .env.dev.local or README → Local test):"
echo "  R2_ENDPOINT=http://127.0.0.1:9000  R2_FORCE_PATH_STYLE=true  R2_REGION=us-east-1"
