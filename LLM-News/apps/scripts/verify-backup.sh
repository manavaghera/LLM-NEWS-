#!/bin/sh
# Verify NewsSense static/cache archives and an optional PostgreSQL dump without touching live data.
set -eu

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
  echo "Usage: verify-backup.sh STATIC_ARCHIVE CACHE_ARCHIVE [POSTGRES_DUMP]" >&2
  exit 2
fi

static_input="$1"
cache_input="$2"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT HUP INT TERM

decrypt() {
  input="$1"
  output="$2"
  case "$input" in
    *.enc)
      if [ -z "${BACKUP_ENCRYPTION_PASSPHRASE:-}" ]; then
        echo "BACKUP_ENCRYPTION_PASSPHRASE is required to verify $input" >&2
        exit 1
      fi
      openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
        -pass env:BACKUP_ENCRYPTION_PASSPHRASE -in "$input" -out "$output"
      ;;
    *) cp "$input" "$output" ;;
  esac
}

decrypt "$static_input" "$work/static.tar.gz"
decrypt "$cache_input" "$work/cache.tar.gz"
BACKUP_VERIFY_WORK_DIR="$work" python "$(dirname "$0")/verify_backup.py" \
  "$work/static.tar.gz" "$work/cache.tar.gz"

if [ "$#" -eq 3 ]; then
  decrypt "$3" "$work/database.dump"
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is required to validate the PostgreSQL custom-format dump." >&2
    exit 1
  fi
  docker run --rm -i postgres:16-alpine pg_restore --list < "$work/database.dump" >/dev/null
  echo "verified PostgreSQL dump"
fi
