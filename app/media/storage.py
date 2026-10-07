"""Файловое хранилище медиа. В БД хранятся пути относительно корня хранилища."""
import logging
import shutil
import time
import uuid
from pathlib import Path

log = logging.getLogger(__name__)


class Storage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        for sub in ("sources", "jobs", "tmp"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def new_id() -> str:
        return uuid.uuid4().hex

    def source_dir(self, source_id: str) -> Path:
        return self.root / "sources" / source_id

    def job_dir(self, job_id: str) -> Path:
        return self.root / "jobs" / job_id

    def new_tmp_dir(self) -> Path:
        path = self.root / "tmp" / self.new_id()
        path.mkdir(parents=True)
        return path

    def relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()

    def absolute(self, relative: str) -> Path:
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Path escapes storage root")
        return path

    @staticmethod
    def remove_dir(path: Path) -> None:
        shutil.rmtree(path, ignore_errors=True)

    def cleanup_tmp(self, max_age_seconds: float = 3600) -> int:
        """Удаляет забытые временные каталоги (например, после аварийного завершения)."""
        removed = 0
        now = time.time()
        for child in (self.root / "tmp").iterdir():
            try:
                if now - child.stat().st_mtime > max_age_seconds:
                    shutil.rmtree(child, ignore_errors=True) if child.is_dir() else child.unlink(missing_ok=True)
                    removed += 1
            except OSError:
                log.warning("Failed to clean %s", child)
        return removed
