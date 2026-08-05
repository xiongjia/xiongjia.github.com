#!/usr/bin/env bash
# Apply the RLS policies the local Storage demo needs (anon key: create/list
# buckets, upload/download/update/delete objects).
#
# Why: current Storage versions ship NO policies by default — RLS then denies
# every non-service_role request (official docs: "By default Storage does not
# allow any uploads to buckets without RLS policies"). The demo uses the anon
# key, so these policies must exist after every fresh `supabase start`.
#
# Idempotent (drop + create), safe to re-run anytime.
#
# Usage:
#   pnpm supabase:setup-storage   # recommended
#   bash scripts/setup_storage_rls.sh
set -euo pipefail

DB_CONTAINER="supabase_db_supabase-storage-client"
DB_USER="postgres"
DB_NAME="postgres"

# Friendly failure instead of a raw `docker exec` error when the stack
# (and thus the DB container) isn't running.
if [ "$(docker container inspect -f '{{.State.Running}}' "$DB_CONTAINER" 2>/dev/null)" != "true" ]; then
  echo "==> ERROR: local Supabase stack is not running (container '$DB_CONTAINER' missing or stopped)." >&2
  echo "    Start it first with: pnpm supabase:start" >&2
  exit 1
fi

docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 <<'SQL'
drop policy if exists "Storage Allow Insert buckets" on storage.buckets;
drop policy if exists "Storage Allow Select buckets" on storage.buckets;
drop policy if exists "Storage Allow Delete buckets" on storage.buckets;
drop policy if exists "Storage Allow Insert objects" on storage.objects;
drop policy if exists "Storage Allow Select objects" on storage.objects;
drop policy if exists "Storage Allow Update objects" on storage.objects;
drop policy if exists "Storage Allow Delete objects" on storage.objects;

create policy "Storage Allow Insert buckets" on storage.buckets
  for insert to anon, authenticated, service_role, supabase_storage_admin
  with check (true);
create policy "Storage Allow Select buckets" on storage.buckets
  for select to anon, authenticated, service_role, supabase_storage_admin
  using (true);
create policy "Storage Allow Delete buckets" on storage.buckets
  for delete to anon, authenticated, service_role, supabase_storage_admin
  using (true);

create policy "Storage Allow Insert objects" on storage.objects
  for insert to anon, authenticated, service_role, supabase_storage_admin
  with check (true);
create policy "Storage Allow Select objects" on storage.objects
  for select to anon, authenticated, service_role, supabase_storage_admin
  using (true);
create policy "Storage Allow Update objects" on storage.objects
  for update to anon, authenticated, service_role, supabase_storage_admin
  using (true);
create policy "Storage Allow Delete objects" on storage.objects
  for delete to anon, authenticated, service_role, supabase_storage_admin
  using (true);
SQL

echo "==> Storage RLS policies applied (anon can manage demo buckets/objects)."
