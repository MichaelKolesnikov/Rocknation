import flet as ft

from rocknation.views.common import Screen, cover, format_ms, safe_update


class MiniPlayer(ft.Container):
    """Compact player shown above the navigation bar."""

    def __init__(self, app):
        self.app = app
        self.cover = ft.Container(width=44, height=44)
        self.title = ft.Text(max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                             weight=ft.FontWeight.W_500)
        self.artist = ft.Text(max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, size=12,
                              color=ft.Colors.ON_SURFACE_VARIANT)
        self.play_btn = ft.IconButton(ft.Icons.PLAY_ARROW,
                                      on_click=lambda e: app.spawn(app.player.toggle))
        self.progress = ft.ProgressBar(value=0, height=2)
        super().__init__(
            content=ft.Column(
                [
                    self.progress,
                    ft.Container(
                        ft.Row(
                            [
                                self.cover,
                                ft.Column([self.title, self.artist], spacing=0, expand=True,
                                          tight=True),
                                self.play_btn,
                                ft.IconButton(ft.Icons.SKIP_NEXT,
                                              on_click=lambda e: app.spawn(app.player.next)),
                            ],
                            spacing=10,
                        ),
                        padding=ft.Padding.only(left=10, right=4, top=4, bottom=4),
                    ),
                ],
                spacing=0,
                tight=True,
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            visible=False,
            on_click=lambda e: app.open_player(),
        )
        self._cover_src = None
        app.player.subscribe(self.refresh, self.refresh_position)

    def refresh(self):
        player = self.app.player
        item = player.current
        self.visible = item is not None
        if item:
            if item.cover != self._cover_src:
                self._cover_src = item.cover
                self.cover.content = cover(item.cover, 44, radius=4)
            self.title.value = item.title
            self.artist.value = f"{item.artist} — {item.album}"
            self.play_btn.icon = ft.Icons.PAUSE if player.playing else ft.Icons.PLAY_ARROW
        safe_update(self)

    def refresh_position(self):
        player = self.app.player
        self.progress.value = player.position / player.duration if player.duration else 0
        safe_update(self.progress)


class PlayerScreen(Screen):
    title = "Сейчас играет"

    def __init__(self, app):
        super().__init__(app)
        self._seeking = False
        self._queue_signature = None
        app.player.subscribe(self.refresh, self.refresh_position)

    def on_close(self):
        self.app.player.unsubscribe(self.refresh, self.refresh_position)

    def build(self) -> ft.Control:
        player = self.app.player
        self.cover = ft.Container(alignment=ft.Alignment.CENTER)
        self.title = ft.Text(size=20, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)
        self.subtitle = ft.TextButton(on_click=self._open_album)
        self.slider = ft.Slider(min=0, max=1, value=0, expand=True,
                                on_change=self._slider_drag, on_change_end=self._seek)
        self.pos_text = ft.Text("0:00", size=12)
        self.dur_text = ft.Text("0:00", size=12)
        self.shuffle_btn = ft.IconButton(ft.Icons.SHUFFLE,
                                         on_click=lambda e: self.app.spawn(player.toggle_shuffle))
        self.repeat_btn = ft.IconButton(ft.Icons.REPEAT,
                                        on_click=lambda e: self.app.spawn(player.cycle_repeat))
        self.play_btn = ft.IconButton(ft.Icons.PLAY_CIRCLE_FILLED, icon_size=64,
                                      icon_color=ft.Colors.PRIMARY,
                                      on_click=lambda e: self.app.spawn(player.toggle))
        self.loading = ft.ProgressRing(width=16, height=16, stroke_width=2, visible=False)
        self.queue = ft.Column(spacing=0)
        self.refresh(update=False)
        return ft.ListView(
            [
                ft.Container(self.cover, padding=ft.Padding.only(top=16, bottom=8)),
                self.title,
                ft.Row([self.subtitle], alignment=ft.MainAxisAlignment.CENTER),
                ft.Container(
                    ft.Row([self.pos_text, self.slider, self.dur_text]),
                    padding=ft.Padding.symmetric(horizontal=12),
                ),
                ft.Row(
                    [
                        self.shuffle_btn,
                        ft.IconButton(ft.Icons.SKIP_PREVIOUS, icon_size=36,
                                      on_click=lambda e: self.app.spawn(player.previous)),
                        self.play_btn,
                        ft.IconButton(ft.Icons.SKIP_NEXT, icon_size=36,
                                      on_click=lambda e: self.app.spawn(player.next)),
                        self.repeat_btn,
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                ft.Row([self.loading], alignment=ft.MainAxisAlignment.CENTER),
                ft.Container(ft.Text("Очередь", weight=ft.FontWeight.BOLD),
                             padding=ft.Padding.only(left=16, top=12)),
                self.queue,
            ],
            expand=True,
        )

    def refresh(self, update: bool = True):
        if self._content is None and update:
            return
        player = self.app.player
        item = player.current
        if item is None:
            self.title.value = "Ничего не играет"
            self.subtitle.content = ""
            self.cover.content = cover("", 280, radius=16, icon=ft.Icons.MUSIC_NOTE)
        else:
            self.cover.content = cover(item.cover, 280, radius=16)
            self.title.value = item.title
            self.subtitle.content = f"{item.artist} — {item.album}"
        self.play_btn.icon = (
            ft.Icons.PAUSE_CIRCLE_FILLED if player.playing else ft.Icons.PLAY_CIRCLE_FILLED
        )
        self.loading.visible = player.loading
        on = ft.Colors.PRIMARY
        self.shuffle_btn.icon_color = on if player.shuffle else None
        self.repeat_btn.icon = ft.Icons.REPEAT_ONE if player.repeat == "one" else ft.Icons.REPEAT
        self.repeat_btn.icon_color = on if player.repeat != "off" else None
        self._fill_queue()
        self.refresh_position(update=False)
        if update:
            safe_update(self._content)

    def _fill_queue(self):
        player = self.app.player
        signature = (id(player.queue), player.index)
        if signature == self._queue_signature:
            return
        self._queue_signature = signature
        self.queue.controls = [
            ft.ListTile(
                leading=ft.Icon(ft.Icons.GRAPHIC_EQ if i == player.index else ft.Icons.MUSIC_NOTE,
                                color=ft.Colors.PRIMARY if i == player.index else None),
                title=ft.Text(q.title, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                subtitle=ft.Text(q.artist, size=12),
                selected=i == player.index,
                dense=True,
                on_click=lambda e, i=i: self.app.spawn(player.skip_to, i),
            )
            for i, q in enumerate(player.queue)
        ]

    def refresh_position(self, update: bool = True):
        if self._seeking or (self._content is None and update):
            return
        player = self.app.player
        duration = max(player.duration, 1)
        self.slider.max = duration
        self.slider.value = min(player.position, duration)
        self.pos_text.value = format_ms(player.position)
        self.dur_text.value = format_ms(player.duration)
        if update:
            safe_update(self.slider, self.pos_text, self.dur_text)

    def _slider_drag(self, e):
        self._seeking = True
        self.pos_text.value = format_ms(int(e.control.value))
        safe_update(self.pos_text)

    async def _seek(self, e):
        self._seeking = False
        await self.app.player.seek(int(e.control.value))

    def _open_album(self, e):
        from rocknation.views.album import AlbumScreen

        item = self.app.player.current
        if item and item.album_id:
            self.app.push(AlbumScreen(self.app, item.album_id, item.album))
