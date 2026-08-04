"""
Regenerate assets/logo.png and assets/pharmaguard.ico from assets/logo.svg.

Only needed when the logo changes; the generated files are committed so a normal
install does not require Pillow.

    python tools/build_icons.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QGuiApplication, QImage, QPainter
from PyQt5.QtSvg import QSvgRenderer

ASSETS = Path(__file__).resolve().parent.parent / "assets"
ICO_SIZES = [16, 32, 48, 64, 128, 256]


def render(renderer: QSvgRenderer, size: int, destination: Path) -> Path:
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    image.save(str(destination))
    return destination


def main() -> int:
    # QGuiApplication must exist before any QImage/QPainter work.
    app = QGuiApplication(sys.argv)  # noqa: F841  (kept alive for the Qt runtime)
    source = ASSETS / "logo.svg"
    renderer = QSvgRenderer(str(source))
    if not renderer.isValid():
        print(f"Could not parse {source}", file=sys.stderr)
        return 1

    temporary = ASSETS / ".render"
    temporary.mkdir(exist_ok=True)
    try:
        render(renderer, 512, ASSETS / "logo.png")
        frames = [Image.open(render(renderer, size, temporary / f"{size}.png")) for size in ICO_SIZES]
        frames[-1].save(ASSETS / "pharmaguard.ico", format="ICO", sizes=[(s, s) for s in ICO_SIZES])
    finally:
        for leftover in temporary.glob("*.png"):
            leftover.unlink()
        temporary.rmdir()

    print(f"Wrote {ASSETS / 'logo.png'} and {ASSETS / 'pharmaguard.ico'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
