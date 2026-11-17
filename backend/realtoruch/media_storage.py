"""Private storage adapters accept only server-generated immutable keys."""
import os
import re
from contextlib import contextmanager
from pathlib import Path


class LocalStorage:
    def __init__(self, root):
        self.root = Path(root)

    @contextmanager
    def _directory(self, key, create=False):
        if not re.fullmatch(r"[0-9a-f-]{36}/[ab]", key):
            raise ValueError("invalid storage key")
        directory, name = key.split("/")
        if create:
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        root_fd = os.open(self.root, flags)
        try:
            os.fchmod(root_fd, 0o700)
            if create:
                try:
                    os.mkdir(directory, mode=0o700, dir_fd=root_fd)
                except FileExistsError:
                    pass
            asset_fd = os.open(directory, flags, dir_fd=root_fd)
            try:
                os.fchmod(asset_fd, 0o700)
                yield asset_fd, name
            finally:
                os.close(asset_fd)
        finally:
            os.close(root_fd)

    def put(self, key, data):
        with self._directory(key, create=True) as (directory, name):
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
            with os.fdopen(fd, "wb") as output:
                output.write(data)

    def get(self, key):
        with self._directory(key) as (directory, name):
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
            with os.fdopen(fd, "rb") as source:
                return source.read()

    def delete(self, key):
        try:
            with self._directory(key) as (directory, name):
                # Refuse symlinks, including a pre-existing attacker-controlled file.
                stat = os.stat(name, dir_fd=directory, follow_symlinks=False)
                import stat as stat_module
                if not stat_module.S_ISREG(stat.st_mode):
                    raise ValueError("invalid stored object")
                os.unlink(name, dir_fd=directory)
        except FileNotFoundError:
            pass

    def fence(self, key):
        self.delete(key)


class GCSStorage:
    """Inject a bucket/client; creation and credentials are operator responsibilities."""
    def __init__(self, bucket):
        self.bucket = bucket

    def put(self, key, data):
        self.bucket.blob(key).upload_from_string(data, content_type="image/jpeg", if_generation_match=0,
                                                 timeout=10, retry=None)

    def get(self, key):
        try:
            return self.bucket.blob(key).download_as_bytes(timeout=10, retry=None)
        except Exception as exc:
            if getattr(exc, "code", None) == 404:
                raise FileNotFoundError from None
            raise

    def delete(self, key):
        try:
            blob = self.bucket.blob(key)
            blob.reload(timeout=10, retry=None)
            blob.delete(if_generation_match=blob.generation, timeout=10, retry=None)
        except Exception as exc:
            if getattr(exc, "code", None) != 404:
                raise

    def fence(self, key):
        """Leave a zero-byte live generation to fence delayed create-only PUTs."""
        for _ in range(3):
            blob = self.bucket.blob(key)
            try:
                blob.reload(timeout=10, retry=None)
            except Exception as exc:
                if getattr(exc, "code", None) != 404:
                    raise
                generation = 0
            else:
                if blob.size == 0:
                    return
                generation = blob.generation
            try:
                blob.upload_from_string(b"", content_type="application/octet-stream",
                                        if_generation_match=generation, timeout=10, retry=None)
                return
            except Exception as exc:
                if getattr(exc, "code", None) not in (404, 412):
                    raise
        raise RuntimeError("Media storage fence conflicted repeatedly")
