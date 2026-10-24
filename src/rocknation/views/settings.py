import flet as ft

from rocknation.views.common import Screen, safe_update


class SettingsScreen(Screen):
    title = "Настройки"

    def build(self) -> ft.Control:
        storage = self.app.storage
        self.folder = ft.ListTile(
            leading=ft.Icon(ft.Icons.FOLDER_OPEN),
            title=ft.Text("Папка для загрузок"),
            subtitle=ft.Text(self.app.download_dir()),
            on_click=self._pick_folder,
        )
        controls: list[ft.Control] = [
            self.folder,
            ft.ListTile(
                leading=ft.Icon(ft.Icons.RESTART_ALT),
                title=ft.Text("Сбросить папку на стандартную"),
                on_click=self._reset_folder,
            ),
            ft.Switch(
                label="Спрашивать папку при скачивании альбома",
                value=storage.get_setting("ask_album_dir"),
                on_change=lambda e: storage.set_setting("ask_album_dir", e.control.value),
            ),
            ft.Switch(
                label="Играть скачанные треки из памяти телефона",
                value=storage.get_setting("prefer_local"),
                on_change=lambda e: storage.set_setting("prefer_local", e.control.value),
            ),
        ]
        if self.app.is_android:
            self.access = ft.ListTile(
                leading=ft.Icon(ft.Icons.SECURITY),
                title=ft.Text("Доступ ко всем файлам"),
                subtitle=ft.Text("Проверка…"),
                on_click=self._request_access,
            )
            controls.append(self.access)
            self.app.spawn(self._refresh_access)
        controls.append(
            ft.Container(
                ft.Text("Музыка: rocknation.su", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                padding=16,
            )
        )
        return ft.ListView(controls, expand=True, spacing=4,
                           padding=ft.Padding.symmetric(horizontal=8))

    async def _refresh_access(self):
        granted = await self.app.has_storage_access()
        self.access.subtitle.value = (
            "Разрешён — можно сохранять в любую папку"
            if granted
            else "Не разрешён — нажмите, чтобы разрешить. Без него музыка "
            "сохраняется только в «Music» и «Download»"
        )
        self.access.trailing = ft.Icon(
            ft.Icons.CHECK_CIRCLE if granted else ft.Icons.CHEVRON_RIGHT,
            color=ft.Colors.PRIMARY if granted else None,
        )
        safe_update(self.access)

    async def _request_access(self, e):
        await self.app.request_storage_access()
        await self._refresh_access()

    async def _pick_folder(self, e):
        path = await self.app.pick_folder("Папка для загрузок")
        if path:
            self.app.storage.set_setting("download_dir", path)
            self.folder.subtitle.value = path
            safe_update(self.folder)

    def _reset_folder(self, e):
        self.app.storage.set_setting("download_dir", "")
        self.folder.subtitle.value = self.app.download_dir()
        safe_update(self.folder)
