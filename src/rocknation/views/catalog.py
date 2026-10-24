import string

import flet as ft

from rocknation.api import BandsPage, SiteError
from rocknation.views.common import (
    Screen,
    band_tile,
    loading,
    message,
    refresh_favorites,
    safe_update,
)


class CatalogScreen(Screen):
    title = "Группы"

    def __init__(self, app):
        super().__init__(app)
        self.letter = ""
        self.genre_id = 0
        self.page_no = 1
        self.pages = 1

    def build(self) -> ft.Control:
        self.letters = ft.Row(scroll=ft.ScrollMode.AUTO, spacing=4)
        for key in ["", *string.ascii_uppercase]:
            self.letters.controls.append(
                ft.Chip(
                    label=ft.Text(key or "Все"),
                    selected=key == self.letter,
                    show_checkmark=False,
                    data=key,
                    on_select=self._letter_selected,
                )
            )
        self.genres = ft.Dropdown(
            label="Жанр",
            dense=True,
            expand=True,
            options=[ft.DropdownOption(key="0", text="Все жанры")],
            value="0",
            on_select=self._genre_selected,
        )
        self.list = ft.ListView(expand=True)
        self.page_label = ft.Text()
        self.prev_btn = ft.IconButton(ft.Icons.CHEVRON_LEFT, on_click=self._prev)
        self.next_btn = ft.IconButton(ft.Icons.CHEVRON_RIGHT, on_click=self._next)
        self.pager = ft.Row(
            [self.prev_btn, self.page_label, self.next_btn],
            alignment=ft.MainAxisAlignment.CENTER,
            visible=False,
        )
        self.app.spawn(self._load_genres)
        self.app.spawn(self.load)
        return ft.Column(
            [
                ft.Container(self.letters, padding=ft.Padding.symmetric(horizontal=8)),
                ft.Container(ft.Row([self.genres]), padding=ft.Padding.symmetric(horizontal=12)),
                self.list,
                self.pager,
            ],
            expand=True,
            spacing=6,
        )

    async def _load_genres(self):
        try:
            genres = await self.app.client.genres()
        except SiteError:
            return
        self.genres.options += [ft.DropdownOption(key=str(g.id), text=g.name) for g in genres]
        safe_update(self.genres)

    async def _letter_selected(self, e):
        self.letter = e.control.data
        self.genre_id = 0
        self.genres.value = "0"
        for chip in self.letters.controls:
            chip.selected = chip.data == self.letter
        self.page_no = 1
        safe_update(self.letters, self.genres)
        await self.load()

    async def _genre_selected(self, e):
        self.genre_id = int(self.genres.value or 0)
        if self.genre_id:
            self.letter = ""
            for chip in self.letters.controls:
                chip.selected = chip.data == ""
            safe_update(self.letters)
        self.page_no = 1
        await self.load()

    async def _prev(self, e):
        await self._go(-1)

    async def _next(self, e):
        await self._go(1)

    async def _go(self, delta: int):
        self.page_no = min(max(1, self.page_no + delta), self.pages)
        await self.load()

    async def load(self, e=None):
        self.list.controls = [loading()]
        self.pager.visible = False
        safe_update(self.list, self.pager)
        client = self.app.client
        try:
            if self.genre_id:
                result: BandsPage = await client.bands_by_genre(self.genre_id, self.page_no)
            elif self.letter:
                result = await client.bands_by_letter(self.letter, self.page_no)
            else:
                result = await client.bands(self.page_no)
        except SiteError as ex:
            self.list.controls = [message(str(ex), ft.Icons.WIFI_OFF, retry=self.load)]
            safe_update(self.list)
            return
        self.pages = result.pages
        self.list.controls = [band_tile(self.app, b.id, b.name, b.genre) for b in result.bands]
        if not result.bands:
            self.list.controls = [message("Ничего не найдено")]
        self.page_label.value = f"{self.page_no} / {self.pages}"
        self.prev_btn.disabled = self.page_no <= 1
        self.next_btn.disabled = self.page_no >= self.pages
        self.pager.visible = self.pages > 1
        safe_update(self.list, self.pager)

    def on_show(self):
        # favorites could have been changed on other screens
        if self._content is not None:
            refresh_favorites(self.app, self.list)


class SearchScreen(Screen):
    title = "Поиск"

    def build(self) -> ft.Control:
        self.field = ft.TextField(
            hint_text="Название группы",
            prefix_icon=ft.Icons.SEARCH,
            autofocus=False,
            on_submit=self.search,
            expand=True,
        )
        self.results = ft.ListView(
            [message("Введите название группы", ft.Icons.SEARCH)], expand=True
        )
        return ft.Column(
            [
                ft.Container(
                    ft.Row([self.field, ft.IconButton(ft.Icons.SEARCH, on_click=self.search)]),
                    padding=ft.Padding.only(left=12, right=4, top=8),
                ),
                self.results,
            ],
            expand=True,
        )

    def on_show(self):
        if self._content is not None:
            refresh_favorites(self.app, self.results)

    async def search(self, e=None):
        text = (self.field.value or "").strip()
        if not text:
            return
        self.results.controls = [loading()]
        safe_update(self.results)
        try:
            bands = await self.app.client.search(text)
        except SiteError as ex:
            self.results.controls = [message(str(ex), ft.Icons.WIFI_OFF, retry=self.search)]
        else:
            self.results.controls = [band_tile(self.app, b.id, b.name, b.genre) for b in bands] or [
                message(f"По запросу «{text}» ничего не найдено")
            ]
        safe_update(self.results)
