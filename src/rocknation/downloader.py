"""Background download queue for tracks."""

import asyncio
import itertools
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import httpx

from rocknation.api import USER_AGENT
from rocknation.storage import Storage

_BAD_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def safe_name(name: str) -> str:
    name = _BAD_CHARS.sub("_", name).strip().strip(".")
    return name[:150] or "untitled"


@dataclass
class DownloadTask:
    id: int
    url: str
    dest: Path
    title: str
    artist: str
    album: str
    status: str = "queued"  # queued | downloading | done | error | cancelled
    progress: float = 0.0
    error: str = ""

    @property
    def finished(self) -> bool:
        return self.status in ("done", "error", "cancelled")


class Downloader:
    def __init__(
        self,
        storage: Storage,
        on_change: Callable[[DownloadTask], None],
        concurrency: int = 2,
    ):
        self.storage = storage
        self.on_change = on_change
        self.tasks: list[DownloadTask] = []
        self._ids = itertools.count(1)
        self._semaphore = asyncio.Semaphore(concurrency)
        self._running: dict[int, asyncio.Task] = {}
        self._client: Optional[httpx.AsyncClient] = None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": USER_AGENT},
                timeout=httpx.Timeout(30.0, read=60.0),
                follow_redirects=True,
            )
        return self._client

    def enqueue(
        self, url: str, dest: Path, title: str, artist: str, album: str
    ) -> DownloadTask:
        for task in self.tasks:
            if task.url == url and task.dest == dest and not task.finished:
                return task
        task = DownloadTask(next(self._ids), url, dest, title, artist, album)
        self.tasks.insert(0, task)
        if dest.exists() and dest.stat().st_size > 0:
            task.status, task.progress = "done", 1.0
            self.storage.add_download(url, str(dest))
            self.on_change(task)
            return task
        self.on_change(task)
        self._running[task.id] = asyncio.create_task(self._run(task))
        return task

    def cancel(self, task: DownloadTask):
        running = self._running.get(task.id)
        if running and not running.done():
            running.cancel()

    def clear_finished(self):
        self.tasks = [t for t in self.tasks if not t.finished]

    @property
    def active_count(self) -> int:
        return sum(1 for t in self.tasks if not t.finished)

    async def _run(self, task: DownloadTask):
        # Keep the audio extension: on Android 11+ the Music folder accepts
        # only audio files from apps without "All files access".
        part = task.dest.with_name(f"{task.dest.stem}.part{task.dest.suffix}")
        try:
            async with self._semaphore:
                task.status = "downloading"
                self.on_change(task)
                task.dest.parent.mkdir(parents=True, exist_ok=True)
                async with self._http().stream("GET", task.url) as r:
                    r.raise_for_status()
                    total = int(r.headers.get("content-length") or 0)
                    done = 0
                    last_reported = 0.0
                    with open(part, "wb") as f:
                        async for chunk in r.aiter_bytes(256 * 1024):
                            f.write(chunk)
                            done += len(chunk)
                            if total:
                                task.progress = done / total
                                if task.progress - last_reported >= 0.05:
                                    last_reported = task.progress
                                    self.on_change(task)
                part.replace(task.dest)
                task.status, task.progress = "done", 1.0
                self.storage.add_download(task.url, str(task.dest))
        except asyncio.CancelledError:
            task.status = "cancelled"
        except PermissionError:
            task.status = "error"
            task.error = "Нет доступа к папке. Выдайте разрешение в настройках."
        except (httpx.HTTPError, OSError) as e:
            task.status = "error"
            task.error = str(e) or type(e).__name__
        finally:
            self._running.pop(task.id, None)
            if task.status != "done":
                part.unlink(missing_ok=True)
            self.on_change(task)
