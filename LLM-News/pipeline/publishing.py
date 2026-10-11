"""Build an edition off-site, then replace its media and articles with rollback on failure."""
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path


def signature(folder):
    return sorted((str(p.relative_to(folder)), p.stat().st_mtime_ns, p.stat().st_size)
                  for p in folder.rglob("*") if p.is_file()) if folder.exists() else []


@contextmanager
def publication_lock(folder):
    """Serialize publication across updater processes; an OS lock is released even after a crash."""
    with (folder.parent / f".{folder.name}.publish.lock").open("a+b") as lock:
        lock.seek(0, os.SEEK_END)
        if not lock.tell():
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            lock.seek(0)
            if os.name == "nt":
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


class EditionWriter:
    def __init__(self, articles: Path, images: Path, audio: Path, append=False):
        self.targets = {"images": images.resolve(), "audio": audio.resolve(), "articles": articles.resolve()}
        self.append = append
        self._keep_backup = False

    def __enter__(self):
        parent = self.targets["articles"].parent
        parent.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix=".edition-", dir=parent)).resolve()
        try:
            with publication_lock(self.targets["articles"]):
                self.original = {name: signature(path) for name, path in self.targets.items()}
                self._stage()
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def _stage(self):
        for name, target in self.targets.items():
            staged = self.root / name
            if self.append and target.exists():
                shutil.copytree(target, staged)
            else:
                staged.mkdir()
            setattr(self, name, staged)

    def commit(self):
        with publication_lock(self.targets["articles"]):
            self._commit()

    def _commit(self):
        if any(signature(path) != self.original[name] for name, path in self.targets.items()):
            raise RuntimeError("The edition changed during generation; retry without overwriting the newer news")
        changed = []
        try:
            for name, target in self.targets.items():  # articles become visible after their media
                target.parent.mkdir(parents=True, exist_ok=True)
                backup = self.root / f"previous-{name}"
                existed = target.exists()
                if existed:
                    os.replace(target, backup)
                changed.append((name, target, backup, existed))
                os.replace(self.root / name, target)
        except BaseException:
            for name, target, backup, existed in reversed(changed):
                try:
                    if target.exists():
                        os.replace(target, self.root / f"unpublished-{name}")
                    if existed:
                        os.replace(backup, target)
                except OSError:
                    self._keep_backup = True
            if self._keep_backup:
                raise RuntimeError(f"Publication failed; original files were retained for recovery in {self.root}")
            raise

    def __exit__(self, *exc):
        if not self._keep_backup:
            # The only recursive removal is the freshly allocated staging folder inside the edition root.
            if self.root.parent == self.targets["articles"].parent and self.root.name.startswith(".edition-"):
                shutil.rmtree(self.root)
