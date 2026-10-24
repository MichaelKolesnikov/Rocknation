"""Playback queue on top of the native background player."""

import random
from dataclasses import dataclass
from typing import Callable, Optional

import flet as ft

from rocknation.storage import Storage


@dataclass
class QueueItem:
    url: str
    title: str
    artist: str
    album: str
    album_id: Optional[int] = None
    band_id: Optional[int] = None
    cover: str = ""


class _DesktopBackend:
    """
    Fallback for `flet run` on desktop, where the background audio extension
    is not compiled in. The queue is advanced from Python.
    """

    def __init__(self, on_state, on_track, on_position, on_error):
        import flet_audio as fta

        self._fta = fta
        self._on_state, self._on_track = on_state, on_track
        self._on_position, self._on_error = on_position, on_error
        self._tracks: list[dict] = []
        self._order: list[int] = []
        self._pos = 0
        self._duration = 0
        self._playing = False
        self._repeat = "off"
        self._audio: Optional["fta.Audio"] = None

    @property
    def _index(self) -> int:
        return self._order[self._pos] if self._order else 0

    async def _load(self, autoplay: bool):
        if self._audio:
            await self._audio.release()
        self._audio = self._fta.Audio(
            src=self._tracks[self._index]["url"],
            on_state_change=self._state_changed,
            on_position_change=lambda e: self._on_position(e.position, self._duration),
            on_duration_change=self._duration_changed,
        )
        self._on_track(self._index)
        if autoplay:
            await self._audio.play()

    def _duration_changed(self, e):
        self._duration = int(e.duration.in_milliseconds)

    async def _state_changed(self, e):
        state = e.state.value
        self._playing = state == "playing"
        self._on_state(self._playing, "ready")
        if state == "completed":
            if self._repeat == "one":
                await self._audio.play()
            elif self._pos + 1 < len(self._order) or self._repeat == "all":
                await self.next()
            else:
                self._on_state(False, "completed")

    async def set_playlist(self, tracks, index=0, autoplay=True, shuffle=False):
        from dataclasses import asdict

        self._tracks = [asdict(t) for t in tracks]
        self._order = list(range(len(self._tracks)))
        self._pos = index
        await self.set_shuffle(shuffle)
        await self._load(autoplay)

    async def play(self):
        if self._audio:
            await self._audio.resume()

    async def pause(self):
        if self._audio:
            await self._audio.pause()

    async def stop(self):
        if self._audio:
            await self._audio.release()
            self._on_state(False, "idle")

    async def seek(self, position_ms):
        if self._audio:
            await self._audio.seek(ft.Duration(milliseconds=position_ms))

    async def next(self):
        if not self._order:
            return
        self._pos = (self._pos + 1) % len(self._order)
        await self._load(True)

    async def previous(self):
        if not self._order:
            return
        self._pos = max(0, self._pos - 1)
        await self._load(True)

    async def skip_to(self, index):
        self._pos = self._order.index(index)
        await self._load(True)

    async def set_shuffle(self, enabled):
        current = self._index
        self._order = list(range(len(self._tracks)))
        if enabled:
            random.shuffle(self._order)
        self._pos = self._order.index(current)

    async def set_repeat(self, mode):
        self._repeat = mode


