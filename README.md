<p align="center">
  <img src="src/assets/icon.png" width="128" alt="Rocknation icon">
</p>

# Rocknation

An unofficial Android client for the MP3 section of [rocknation.su](https://rocknation.su/),
written in Python with [Flet 1.0](https://flet.dev).

[Русская версия](README.ru.md)

## Features

- **Catalog**: browse bands alphabetically or by genre, with pagination.
- **Search** bands by name.
- **Band and album pages** with covers and track lists.
- **Favorites**: save bands and albums. Favorites are stored on the device.
- **Streaming in the background**: queue, shuffle, repeat. Playback keeps going with the
  screen off and can be controlled from the notification shade and the lock screen.
- **Downloads**: save a single track to the default folder, or a whole album to a folder
  you pick. Progress is shown on the *Downloads* tab, and downloads can be cancelled.
- **Offline playback**: downloaded tracks play from local storage.

## How it works

The site has no public API, so the app reads its HTML pages: band lists, album lists and
the track playlist embedded in each album page. Flet has no built-in background playback,
so the project ships its own Flet extension, `flet_bg_audio`. It wraps
[`audio_service`](https://pub.dev/packages/audio_service) and
[`just_audio`](https://pub.dev/packages/just_audio). The whole playlist is passed to the
native player, so tracks keep switching even while the Python side is idle.

```
src/                         the app (entry point: src/main.py)
  rocknation/api.py          rocknation.su scraper
  rocknation/player.py       playback queue
  rocknation/downloader.py   download queue
  rocknation/storage.py      favorites, downloads, settings (JSON)
  rocknation/views/          screens
  assets/icon.svg            app icon source (icon.png is generated from it)
flet_bg_audio/               Flet extension: background player + media notification
tools/prepare_template.py    patches the Flet build template for background playback
tools/render_icon.py         renders icon.svg to icon.png
```

## Building the APK

Requirements: Python 3.10+, JDK 17 and the Android SDK. `flet build` installs Flutter
itself if it is missing.

```bash
python -m venv .venv
.venv/bin/pip install -e ./flet_bg_audio -e ".[desktop]" "flet[all]==1.0.5"

# once, and again after every Flet upgrade:
.venv/bin/python tools/prepare_template.py

.venv/bin/flet build apk --arch arm64-v8a
# output: build/apk/rocknation.apk
```

`arm64-v8a` is also set in `pyproject.toml`, so a plain `flet build apk` produces the
same APK.

`tools/prepare_template.py` downloads the official Flet build template into
`build_template/` and applies the changes `audio_service` needs:

- `MainActivity` extends `AudioServiceFragmentActivity`;
- the media service and the media button receiver are declared in `AndroidManifest.xml`;
- a monochrome notification icon is added and protected from release resource shrinking.
  Without that protection, the app crashes on the first track.

## Running on desktop

For development:

```bash
.venv/bin/flet run src/main.py
```

On desktop, music plays through `flet-audio`, without background playback or a media
notification. The `flet_bg_audio` extension only works in a built app.

## App icon

The source is `src/assets/icon.svg`. `flet build` cannot rasterize SVG, so regenerate
`src/assets/icon.png` after editing the SVG:

```bash
.venv/bin/pip install cairosvg
.venv/bin/python tools/render_icon.py
```

The background behind the adaptive Android icon is set by `adaptive_icon_background` in
`pyproject.toml`.

## Where music is saved

- **Default:** `Music/Rocknation/<Band>/<Year - Album>/`. On Android 11+ this folder works
  without any permission.
- **Albums** go to the folder you pick when downloading. You can turn this off in Settings.
- **Any other folder** on Android 11+ needs *All files access*. The app asks for it before
  the first download and opens the system settings screen. You can also grant it later in
  *Settings → All files access*.

## Disclaimer

This is an unofficial project and is not affiliated with rocknation.su. All music,
cover art and other content belong to their respective rights holders. The MIT license
covers only the source code in this repository.

## License

[MIT](LICENSE) © 2026 Michael Kolesnikov
