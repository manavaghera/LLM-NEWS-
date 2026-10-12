#!/usr/bin/env bash
set -euo pipefail

# Prepare a fresh Ubuntu 24.04 Oracle Cloud VM for NewsSense.
# Run as root: sudo bash bootstrap.sh [repository-url] [branch] [production|staging]

REPOSITORY_URL="${1:-https://github.com/manavaghera/LLM-NEWS-.git}"
DEPLOY_BRANCH="${2:-feature/newssense-rebuild}"
TARGET_ENVIRONMENT="${3:-production}"
DEPLOY_ROOT="/opt/newssense"
DEPLOY_USER="newssense"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script with sudo." >&2
  exit 1
fi

case "${TARGET_ENVIRONMENT}" in
  production|staging) ;;
  *) echo "Environment must be production or staging." >&2; exit 2 ;;
esac

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  ca-certificates curl git docker.io docker-compose-v2 unattended-upgrades

systemctl enable --now docker

if ! id "${DEPLOY_USER}" >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash "${DEPLOY_USER}"
fi
usermod -aG docker "${DEPLOY_USER}"
install -d -o "${DEPLOY_USER}" -g "${DEPLOY_USER}" "${DEPLOY_ROOT}"
install -d -o "${DEPLOY_USER}" -g "${DEPLOY_USER}" \
  "${DEPLOY_ROOT}/data" "${DEPLOY_ROOT}/data/${TARGET_ENVIRONMENT}" \
  "${DEPLOY_ROOT}/data/${TARGET_ENVIRONMENT}/static"

# Reuse the VM creator's authorized SSH keys for the restricted deployment account.
SOURCE_USER="${SUDO_USER:-root}"
SOURCE_HOME="$(getent passwd "${SOURCE_USER}" | cut -d: -f6)"
if [[ -f "${SOURCE_HOME}/.ssh/authorized_keys" ]]; then
  install -d -m 0700 -o "${DEPLOY_USER}" -g "${DEPLOY_USER}" "/home/${DEPLOY_USER}/.ssh"
  install -m 0600 -o "${DEPLOY_USER}" -g "${DEPLOY_USER}" \
    "${SOURCE_HOME}/.ssh/authorized_keys" "/home/${DEPLOY_USER}/.ssh/authorized_keys"
fi

if [[ ! -d "${DEPLOY_ROOT}/repo/.git" ]]; then
  sudo -u "${DEPLOY_USER}" git clone --branch "${DEPLOY_BRANCH}" --single-branch \
    "${REPOSITORY_URL}" "${DEPLOY_ROOT}/repo"
else
  sudo -u "${DEPLOY_USER}" git -C "${DEPLOY_ROOT}/repo" fetch origin "${DEPLOY_BRANCH}"
  sudo -u "${DEPLOY_USER}" git -C "${DEPLOY_ROOT}/repo" checkout "${DEPLOY_BRANCH}"
  sudo -u "${DEPLOY_USER}" git -C "${DEPLOY_ROOT}/repo" pull --ff-only origin "${DEPLOY_BRANCH}"
fi

chmod 0755 "${DEPLOY_ROOT}/repo/LLM-News/deployment/oracle-cloud/deploy.sh"
ln -sfn "${DEPLOY_ROOT}/repo/LLM-News/deployment/oracle-cloud/deploy.sh" /usr/local/bin/newssense-deploy

cat >/etc/cron.d/newssense-backup <<'CRON'
17 2 * * * newssense cd /opt/newssense/repo/LLM-News/apps && BACKUP_ENV_FILE=/opt/newssense/backup.env ./scripts/backup.sh /opt/newssense/backups __TARGET_ENVIRONMENT__ >/tmp/newssense-backup.log 2>&1
CRON
sed -i "s/__TARGET_ENVIRONMENT__/${TARGET_ENVIRONMENT}/" /etc/cron.d/newssense-backup
chmod 0644 /etc/cron.d/newssense-backup
install -d -o "${DEPLOY_USER}" -g "${DEPLOY_USER}" "${DEPLOY_ROOT}/backups"
if [[ ! -e "${DEPLOY_ROOT}/backup.env" ]]; then
  install -m 0600 -o "${DEPLOY_USER}" -g "${DEPLOY_USER}" /dev/null "${DEPLOY_ROOT}/backup.env"
fi

echo
echo "Server ready. Next:"
echo "  1. Create ${DEPLOY_ROOT}/repo/LLM-News/.env.production (or .env.staging)."
echo "  2. Run: sudo -u ${DEPLOY_USER} newssense-deploy ${TARGET_ENVIRONMENT}"
echo "  3. Open TCP ports 22, 80 and 443 in the Oracle subnet security list."
