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
    DEFAULT_NEWS_DATA_DIR="/opt/newssense/data/production/static"
    ;;
  staging)
    ENV_FILE="${APP_ROOT}/.env.staging"
    OVERLAY="docker-compose.staging.yml"
    PROJECT="newssense-staging"
    DOMAIN_KEY="STAGING_DOMAIN"
    DEFAULT_NEWS_DATA_DIR="/opt/newssense/data/staging/static"
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

# Keep generated editions outside the Git checkout. This also prevents staging and production
# deployments on the same machine from reading or replacing each other's news.
export NEWS_DATA_DIR="${NEWS_DATA_DIR:-${DEFAULT_NEWS_DATA_DIR}}"
mkdir -p "${NEWS_DATA_DIR}"/{articles,images,audio,resources,summary-video}
legacy_data="${APP_ROOT}/apps/static"
legacy_article=""
current_article="$(find "${NEWS_DATA_DIR}/articles" -type f -name 'group_[0-9]*.json' -print -quit)"
if [[ -d "${legacy_data}/articles" ]]; then
  legacy_article="$(find "${legacy_data}/articles" -type f -name 'group_[0-9]*.json' -print -quit)"
fi
if [[ -z "${current_article}" && -n "${legacy_article}" ]]; then
  cp -a "${legacy_data}/." "${NEWS_DATA_DIR}/"
  echo "Migrated the existing news archive to ${NEWS_DATA_DIR}"
fi
# Directories inherit the host deployment account's group; the updater receives that group as a
# supplemental group and stays non-root inside the container.
find "${NEWS_DATA_DIR}" -type d -exec chmod 2775 {} +
export NEWS_DATA_GID="${NEWS_DATA_GID:-$(stat -c '%g' "${NEWS_DATA_DIR}")}"
catalog_temp="${NEWS_DATA_DIR}/.model_catalog.json.$$"
install -m 0664 "${APP_ROOT}/apps/static/model_catalog.json" "${catalog_temp}"
mv "${catalog_temp}" "${NEWS_DATA_DIR}/model_catalog.json"

cd "${APP_ROOT}/apps"
export APP_ENV_FILE="../$(basename "${ENV_FILE}")"

docker compose -p "${PROJECT}" --env-file "${ENV_FILE}" \
  -f docker-compose.yml -f "${OVERLAY}" --profile updates config --quiet
docker compose -p "${PROJECT}" --env-file "${ENV_FILE}" \
  -f docker-compose.yml -f "${OVERLAY}" --profile updates up -d --build --remove-orphans

# A first edition can take several minutes; allow 30 minutes before declaring deployment failure.
for attempt in {1..360}; do
  if curl --fail --silent --show-error "https://${DOMAIN}/api/health/ready" >/dev/null; then
    "${APP_ROOT}/deployment/smoke-test.sh" "https://${DOMAIN}"
    echo "${ENVIRONMENT} is ready at https://${DOMAIN}"
    exit 0
  fi
  sleep 5
done

echo "Deployment started, but readiness failed at https://${DOMAIN}/api/health/ready" >&2
docker compose -p "${PROJECT}" --env-file "${ENV_FILE}" \
  -f docker-compose.yml -f "${OVERLAY}" --profile updates ps
exit 1
