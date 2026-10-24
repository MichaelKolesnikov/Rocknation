import asyncio
from pathlib import Path
from typing import Optional

import flet as ft

from rocknation.api import Album, RocknationClient, Track
from rocknation.downloader import Downloader, DownloadTask, safe_name
from rocknation.player import Player
from rocknation.storage import Storage
from rocknation.views.catalog import CatalogScreen, SearchScreen
from rocknation.views.common import Screen, safe_update
from rocknation.views.downloads import DownloadsScreen
from rocknation.views.favorites import FavoritesScreen
from rocknation.views.player import MiniPlayer, PlayerScreen
from rocknation.views.settings import SettingsScreen

ANDROID_MUSIC_DIR = "/storage/emulated/0/Music/Rocknation"


class RocknationApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.is_android = page.platform == ft.PagePlatform.ANDROID
        self.client = RocknationClient()
        self.storage = Storage()
        self.player = Player(page, self.storage)
        self.player.on_error = lambda msg: self.toast(f"Ошибка воспроизведения: {msg}")
        self.downloader = Downloader(self.storage, self._download_changed)
        self.file_picker = ft.FilePicker()
        self._permissions = None
        self._storage_asked = False

        self.downloads_screen = DownloadsScreen(self)
        self.tabs: list[list[Screen]] = [
            [CatalogScreen(self)],
            [SearchScreen(self)],
            [FavoritesScreen(self)],
            [self.downloads_screen],
        ]
        self.tab = 0

        self.body = ft.Container(expand=True)
        self.mini_player = MiniPlayer(self)
        self.appbar = ft.AppBar(automatically_imply_leading=False)
        self.nav = ft.NavigationBar(
            destinations=[
                ft.NavigationBarDestination(icon=ft.Icons.LIBRARY_MUSIC, label="Каталог"),
                ft.NavigationBarDestination(icon=ft.Icons.SEARCH, label="Поиск"),
                ft.NavigationBarDestination(icon=ft.Icons.FAVORITE_BORDER,
                                            selected_icon=ft.Icons.FAVORITE, label="Избранное"),
                ft.NavigationBarDestination(icon=ft.Icons.DOWNLOAD, label="Загрузки"),
            ],
            on_change=self._tab_changed,
        )

    # ---- setup ----

    def start(self):
        page = self.page
        page.title = "Rocknation"
        page.theme_mode = ft.ThemeMode.DARK
        page.theme = ft.Theme(color_scheme_seed=ft.Colors.DEEP_ORANGE)
        page.dark_theme = ft.Theme(color_scheme_seed=ft.Colors.DEEP_ORANGE)
        view = page.views[0]
        view.padding = 0
        view.spacing = 0
        view.appbar = self.appbar
        view.navigation_bar = self.nav
        view.on_confirm_pop = self._back_pressed
        view.controls = [ft.Column([self.body, self.mini_player], expand=True, spacing=0)]
        self._show()

    def spawn(self, fn, *args):
        """Run a coroutine function in the background."""
        return self.page.run_task(fn, *args)

    def toast(self, text: str):
        self.page.show_dialog(ft.SnackBar(ft.Text(text)))

    # ---- navigation ----

    @property
    def stack(self) -> list[Screen]:
        return self.tabs[self.tab]

    def push(self, screen: Screen):
        self.stack.append(screen)
        self._show()

    def pop(self):
        if len(self.stack) > 1:
            self.stack.pop().on_close()
            self._show()

    def open_player(self):
        if not isinstance(self.stack[-1], PlayerScreen):
            self.push(PlayerScreen(self))

    def refresh_title(self, screen: Screen):
        if self.stack and self.stack[-1] is screen:
            self.appbar.title = ft.Text(screen.title, max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS)
            safe_update(self.appbar)

    def _show(self):
        screen = self.stack[-1]
        nested = len(self.stack) > 1
        self.appbar.leading = (
            ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda e: self.pop()) if nested else None
        )
        self.appbar.title = ft.Text(screen.title, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
        actions = list(screen.actions())
        if not nested:
            actions.append(ft.IconButton(ft.Icons.SETTINGS, tooltip="Настройки",
                                         on_click=lambda e: self.push(SettingsScreen(self))))
        self.appbar.actions = actions
        self.body.content = screen.content
        self.nav.selected_index = self.tab
        # Let the system back button go through our stack first.
        self.page.views[0].can_pop = not nested
        screen.on_show()
        self.page.update()

    def _tab_changed(self, e):
        index = self.nav.selected_index
        if index == self.tab and len(self.stack) > 1:
            # second tap on the active tab returns to its root
            while len(self.stack) > 1:
                self.stack.pop().on_close()
        self.tab = index
        self._show()

    async def _back_pressed(self, e):
        self.pop()
        await self.page.views[0].confirm_pop(False)

    # ---- downloads ----

    def download_dir(self) -> str:
        custom = self.storage.get_setting("download_dir")
        if custom:
            return custom
        if self.is_android:
            return ANDROID_MUSIC_DIR
        return str(Path.home() / "Music" / "Rocknation")

    def _album_folder(self, album: Album) -> str:
        return safe_name(" - ".join(x for x in (album.year, album.title) if x))

    def _download_changed(self, task: DownloadTask):
        self.downloads_screen.task_changed(task)
        if task.status == "done":
            self.player.notify()  # refresh "downloaded" marks on album screens
        if task.status == "error" and "доступа" in task.error:
            self.toast(task.error)

    async def download_track(self, album: Album, track: Track):
        base = Path(self.download_dir()) / safe_name(album.band_name) / self._album_folder(album)
        if not await self._ensure_writable(base):
            return
        self.downloader.enqueue(
            track.url, base / safe_name(f"{track.title}.mp3"),
            track.title, album.band_name, album.title,
        )
        self.toast(f"Скачивается: {track.title}")

    async def download_album(self, album: Album):
        if not album.tracks:
            return
        if self.storage.get_setting("ask_album_dir"):
            folder = await self.pick_folder(f"Куда сохранить «{album.title}»?")
            if not folder:
                return
        else:
            folder = str(Path(self.download_dir()) / safe_name(album.band_name))
        target = Path(folder) / safe_name(f"{album.band_name} - {self._album_folder(album)}")
        if not await self._ensure_writable(target):
            return
        for track in album.tracks:
            self.downloader.enqueue(
                track.url, target / safe_name(f"{track.title}.mp3"),
                track.title, album.band_name, album.title,
            )
        self.toast(f"Добавлено в загрузки: {len(album.tracks)} треков → {target}")

    async def pick_folder(self, title: str) -> Optional[str]:
        try:
            path = await self.file_picker.get_directory_path(
                dialog_title=title, initial_directory=self.download_dir()
            )
        except Exception as e:
            self.toast(f"Не удалось открыть выбор папки: {e}")
            return None
        if path and self.is_android and path.startswith("/tree/"):
            # Some devices return a SAF tree URI path instead of a file path.
            self.toast("Эта папка недоступна. Выберите папку во внутренней памяти.")
            return None
        return path

    async def _ensure_writable(self, folder: Path) -> bool:
        if self.is_android and not self._storage_asked:
            # Ask once per launch, before the first download.
            self._storage_asked = True
            if not await self.has_storage_access():
                await self.request_storage_access(explain=True)
        if self._is_writable(folder):
            return True
        if self.is_android and await self.request_storage_access(explain=True):
            if self._is_writable(folder):
                return True
        self.toast(f"Нет доступа к папке {folder}")
        return False

    @staticmethod
    def _is_writable(folder: Path) -> bool:
        try:
            folder.mkdir(parents=True, exist_ok=True)
            # .mp3, so the probe is accepted by Android's Music folder rules
            probe = folder / ".rocknation_write_test.mp3"
            probe.write_bytes(b"")
            probe.unlink()
            return True
        except OSError:
            return False

    def _permission_handler(self):
        import flet_permission_handler as fph

        if self._permissions is None:
            self._permissions = fph.PermissionHandler()
        return fph, self._permissions

    async def has_storage_access(self) -> bool:
        fph, ph = self._permission_handler()
        try:
            status = await ph.get_status(fph.Permission.MANAGE_EXTERNAL_STORAGE)
        except Exception:
            return False
        return status == fph.PermissionStatus.GRANTED

    async def _confirm_storage_request(self) -> bool:
        answer = asyncio.get_running_loop().create_future()

        def close(result: bool):
            self.page.pop_dialog()
            if not answer.done():
                answer.set_result(result)

        self.page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Доступ к файлам"),
                content=ft.Text(
                    "Чтобы сохранять музыку в любую папку телефона, разрешите "
                    "приложению «Доступ ко всем файлам».\n\n"
                    "Откроется системный экран — включите там переключатель "
                    "и вернитесь назад.\n\n"
                    "Без разрешения музыка будет сохраняться только в "
                    "папки «Music» и «Download»."
                ),
                actions=[
                    ft.TextButton("Не сейчас", on_click=lambda e: close(False)),
                    ft.FilledButton("Разрешить", on_click=lambda e: close(True)),
                ],
            )
        )
        return await answer

    async def request_storage_access(self, explain: bool = False) -> bool:
        """
        Android 11+: opens the system "All files access" screen for the app.
        Android 10 and older: the regular storage permission dialog.
        """
        if await self.has_storage_access():
            return True
        if explain and not await self._confirm_storage_request():
            return False
        fph, ph = self._permission_handler()
        granted = (fph.PermissionStatus.GRANTED, fph.PermissionStatus.LIMITED)
        for permission in (fph.Permission.MANAGE_EXTERNAL_STORAGE, fph.Permission.STORAGE):
            try:
                status = await ph.request(permission)
            except Exception:
                continue
            if status in granted:
                self.toast("Доступ к файлам предоставлен")
                return True
        self.toast("Доступ не предоставлен. Его можно включить в «Настройки → Доступ к файлам».")
        return False
