import os
import sys
from pathlib import Path
from tkinter import TclError

from PIL import Image, ImageTk


APP_USER_MODEL_ID = "Selene.UserbotManager"
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def _set_windows_app_id():
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass


def configure_window_assets(window, assets_dir: str | os.PathLike) -> Image.Image | None:
    """Apply a stable Tk/Windows icon and return the source image for in-app logos."""
    _set_windows_app_id()

    assets_path = Path(assets_dir)
    ico_path = assets_path / "selene.ico"
    png_path = assets_path / "selene.png"
    source_path = png_path if png_path.exists() else ico_path

    if ico_path.exists():
        try:
            window.iconbitmap(default=str(ico_path))
        except TclError:
            pass

    if not source_path.exists():
        return None

    try:
        source = Image.open(source_path).convert("RGBA")
    except Exception:
        return None

    icon_images = []
    for size in ICON_SIZES:
        resized = source.resize((size, size), Image.Resampling.LANCZOS)
        icon_images.append(ImageTk.PhotoImage(resized))

    if icon_images:
        window._window_icon_images = icon_images
        window._window_icon = icon_images[-1]
        try:
            window.iconphoto(True, *icon_images)
        except TclError:
            pass

        # Some Windows/Tk combinations replace the icon after the first map event.
        def reapply_icon():
            try:
                window.iconphoto(True, *window._window_icon_images)
            except TclError:
                pass

        window.after(100, reapply_icon)

    return source
