import flet as ft

from rocknation.api import BandDetails, SiteError
from rocknation.views.common import (
    Screen,
    album_tile,
    cover,
    favorite_button,
    loading,
    message,
    refresh_favorites,
    safe_update,
)


class BandScreen(Screen):
    def __init__(self, app, band_id: int, name: str = "", genre: str = ""):
        super().__init__(app)
        self.band_id = band_id
        self.title = name or "Группа"
        self.genre = genre
        self.details: BandDetails | None = None
        self.fav = favorite_button(app.storage.is_favorite_band(band_id), self._toggle)

    def actions(self) -> list[ft.Control]:
        return [self.fav]

    def _toggle(self, e):
        name = self.details.band.name if self.details else self.title
        self.fav.selected = self.app.storage.toggle_favorite_band(self.band_id, name, self.genre)
        safe_update(self.fav)

    def build(self) -> ft.Control:
        self.list = ft.ListView([loading()], expand=True)
        self.app.spawn(self.load)
        return self.list

    async def load(self, e=None):
        self.list.controls = [loading()]
        safe_update(self.list)
        try:
            self.details = await self.app.client.band(self.band_id)
        except SiteError as ex:
            self.list.controls = [message(str(ex), ft.Icons.WIFI_OFF, retry=self.load)]
            safe_update(self.list)
            return
        band = self.details.band
        if band.name and band.name != self.title:
            self.title = band.name
            self.app.refresh_title(self)
        header = ft.Container(
            ft.Column(
                [
                    cover(band.image, 220, radius=12, icon=ft.Icons.GROUPS),
                    ft.Text(band.name, size=22, weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER),
                    ft.Text(f"Альбомов: {len(self.details.albums)}",
                            color=ft.Colors.ON_SURFACE_VARIANT),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=16,
            alignment=ft.Alignment.CENTER,
        )
        self.list.controls = [header] + [
            album_tile(self.app, a.id, a.title, a.year, band.id, band.name)
            for a in self.details.albums
        ]
        if not self.details.albums:
            self.list.controls.append(message("У группы пока нет альбомов"))
        safe_update(self.list)

    def on_show(self):
        self.fav.selected = self.app.storage.is_favorite_band(self.band_id)
        safe_update(self.fav)
        if self._content is not None:
            refresh_favorites(self.app, self.list)
