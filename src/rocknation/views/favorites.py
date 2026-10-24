import flet as ft

from rocknation.views.common import Screen, album_tile, band_tile, message, safe_update


class FavoritesScreen(Screen):
    title = "Избранное"

    def __init__(self, app):
        super().__init__(app)
        self.section = "bands"

    def build(self) -> ft.Control:
        self.chips = ft.Row(
            [
                ft.Chip(label=ft.Text("Группы"), data="bands", show_checkmark=False,
                        leading=ft.Icon(ft.Icons.GROUPS), on_select=self._select),
                ft.Chip(label=ft.Text("Альбомы"), data="albums", show_checkmark=False,
                        leading=ft.Icon(ft.Icons.ALBUM), on_select=self._select),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
        )
        self.list = ft.ListView(expand=True)
        self._fill()
        return ft.Column([ft.Container(self.chips, padding=8), self.list], expand=True)

    def _select(self, e):
        self.section = e.control.data
        self._fill()
        safe_update(self.chips, self.list)

    def _fill(self):
        for chip in self.chips.controls:
            chip.selected = chip.data == self.section
        storage = self.app.storage
        if self.section == "bands":
            items = [band_tile(self.app, b["id"], b["name"], b.get("genre", ""))
                     for b in storage.favorite_bands()]
            empty = "Нет избранных групп.\nНажмите ♡ рядом с группой, чтобы добавить её."
        else:
            items = [
                album_tile(self.app, a["id"], a["title"], a.get("year", ""),
                           a.get("band_id"), a.get("band_name", ""), show_band=True)
                for a in storage.favorite_albums()
            ]
            empty = "Нет избранных альбомов.\nНажмите ♡ рядом с альбомом, чтобы добавить его."
        self.list.controls = items or [message(empty, ft.Icons.FAVORITE_BORDER)]

    def on_show(self):
        if self._content is not None:
            self._fill()
            safe_update(self.chips, self.list)
