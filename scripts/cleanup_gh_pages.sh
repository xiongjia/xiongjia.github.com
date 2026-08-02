#!/usr/bin/env bash
#
# cleanup_gh_pages.sh
#
# One-off cleanup: delete the bloated remote `gh-pages` branch (and local refs).
#
# Background: the old CI `deploy-preview` job (peaceiris/actions-gh-pages) pushed
# a full site copy into pr-preview/<PR>/ on every PR push with keep_files: true,
# accumulating ~80 commits / ~86MB of history on gh-pages. The live site is
# served from GitHub Actions artifacts (Pages build_type: "workflow"), NOT from
# the gh-pages branch — so the branch is safe to delete.
#
# Usage:  bash scripts/cleanup_gh_pages.sh
#
# After deletion, unreachable objects are garbage-collected by GitHub within a
# few days; the repo size shown in the UI drops accordingly.

set -euo pipefail

REMOTE="origin"
BRANCH="gh-pages"
SITE_URL="${SITE_URL:-https://xiongjia.github.io/}"

echo "==> Fetching latest refs from ${REMOTE}"
git fetch "${REMOTE}"

if ! git rev-parse --verify "${REMOTE}/${BRANCH}" >/dev/null 2>&1; then
  echo "No remote branch ${BRANCH} found on ${REMOTE}; nothing to do."
  exit 0
fi

# Safety check 1: never delete the branch while it is checked out locally.
if [ "$(git branch --show-current)" = "${BRANCH}" ]; then
  echo "ERROR: you are currently on the ${BRANCH} branch; switch away first." >&2
  exit 1
fi

# Safety check 2: confirm GitHub Pages is served from Actions artifacts, not
# from the gh-pages branch. Deleting the branch would break a branch-served site.
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
  BUILD_TYPE="$(gh api "repos/${REPO}/pages" -q .build_type 2>/dev/null || echo "unknown")"
  echo "==> GitHub Pages build_type: ${BUILD_TYPE}"
  if [ "${BUILD_TYPE}" != "workflow" ]; then
    echo "ERROR: Pages build_type is '${BUILD_TYPE}', not 'workflow'." >&2
    echo "       The site may be served from the ${BRANCH} branch — do NOT delete it." >&2
    exit 1
  fi
else
  echo "WARNING: 'gh' CLI not available/authenticated; skipping Pages source check."
  echo "         Confirm in repo Settings -> Pages -> Source = 'GitHub Actions' first."
  read -r -p "Continue anyway? [y/N] " ans
  [[ "${ans}" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 1; }
fi

# Final confirmation (destructive!)
echo
echo "This will DELETE the remote branch ${REMOTE}/${BRANCH} and all its history."
read -r -p "Type 'delete' to confirm: " ans
[[ "${ans}" == "delete" ]] || { echo "Aborted."; exit 1; }

echo "==> Deleting remote branch ${REMOTE}/${BRANCH}"
git push "${REMOTE}" --delete "${BRANCH}"

echo "==> Pruning local refs"
git branch -D "${BRANCH}" >/dev/null 2>&1 || true
git fetch --prune "${REMOTE}"

echo "==> Verifying live site is still up"
code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "${SITE_URL}" || echo 'failed')"
if [ "${code}" = "200" ]; then
  echo "OK: ${SITE_URL} -> ${code}"
  echo "Done. Unreachable objects will be GC'd by GitHub within a few days."
else
  echo "WARNING: ${SITE_URL} returned ${code} — site may need attention (unrelated to branch deletion)."
fi