class Player:
    REPEAT_MODES = ("off", "all", "one")

    def __init__(self, page: ft.Page, storage: Storage):
        self.page = page
        self.storage = storage
        self.queue: list[QueueItem] = []
        self.index: int = -1
        self.playing = False
        self.loading = False
        self.position = 0
        self.duration = 0
        self.shuffle = False
        self.repeat = "off"
        self._listeners: list[Callable[[], None]] = []
        self._position_listeners: list[Callable[[], None]] = []
        self.on_error: Optional[Callable[[str], None]] = None

        if page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS):
            import flet_bg_audio as fba

            self._track_cls = fba.BgAudioTrack
            self.backend = fba.BackgroundAudio(
                notification_channel_id="su.rocknation.app.playback",
                notification_channel_name="Воспроизведение",
                notification_icon="drawable/ic_stat_music",
                on_state_change=lambda e: self._set_state(e.playing, e.processing),
                on_track_change=lambda e: self._set_index(e.index),
                on_position_change=lambda e: self._set_position(e.position, e.duration),
                on_error=lambda e: self._error(e.message),
            )
        else:
            from flet_bg_audio.types import BgAudioTrack

            self._track_cls = BgAudioTrack
            self.backend = _DesktopBackend(
                self._set_state, self._set_index, self._set_position, self._error
            )

    # ---- listeners ----

    def subscribe(self, on_change: Callable[[], None], on_position=None):
        self._listeners.append(on_change)
        if on_position:
            self._position_listeners.append(on_position)

    def unsubscribe(self, on_change: Callable[[], None], on_position=None):
        if on_change in self._listeners:
            self._listeners.remove(on_change)
        if on_position in self._position_listeners:
            self._position_listeners.remove(on_position)

    def notify(self):
        self._notify(self._listeners)

    def _notify(self, listeners):
        for listener in list(listeners):
            try:
                listener()
            except Exception as e:  # a broken view must not stop playback updates
                print("Player listener error:", e)

    def _set_state(self, playing: bool, processing: str):
        self.playing = playing
        self.loading = processing in ("loading", "buffering")
        self._notify(self._listeners)

    def _set_index(self, index: int):
        if index != self.index:
            self.index = index
            self.position, self.duration = 0, 0
        self._notify(self._listeners)

    def _set_position(self, position: int, duration: int):
        self.position = position
        self.duration = duration or self.duration
        self._notify(self._position_listeners)

    def _error(self, message: str):
        if self.on_error:
            self.on_error(message)

    # ---- state ----

    @property
    def current(self) -> Optional[QueueItem]:
        if 0 <= self.index < len(self.queue):
            return self.queue[self.index]
        return None

    def is_current(self, url: str) -> bool:
        return self.current is not None and self.current.url == url

    # ---- commands ----

    async def play_queue(
        self, items: list[QueueItem], index: int = 0, shuffle: Optional[bool] = None
    ):
        if not items:
            return
        if shuffle is not None:
            self.shuffle = shuffle
        self.queue = list(items)
        self.index = index
        self.position, self.duration = 0, 0
        self.loading = True
        self._notify(self._listeners)
        prefer_local = self.storage.get_setting("prefer_local")
        tracks = []
        for i, item in enumerate(items):
            local = self.storage.local_path(item.url) if prefer_local else None
            tracks.append(
                self._track_cls(
                    id=f"{i}:{item.url}",
                    url=local or item.url,
                    title=item.title,
                    artist=item.artist,
                    album=item.album,
                    art_uri=item.cover or None,
                )
            )
        await self.backend.set_playlist(
            tracks, index=index, autoplay=True, shuffle=self.shuffle
        )

    async def toggle(self):
        if self.current is None:
            return
        if self.playing:
            await self.backend.pause()
        else:
            await self.backend.play()

    async def next(self):
        await self.backend.next()

    async def previous(self):
        await self.backend.previous()

    async def skip_to(self, index: int):
        await self.backend.skip_to(index)

    async def seek(self, position_ms: int):
        self.position = position_ms
        await self.backend.seek(position_ms)

    async def stop(self):
        await self.backend.stop()
        self.queue, self.index = [], -1
        self.playing = False
        self._notify(self._listeners)

    async def toggle_shuffle(self):
        self.shuffle = not self.shuffle
        await self.backend.set_shuffle(self.shuffle)
        self._notify(self._listeners)

    async def cycle_repeat(self):
        i = self.REPEAT_MODES.index(self.repeat)
        self.repeat = self.REPEAT_MODES[(i + 1) % len(self.REPEAT_MODES)]
        await self.backend.set_repeat(self.repeat)
        self._notify(self._listeners)
