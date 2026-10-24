from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

import flet as ft

if TYPE_CHECKING:
    from flet_bg_audio.bg_audio import BackgroundAudio  # noqa

__all__ = [
    "BgAudioErrorEvent",
    "BgAudioPositionChangeEvent",
    "BgAudioStateChangeEvent",
    "BgAudioTrack",
    "BgAudioTrackChangeEvent",
]


@dataclass
class BgAudioTrack:
    """
    A playlist item.

    `url` is either an http(s) URL or an absolute path to a local file.
    """

    id: str
    url: str
    title: str
    artist: Optional[str] = None
    album: Optional[str] = None
    art_uri: Optional[str] = None


@dataclass
class BgAudioStateChangeEvent(ft.Event["BackgroundAudio"]):
    playing: bool
    processing: str
    """One of `idle`, `loading`, `buffering`, `ready`, `completed`."""


@dataclass
class BgAudioTrackChangeEvent(ft.Event["BackgroundAudio"]):
    index: int


@dataclass
class BgAudioPositionChangeEvent(ft.Event["BackgroundAudio"]):
    position: int
    """Position in milliseconds."""
    duration: int = field(default=0)
    """Duration of the current track in milliseconds, `0` if unknown yet."""


@dataclass
class BgAudioErrorEvent(ft.Event["BackgroundAudio"]):
    message: str
