"""Durable S3-compatible storage for published editions and generated media.

The updater uploads content before replacing the remote manifest. A new deployment pulls
only manifest-listed files into its writable news directory before the backend becomes ready.
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


MANIFEST_VERSION = 1


def configured() -> bool:
    return bool(os.getenv("OBJECT_STORAGE_BUCKET", "").strip())


def _prefix() -> str:
    return os.getenv("OBJECT_STORAGE_PREFIX", "news").strip("/")


def _key(relative: str) -> str:
    prefix = _prefix()
    return f"{prefix}/{relative}" if prefix else relative


def _client():
    try:
        import boto3
    except ImportError as exc:  # pragma: no cover - container dependency check
        raise RuntimeError("Object storage requires boto3") from exc
    options = {
        "service_name": "s3",
        "region_name": os.getenv("OBJECT_STORAGE_REGION") or "auto",
    }
    endpoint = os.getenv("OBJECT_STORAGE_ENDPOINT", "").strip()
    if endpoint:
        options["endpoint_url"] = endpoint
    access_key = os.getenv("OBJECT_STORAGE_ACCESS_KEY_ID", "").strip()
    secret_key = os.getenv("OBJECT_STORAGE_SECRET_ACCESS_KEY", "").strip()
    if access_key:
        options["aws_access_key_id"] = access_key
    if secret_key:
        options["aws_secret_access_key"] = secret_key
    return boto3.client(**options)


def _digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def _published_files(root: Path):
    for path in sorted(root.rglob("*")):
        if (path.is_file() and not path.is_symlink() and not path.name.startswith(".")
                and path.name != "object-storage-manifest.json"):
            relative = path.relative_to(root).as_posix()
            if all(part not in {"..", ""} for part in PurePosixPath(relative).parts):
                yield path, relative


def push(root: Path, client=None) -> int:
    """Upload changed files and atomically publish a new manifest. Returns uploaded file count."""
    if not configured():
        return 0
    root = root.resolve()
    if not root.is_dir():
        raise RuntimeError(f"News directory does not exist: {root}")
    storage = client or _client()
    bucket = os.environ["OBJECT_STORAGE_BUCKET"].strip()
    entries, uploaded = [], 0
    for path, relative in _published_files(root):
        checksum = _digest(path)
        entry = {"path": relative, "size": path.stat().st_size, "sha256": checksum}
        entries.append(entry)
        remote_key = _key(relative)
        unchanged = False
        try:
            saved = storage.head_object(Bucket=bucket, Key=remote_key)
            unchanged = saved.get("Metadata", {}).get("sha256") == checksum
        except Exception as exc:
            code = str(getattr(exc, "response", {}).get("Error", {}).get("Code", ""))
            if code not in {"404", "NoSuchKey", "NotFound"}:
                raise
        if unchanged:
            continue
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        storage.upload_file(
            str(path), bucket, remote_key,
            ExtraArgs={"ContentType": content_type, "CacheControl": "public,max-age=3600",
                       "Metadata": {"sha256": checksum}},
        )
        uploaded += 1

    manifest = {
        "version": MANIFEST_VERSION,
        "published_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": entries,
    }
    storage.put_object(
        Bucket=bucket, Key=_key("manifest.json"),
        Body=json.dumps(manifest, separators=(",", ":")).encode(),
        ContentType="application/json", CacheControl="no-cache",
    )
    return uploaded


def _safe_destination(root: Path, relative: str) -> Path:
    candidate = PurePosixPath(relative)
    if candidate.is_absolute() or not candidate.parts or any(part in {"", ".", ".."} for part in candidate.parts):
        raise RuntimeError(f"Unsafe object-storage path: {relative}")
    destination = (root / Path(*candidate.parts)).resolve()
    if not destination.is_relative_to(root.resolve()):
        raise RuntimeError(f"Unsafe object-storage path: {relative}")
    return destination


def pull(root: Path, client=None) -> int:
    """Restore changed manifest-listed files using verified temporary downloads."""
    if not configured():
        return 0
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    storage = client or _client()
    bucket = os.environ["OBJECT_STORAGE_BUCKET"].strip()
    response = storage.get_object(Bucket=bucket, Key=_key("manifest.json"))
    try:
        manifest = json.loads(response["Body"].read())
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("Object-storage manifest is invalid") from exc
    if manifest.get("version") != MANIFEST_VERSION or not isinstance(manifest.get("files"), list):
        raise RuntimeError("Object-storage manifest version is unsupported")

    restored = 0
    for entry in manifest["files"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise RuntimeError("Object-storage manifest contains an invalid file")
        expected_hash = entry.get("sha256")
        expected_size = entry.get("size")
        if not isinstance(expected_hash, str) or len(expected_hash) != 64 or type(expected_size) is not int:
            raise RuntimeError("Object-storage manifest contains invalid integrity data")
        destination = _safe_destination(root, entry["path"])
        if destination.is_file() and destination.stat().st_size == expected_size and _digest(destination) == expected_hash:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
        os.close(handle)
        temporary = Path(temporary_name)
        try:
            storage.download_file(bucket, _key(entry["path"]), str(temporary))
            if temporary.stat().st_size != expected_size or _digest(temporary) != expected_hash:
                raise RuntimeError(f"Object-storage integrity check failed: {entry['path']}")
            os.replace(temporary, destination)
            restored += 1
        finally:
            temporary.unlink(missing_ok=True)
    return restored


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("push", "pull"))
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    count = push(args.root) if args.operation == "push" else pull(args.root)
    print(f"object storage {args.operation}: {count} files changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
