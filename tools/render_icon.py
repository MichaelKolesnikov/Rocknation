"""
Renders src/assets/icon.svg to src/assets/icon.png.

`flet build` ignores SVG icons, so the PNG must be regenerated after the SVG
is edited:

    pip install cairosvg
    python tools/render_icon.py
"""

from pathlib import Path

import cairosvg

ASSETS = Path(__file__).resolve().parent.parent / "src" / "assets"


def main():
    src, dst = ASSETS / "icon.svg", ASSETS / "icon.png"
    cairosvg.svg2png(url=str(src), write_to=str(dst), output_width=1024, output_height=1024)
    print(f"Rendered {dst}")


if __name__ == "__main__":
    main()
