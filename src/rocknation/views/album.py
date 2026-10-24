import random

import flet as ft

from rocknation.api import Album, SiteError
from rocknation.player import QueueItem
from rocknation.views.common import (
    Screen,
    cover,
    favorite_button,
    loading,
    message,
    safe_update,
)


class AlbumScreen(Screen):
    def __init__(self, app, album_id: int, title: str = ""):
        super().__init__(app)
        self.album_id = album_id
        self.title = title or "Альбом"
        self.album: Album | None = None
        self.track_tiles: list[ft.ListTile] = []
        self.fav = favorite_button(app.storage.is_favorite_album(album_id), self._toggle)
        app.player.subscribe(self._player_changed)

    def actions(self) -> list[ft.Control]:
        return [self.fav]

    def on_close(self):
        self.app.player.unsubscribe(self._player_changed)

    def on_show(self):
        self.fav.selected = self.app.storage.is_favorite_album(self.album_id)
        safe_update(self.fav)
        self._refresh_tracks()

    def _toggle(self, e):
        a = self.album
        if a is None:
            return
        self.fav.selected = self.app.storage.toggle_favorite_album(
            a.id, a.title, a.year, a.band_id, a.band_name
        )
        safe_update(self.fav)

    def build(self) -> ft.Control:
        self.list = ft.ListView([loading()], expand=True)
        self.app.spawn(self.load)
        return self.list

    def queue_items(self) -> list[QueueItem]:
        a = self.album
        return [
            QueueItem(t.url, t.title, a.band_name, a.title, a.id, a.band_id, a.cover)
            for t in a.tracks
        ]

    async def load(self, e=None):
        self.list.controls = [loading()]
        safe_update(self.list)
        try:
            self.album = a = await self.app.client.album(self.album_id)
        except SiteError as ex:
            self.list.controls = [message(str(ex), ft.Icons.WIFI_OFF, retry=self.load)]
            safe_update(self.list)
            return
        if a.title and a.title != self.title:
            self.title = a.title
            self.app.refresh_title(self)

        band_link = ft.TextButton(
            a.band_name,
            icon=ft.Icons.PERSON,
            on_click=self._open_band,
            disabled=a.band_id is None,
        )
        buttons = ft.Row(
            [
                ft.FilledButton("Слушать", icon=ft.Icons.PLAY_ARROW, on_click=self._play_all),
                ft.OutlinedButton("Вперемешку", icon=ft.Icons.SHUFFLE, on_click=self._shuffle),
                ft.IconButton(
                    ft.Icons.DOWNLOAD,
                    tooltip="Скачать альбом",
                    on_click=lambda e: self.app.spawn(self.app.download_album, a),
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            wrap=True,
        )
        header = ft.Container(
            ft.Column(
                [
                    cover(a.cover, 240, radius=12),
                    ft.Text(a.title, size=20, weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER),
                    band_link,
                    ft.Text(
                        " · ".join(x for x in (a.year, f"треков: {len(a.tracks)}") if x),
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    buttons,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=6,
            ),
            padding=16,
            alignment=ft.Alignment.CENTER,
        )
        self.track_tiles = [self._track_tile(i) for i in range(len(a.tracks))]
        self.list.controls = [header, *self.track_tiles]
        if not a.tracks:
            self.list.controls.append(message("Треки не найдены"))
        self._refresh_tracks(update=False)
        safe_update(self.list)

    def _track_tile(self, i: int) -> ft.ListTile:
        track = self.album.tracks[i]
        return ft.ListTile(
            leading=ft.Container(
                ft.Text(str(track.number), color=ft.Colors.ON_SURFACE_VARIANT),
                width=32,
                alignment=ft.Alignment.CENTER,
            ),
            title=ft.Text(track.title, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
            trailing=ft.IconButton(
                ft.Icons.DOWNLOAD,
                tooltip="Скачать трек",
                on_click=lambda e: self.app.spawn(self.app.download_track, self.album, track),
            ),
            on_click=lambda e: self.app.spawn(self._play, i),
            dense=True,
            data=track.url,
        )

    def _refresh_tracks(self, update: bool = True):
        player = self.app.player
        for number, tile in enumerate(self.track_tiles, start=1):
            url = tile.data
            current = player.is_current(url)
            tile.selected = current
            tile.leading.content = (
                ft.Icon(ft.Icons.GRAPHIC_EQ, color=ft.Colors.PRIMARY)
                if current
                else ft.Text(str(number), color=ft.Colors.ON_SURFACE_VARIANT)
            )
            downloaded = self.app.storage.local_path(url) is not None
            tile.trailing.icon = ft.Icons.DOWNLOAD_DONE if downloaded else ft.Icons.DOWNLOAD
            tile.trailing.icon_color = ft.Colors.PRIMARY if downloaded else None
        if update and self.track_tiles:
            safe_update(*self.track_tiles)

    def _player_changed(self):
        self._refresh_tracks()

    async def _play(self, index: int, shuffle=None):
        await self.app.player.play_queue(self.queue_items(), index, shuffle)

    async def _play_all(self, e):
        if self.album and self.album.tracks:
            await self._play(0, shuffle=False)

    async def _shuffle(self, e):
        if self.album and self.album.tracks:
            await self._play(random.randrange(len(self.album.tracks)), shuffle=True)

    def _open_band(self, e):
        from rocknation.views.band import BandScreen

        self.app.push(BandScreen(self.app, self.album.band_id, self.album.band_name))
