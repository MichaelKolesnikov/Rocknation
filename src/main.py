import flet as ft

from rocknation.app import RocknationApp


def main(page: ft.Page):
    RocknationApp(page).start()


if __name__ == "__main__":
    ft.run(main)
