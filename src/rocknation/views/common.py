from typing import TYPE_CHECKING, Callable, Optional

import flet as ft

if TYPE_CHECKING:
    from rocknation.app import RocknationApp


class Screen:
    """A page of the in-app navigation stack."""

    title: str = ""

    def __init__(self, app: "RocknationApp"):
        self.app = app
        self._content: Optional[ft.Control] = None

    @property
    def content(self) -> ft.Control:
        if self._content is None:
            self._content = self.build()
        return self._content

    def build(self) -> ft.Control:
        raise NotImplementedError

    def actions(self) -> list[ft.Control]:
        return []

    def on_show(self):
        """Called every time the screen becomes visible."""

    def on_close(self):
        """Called when the screen is removed from the stack."""


def safe_update(*controls: ft.Control):
    """Update controls that may currently be detached from the page."""
    for c in controls:
        try:
            c.update()
        except (RuntimeError, AssertionError):
            pass


def cover(src: str, size: float, radius: float = 6, icon=ft.Icons.ALBUM) -> ft.Control:
    return ft.Image(
        src=src,
        width=size,
        height=size,
        fit=ft.BoxFit.COVER,
        border_radius=radius,
        gapless_playback=True,
        error_content=ft.Container(
            ft.Icon(icon, size=size * 0.5, color=ft.Colors.ON_SURFACE_VARIANT),
            width=size,
            height=size,
            alignment=ft.Alignment.CENTER,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            border_radius=radius,
        ),
    )


def loading() -> ft.Control:
    return ft.Container(ft.ProgressRing(), alignment=ft.Alignment.CENTER, padding=40)


def message(text: str, icon=ft.Icons.INFO_OUTLINE, retry: Optional[Callable] = None):
    controls: list[ft.Control] = [
        ft.Icon(icon, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
        ft.Text(text, text_align=ft.TextAlign.CENTER, color=ft.Colors.ON_SURFACE_VARIANT),
    ]
    if retry:
        controls.append(ft.TextButton("Повторить", icon=ft.Icons.REFRESH, on_click=retry))
    return ft.Container(
        ft.Column(controls, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        alignment=ft.Alignment.CENTER,
        padding=40,
    )


def favorite_button(is_favorite: bool, on_click, size: float = 24) -> ft.IconButton:
    return ft.IconButton(
        icon=ft.Icons.FAVORITE_BORDER,
        selected_icon=ft.Icons.FAVORITE,
        selected=is_favorite,
        icon_size=size,
        icon_color=ft.Colors.PRIMARY,
        tooltip="Избранное",
        on_click=on_click,
    )


def band_tile(app: "RocknationApp", band_id: int, name: str, genre: str = "") -> ft.ListTile:
    from rocknation.views.band import BandScreen

    def toggle(e):
        added = app.storage.toggle_favorite_band(band_id, name, genre)
        e.control.selected = added
        safe_update(e.control)

    return ft.ListTile(
        leading=ft.CircleAvatar(
            foreground_image_src=f"https://rocknation.su/upload/images/bands/{band_id}.jpg",
            content=ft.Text(name[:1].upper()),
        ),
        title=ft.Text(name, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
        subtitle=ft.Text(genre) if genre else None,
        trailing=favorite_button(app.storage.is_favorite_band(band_id), toggle),
        on_click=lambda e: app.push(BandScreen(app, band_id, name)),
        data=("band", band_id),
    )


def album_tile(
    app: "RocknationApp",
    album_id: int,
    title: str,
    year: str,
    band_id: Optional[int],
    band_name: str,
    show_band: bool = False,
) -> ft.ListTile:
    from rocknation.api import album_cover
    from rocknation.views.album import AlbumScreen

    def toggle(e):
        added = app.storage.toggle_favorite_album(album_id, title, year, band_id, band_name)
        e.control.selected = added
        safe_update(e.control)

    subtitle = " · ".join(x for x in (band_name if show_band else "", year) if x)
    return ft.ListTile(
        leading=cover(album_cover(album_id), 48),
        title=ft.Text(title, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
        subtitle=ft.Text(subtitle) if subtitle else None,
        trailing=favorite_button(app.storage.is_favorite_album(album_id), toggle),
        on_click=lambda e: app.push(AlbumScreen(app, album_id, title)),
        data=("album", album_id),
    )


def refresh_favorites(app: "RocknationApp", list_view: ft.Control):
    """Sync heart buttons of band/album tiles with the storage."""
    for tile in getattr(list_view, "controls", []):
        if not isinstance(tile, ft.ListTile) or not isinstance(tile.data, tuple):
            continue
        kind, item_id = tile.data
        if kind == "band":
            tile.trailing.selected = app.storage.is_favorite_band(item_id)
        else:
            tile.trailing.selected = app.storage.is_favorite_album(item_id)
    safe_update(list_view)


def format_ms(ms: int) -> str:
    s = max(0, int(ms // 1000))
    return f"{s // 60}:{s % 60:02d}"
