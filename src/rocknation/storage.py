"""Persistent app state: favorites, downloaded tracks and settings (JSON)."""

import json
import os
import threading
from pathlib import Path
from typing import Any, Optional


def data_dir() -> Path:
    # Set by `flet build` apps to the app's private persistent directory.
    path = os.getenv("FLET_APP_STORAGE_DATA") or Path.home() / ".rocknation"
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


DEFAULT_SETTINGS = {
    "download_dir": "",
    "ask_album_dir": True,
    "prefer_local": True,
}


class Storage:
    def __init__(self, path: Optional[Path] = None):
        self.path = path or data_dir() / "state.json"
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {
            "bands": {},
            "albums": {},
            "downloads": {},
            "settings": dict(DEFAULT_SETTINGS),
        }
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text("utf-8"))
                for key, value in loaded.items():
                    if isinstance(value, dict):
                        self._data.setdefault(key, {}).update(value)
            except (OSError, ValueError):
                pass

    def _save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=1), "utf-8")
        tmp.replace(self.path)

    # ---- favorite bands ----

    def favorite_bands(self) -> list[dict]:
        return sorted(self._data["bands"].values(), key=lambda b: b["name"].lower())

    def is_favorite_band(self, band_id: int) -> bool:
        return str(band_id) in self._data["bands"]

    def toggle_favorite_band(self, band_id: int, name: str, genre: str = "") -> bool:
        with self._lock:
            key = str(band_id)
            if key in self._data["bands"]:
                del self._data["bands"][key]
                added = False
            else:
                self._data["bands"][key] = {"id": band_id, "name": name, "genre": genre}
                added = True
            self._save()
        return added

    # ---- favorite albums ----

    def favorite_albums(self) -> list[dict]:
        return sorted(
            self._data["albums"].values(),
            key=lambda a: (a["band_name"].lower(), a.get("year", ""), a["title"]),
        )

    def is_favorite_album(self, album_id: int) -> bool:
        return str(album_id) in self._data["albums"]

    def toggle_favorite_album(
        self, album_id: int, title: str, year: str, band_id: Optional[int], band_name: str
    ) -> bool:
        with self._lock:
            key = str(album_id)
            if key in self._data["albums"]:
                del self._data["albums"][key]
                added = False
            else:
                self._data["albums"][key] = {
                    "id": album_id,
                    "title": title,
                    "year": year,
                    "band_id": band_id,
                    "band_name": band_name,
                }
                added = True
            self._save()
        return added

    # ---- downloaded files (track url -> local path) ----

    def local_path(self, url: str) -> Optional[str]:
        path = self._data["downloads"].get(url)
        if path and os.path.exists(path):
            return path
        return None

    def add_download(self, url: str, path: str):
        with self._lock:
            self._data["downloads"][url] = path
            self._save()

    def remove_download(self, url: str):
        with self._lock:
            if self._data["downloads"].pop(url, None) is not None:
                self._save()

    # ---- settings ----

    def get_setting(self, key: str) -> Any:
        return self._data["settings"].get(key, DEFAULT_SETTINGS.get(key))

    def set_setting(self, key: str, value: Any):
        with self._lock:
            self._data["settings"][key] = value
            self._save()
