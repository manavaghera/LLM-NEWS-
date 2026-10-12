#!/bin/sh
# Verify a NewsSense static archive and cache archive without touching the live deployment.
set -eu

if [ "$#" -ne 2 ]; then
  echo "Usage: verify-backup.sh STATIC_ARCHIVE CACHE_ARCHIVE" >&2
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
