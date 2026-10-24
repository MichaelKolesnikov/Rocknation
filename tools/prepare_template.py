"""
Builds `build_template/` - the official Flet build template patched for
background playback (audio_service):

* MainActivity extends AudioServiceFragmentActivity, so the Flutter engine is
  shared with the media service;
* AndroidManifest declares the media service and the media button receiver;
* a monochrome status bar icon for the playback notification (protected from
  resource shrinking).

Run it once (and again after upgrading Flet):

    python tools/prepare_template.py
"""

import io
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

import flet.version

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "build_template"
URL = "https://github.com/flet-dev/flet/releases/download/v{v}/flet-build-template.zip"

OUT = "build/{{cookiecutter.out_dir}}"
MAIN_ACTIVITY = OUT + "/android/app/src/main/kotlin/{{ cookiecutter.kotlin_dir }}/MainActivity.kt"
MANIFEST = OUT + "/android/app/src/main/AndroidManifest.xml"
STAT_ICON = OUT + "/android/app/src/main/res/drawable/ic_stat_music.xml"
KEEP_RES = OUT + "/android/app/src/main/res/raw/keep.xml"

MANIFEST_ANCHOR = "        <!-- Don't delete the meta-data below."
MANIFEST_SERVICE = """\
        <!-- rocknation: background playback (audio_service) -->
        <service android:name="com.ryanheise.audioservice.AudioService"
            android:foregroundServiceType="mediaPlayback"
            android:exported="true"
            tools:ignore="Instantiatable">
            <intent-filter>
                <action android:name="android.media.browse.MediaBrowserService" />
            </intent-filter>
        </service>
        <receiver android:name="com.ryanheise.audioservice.MediaButtonReceiver"
            android:exported="true"
            tools:ignore="Instantiatable">
            <intent-filter>
                <action android:name="android.intent.action.MEDIA_BUTTON" />
            </intent-filter>
        </receiver>
"""

STAT_ICON_XML = """\
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp" android:height="24dp"
    android:viewportWidth="24" android:viewportHeight="24">
    <path android:fillColor="#FFFFFFFF"
        android:pathData="M12,3v10.55C11.41,13.21 10.73,13 10,13c-2.21,0 -4,1.79 -4,4s1.79,4 4,4 4,-1.79 4,-4V7h4V3h-6z"/>
</vector>
"""

# The icon is looked up by name at runtime only, so release resource shrinking
# would strip it and the notification (and the app) would crash on first play.
KEEP_RES_XML = """\
<?xml version="1.0" encoding="utf-8"?>
<resources xmlns:tools="http://schemas.android.com/tools"
    tools:keep="@drawable/ic_stat_music" />
"""


def patch(path: Path, old: str, new: str):
    text = path.read_text("utf-8")
    if new in text:
        return
    if old not in text:
        sys.exit(f"Template changed, cannot patch {path}: {old!r} not found")
    path.write_text(text.replace(old, new, 1), "utf-8")


def main():
    version = flet.version.flet_version
    print(f"Downloading Flet {version} build template...")
    with urllib.request.urlopen(URL.format(v=version)) as r:
        data = r.read()

    if TARGET.exists():
        shutil.rmtree(TARGET)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(TARGET)

    patch(
        TARGET / MAIN_ACTIVITY,
        "import io.flutter.embedding.android.FlutterFragmentActivity\n\n"
        "class MainActivity : FlutterFragmentActivity()",
        "import com.ryanheise.audioservice.AudioServiceFragmentActivity\n\n"
        "class MainActivity : AudioServiceFragmentActivity()",
    )
    patch(TARGET / MANIFEST, MANIFEST_ANCHOR, MANIFEST_SERVICE + MANIFEST_ANCHOR)
    icon = TARGET / STAT_ICON
    icon.parent.mkdir(parents=True, exist_ok=True)
    icon.write_text(STAT_ICON_XML, "utf-8")
    keep = TARGET / KEEP_RES
    keep.parent.mkdir(parents=True, exist_ok=True)
    keep.write_text(KEEP_RES_XML, "utf-8")
    print(f"Template ready: {TARGET}")


if __name__ == "__main__":
    main()
