from dataclasses import asdict
from typing import Literal, Optional

import flet as ft
from flet_bg_audio.types import (
    BgAudioErrorEvent,
    BgAudioPositionChangeEvent,
    BgAudioStateChangeEvent,
    BgAudioTrack,
    BgAudioTrackChangeEvent,
)


@ft.control("BgAudio")
class BackgroundAudio(ft.Service):
    """
    Playlist player that keeps playing in the background and shows a media
    notification with playback controls (Android/iOS).

    The whole playlist lives on the native side, so switching to the next
    track does not require the Python side to be responsive.
    """

    notification_channel_id: str = "flet.bg_audio.channel"
    notification_channel_name: str = "Music"
    notification_icon: str = "mipmap/ic_launcher"
    """Android drawable resource used as the small notification icon."""

    on_state_change: Optional[ft.EventHandler[BgAudioStateChangeEvent]] = None
    on_track_change: Optional[ft.EventHandler[BgAudioTrackChangeEvent]] = None
    on_position_change: Optional[ft.EventHandler[BgAudioPositionChangeEvent]] = None
    """Fires every second while the position changes."""
    on_error: Optional[ft.EventHandler[BgAudioErrorEvent]] = None

    async def set_playlist(
        self,
        tracks: list[BgAudioTrack],
        index: int = 0,
        autoplay: bool = True,
        shuffle: bool = False,
    ):
        """
        Replaces the queue. Returns immediately; loading errors are reported
        via `on_error`.
        """
        await self._invoke_method(
            "set_playlist",
            {
                "tracks": [asdict(t) for t in tracks],
                "index": index,
                "autoplay": autoplay,
                "shuffle": shuffle,
            },
        )

    async def play(self):
        await self._invoke_method("play")

    async def pause(self):
        await self._invoke_method("pause")

    async def stop(self):
        await self._invoke_method("stop")

    async def seek(self, position_ms: int):
        await self._invoke_method("seek", {"position": int(position_ms)})

    async def next(self):
        await self._invoke_method("next")

    async def previous(self):
        await self._invoke_method("previous")

    async def skip_to(self, index: int):
        await self._invoke_method("skip_to", {"index": index})

    async def set_shuffle(self, enabled: bool):
        await self._invoke_method("set_shuffle", {"enabled": enabled})

    async def set_repeat(self, mode: Literal["off", "all", "one"]):
        await self._invoke_method("set_repeat", {"mode": mode})

    async def get_state(self) -> dict:
        return await self._invoke_method("get_state")
