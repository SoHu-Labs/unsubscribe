#!/usr/bin/env bash
# Example wrapper for cron or launchd. Copy beside your real job, chmod +x, set env vars.
#
# Required: GOOGLE_OAUTH_TOKEN (path to Gmail OAuth JSON with gmail.readonly + gmail.send if emailing).
# Optional: DIGEST_REPO, UNSUBSCRIBE_KEEP, DIGEST_CACHE_DB, DEEPSEEK_API_KEY (or opencode auth file per README).
set -euo pipefail

REPO="${DIGEST_REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$REPO"

: "${GOOGLE_OAUTH_TOKEN:?set GOOGLE_OAUTH_TOKEN to your OAuth JSON path}"

KEEP="${UNSUBSCRIBE_KEEP:-$HOME/.unsubscribe_keep.json}"
CACHE="${DIGEST_CACHE_DB:-$REPO/cache/digest.sqlite}"

exec mamba run -n email-digest python -m email_digest digest run --all --strict \
  --topics-dir "$REPO/topics" \
  --keep-list "$KEEP" \
  --cache-db "$CACHE"
