"""Create a named administrator or reset its password from a trusted server shell."""
from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.admin_accounts import create_user, new_totp_secret, reset_password  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("create", "reset-password"))
    parser.add_argument("username")
    parser.add_argument("--role", choices=("owner", "editor", "viewer"), default="owner")
    parser.add_argument("--with-mfa", action="store_true")
    args = parser.parse_args()
    password = os.getenv("ADMIN_NEW_PASSWORD") or getpass.getpass("New password: ")
    confirmation = os.getenv("ADMIN_NEW_PASSWORD") or getpass.getpass("Repeat password: ")
    if password != confirmation:
        print("Passwords do not match.", file=sys.stderr)
        return 2
    if args.operation == "reset-password":
        reset_password(args.username, password)
        print(f"Password reset and existing sessions revoked for {args.username}.")
        return 0
    secret = new_totp_secret() if args.with_mfa else ""
    create_user(args.username, password, args.role, secret)
    print(f"Created {args.role} account: {args.username}")
    if secret:
        issuer = quote("NewsSense")
        label = quote(f"NewsSense:{args.username}")
        print(f"TOTP secret (save now): {secret}")
        print(f"Authenticator URI: otpauth://totp/{label}?secret={secret}&issuer={issuer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
