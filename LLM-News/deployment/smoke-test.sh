#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-}"
if [[ ! "${BASE_URL}" =~ ^https:// ]]; then
  echo "Usage: smoke-test.sh https://staging.example.com" >&2
  exit 2
fi
BASE_URL="${BASE_URL%/}"

ready="$(curl --fail --silent --show-error --max-time 20 "${BASE_URL}/api/health/ready")"
grep -Eq '"status"[[:space:]]*:[[:space:]]*"ready"' <<<"${ready}" || {
  echo "Readiness response is not ready." >&2
  exit 1
}

for path in / /robots.txt /sitemap.xml /feed.xml; do
  curl --fail --silent --show-error --max-time 20 --output /dev/null "${BASE_URL}${path}"
done

headers="$(curl --fail --silent --show-error --head --max-time 20 "${BASE_URL}/")"
grep -Eqi '^strict-transport-security:' <<<"${headers}" || { echo "Missing HSTS header." >&2; exit 1; }
grep -Eqi '^x-content-type-options:[[:space:]]*nosniff' <<<"${headers}" || { echo "Missing nosniff header." >&2; exit 1; }
grep -Eqi '^content-security-policy:' <<<"${headers}" || { echo "Missing Content-Security-Policy header." >&2; exit 1; }

echo "Smoke checks passed for ${BASE_URL}"
