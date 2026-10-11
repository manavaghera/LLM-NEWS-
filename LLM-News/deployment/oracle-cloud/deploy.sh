#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT="${1:-}"
REPOSITORY_ROOT="${NEWSSENSE_REPOSITORY_ROOT:-/opt/newssense/repo}"
APP_ROOT="${REPOSITORY_ROOT}/LLM-News"

case "${ENVIRONMENT}" in
  production)
    ENV_FILE="${APP_ROOT}/.env.production"
    OVERLAY="docker-compose.prod.yml"
    PROJECT="newssense-production"
    DOMAIN_KEY="DOMAIN"
    ;;
  staging)
    ENV_FILE="${APP_ROOT}/.env.staging"
    OVERLAY="docker-compose.staging.yml"
    PROJECT="newssense-staging"
    DOMAIN_KEY="STAGING_DOMAIN"
    ;;
  *)
    echo "Usage: newssense-deploy production|staging" >&2
    exit 2
    ;;
esac

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing secret file: ${ENV_FILE}" >&2
  exit 1
fi

DOMAIN="$(sed -n "s/^${DOMAIN_KEY}=//p" "${ENV_FILE}" | tail -n 1 | tr -d '\r')"
if [[ -z "${DOMAIN}" ]]; then
  echo "${DOMAIN_KEY} is missing in ${ENV_FILE}" >&2
  exit 1
fi

cd "${APP_ROOT}/apps"
export APP_ENV_FILE="../$(basename "${ENV_FILE}")"

docker compose -p "${PROJECT}" --env-file "${ENV_FILE}" \
  -f docker-compose.yml -f "${OVERLAY}" --profile updates config --quiet
docker compose -p "${PROJECT}" --env-file "${ENV_FILE}" \
  -f docker-compose.yml -f "${OVERLAY}" --profile updates up -d --build --remove-orphans

for attempt in {1..24}; do
  if curl --fail --silent --show-error "https://${DOMAIN}/api/health/ready" >/dev/null; then
    echo "${ENVIRONMENT} is ready at https://${DOMAIN}"
    exit 0
  fi
  sleep 5
done

echo "Deployment started, but readiness failed at https://${DOMAIN}/api/health/ready" >&2
docker compose -p "${PROJECT}" --env-file "${ENV_FILE}" \
  -f docker-compose.yml -f "${OVERLAY}" --profile updates ps
exit 1
