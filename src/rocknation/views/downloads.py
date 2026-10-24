import flet as ft

from rocknation.downloader import DownloadTask
from rocknation.views.common import Screen, message, safe_update

_STATUS = {
    "queued": "В очереди",
    "downloading": "Загрузка",
    "done": "Готово",
    "error": "Ошибка",
    "cancelled": "Отменено",
}


class DownloadsScreen(Screen):
    title = "Загрузки"

    def __init__(self, app):
        super().__init__(app)
        self.rows: dict[int, ft.ListTile] = {}

    def actions(self) -> list[ft.Control]:
        return [
            ft.IconButton(ft.Icons.DELETE_SWEEP, tooltip="Убрать завершённые",
                          on_click=self._clear),
        ]

    def build(self) -> ft.Control:
        self.folder = ft.Text(size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        self.list = ft.ListView(expand=True)
        self._fill()
        return ft.Column(
            [ft.Container(self.folder, padding=ft.Padding.symmetric(horizontal=16, vertical=6)),
             self.list],
            expand=True,
            spacing=0,
        )

    def _fill(self):
        self.folder.value = f"Папка по умолчанию: {self.app.download_dir()}"
        self.rows = {t.id: self._row(t) for t in self.app.downloader.tasks}
        self.list.controls = list(self.rows.values()) or [
            message("Загрузок пока нет.\nСкачивайте треки и альбомы на странице альбома.",
                    ft.Icons.DOWNLOAD)
        ]

    def _row(self, task: DownloadTask) -> ft.ListTile:
        tile = ft.ListTile(
            title=ft.Text(task.title, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            subtitle=ft.Column([ft.Text(), ft.ProgressBar(height=3)], spacing=4, tight=True),
            trailing=ft.IconButton(ft.Icons.CLOSE, tooltip="Отменить",
                                   on_click=lambda e: self.app.downloader.cancel(task)),
            dense=True,
        )
        self._apply(tile, task)
        return tile

    def _apply(self, tile: ft.ListTile, task: DownloadTask):
        text, bar = tile.subtitle.controls
        status = _STATUS.get(task.status, task.status)
        if task.status == "downloading":
            status += f" {int(task.progress * 100)}%"
        if task.status == "error":
            status += f": {task.error}"
        text.value = f"{task.artist} — {task.album} · {status}"
        bar.value = task.progress if task.status != "queued" else None
        bar.visible = not task.finished
        tile.leading = ft.Icon({
            "done": ft.Icons.CHECK_CIRCLE,
            "error": ft.Icons.ERROR_OUTLINE,
            "cancelled": ft.Icons.CANCEL,
        }.get(task.status, ft.Icons.DOWNLOADING),
            color=ft.Colors.ERROR if task.status == "error" else ft.Colors.PRIMARY)
        tile.trailing.visible = not task.finished

    def task_changed(self, task: DownloadTask):
        if self._content is None:
            return
        tile = self.rows.get(task.id)
        if tile is None:
            self._fill()
            safe_update(self.list)
        else:
            self._apply(tile, task)
            safe_update(tile)

    def _clear(self, e):
        self.app.downloader.clear_finished()
        self._fill()
        safe_update(self.list)

    def on_show(self):
        if self._content is not None:
            self._fill()
            safe_update(self.folder, self.list)
