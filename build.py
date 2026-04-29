"""
build.py — сборка Selene в .exe через PyInstaller.
"""

import subprocess
import sys
import os
import shutil

APP_NAME = "Selene"
ENTRY = "main.py"
ICON = os.path.join("gui", "assets", "selene.ico")
DIST_DIR = "dist_selene"
BUILD_DIR = "build_selene"

# Скрытые импорты которые PyInstaller не видит сам
HIDDEN_IMPORTS = [
    "customtkinter",
    "tkinter",
    "tkinter.messagebox",
    "anthropic",
    "telethon",
    "telethon.tl.functions.account",
    "zoneinfo",
    "tzdata",
    "sqlite3",
    "asyncio",
    "threading",
]

# Дополнительные папки/файлы которые нужно включить в сборку
# Формат: ("источник", "папка назначения внутри exe")
DATA_FILES = [
    ("db",       "db"),
    ("sessions", "sessions"),
]

# CustomTkinter требует включения своих ресурсов (темы, шрифты)
try:
    import customtkinter
    ctk_path = os.path.dirname(customtkinter.__file__)
    DATA_FILES.append((ctk_path, "customtkinter"))
except ImportError:
    print("⚠ CustomTkinter не найден — установи: pip install customtkinter")
    sys.exit(1)


def build():
    print("=" * 50)
    print(f"  Building {APP_NAME}")
    print("=" * 50)

    # Чистим старую сборку
    for d in [DIST_DIR, BUILD_DIR]:
        if os.path.exists(d):
            shutil.rmtree(d)
            print(f"  Cleaned {d}/")

    # Формируем команду
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onedir",              # папка с зависимостями (быстрее чем --onefile)
        "--windowed",            # без консоли
        "--name", APP_NAME,
        "--distpath", DIST_DIR,
        "--workpath", BUILD_DIR,
        "--noconfirm",
    ]

    # Иконка
    if os.path.exists(ICON):
        cmd += ["--icon", ICON]

    # Скрытые импорты
    for h in HIDDEN_IMPORTS:
        cmd += ["--hidden-import", h]

    # Данные
    sep = ";" if sys.platform == "win32" else ":"
    for src, dst in DATA_FILES:
        if os.path.exists(src):
            cmd += ["--add-data", f"{src}{sep}{dst}"]

    cmd.append(ENTRY)

    print("\n  Running PyInstaller...\n")
    result = subprocess.run(cmd, capture_output=False)

    if result.returncode == 0:
        exe_path = os.path.join(DIST_DIR, APP_NAME)
        print("\n" + "=" * 50)
        print("  Build completed successfully")
        print(f"  Output: {exe_path}/")
        print("=" * 50)
        print("\n  Post-build notes:")
        print(f"  1. Ensure sessions/ exists in dist/{APP_NAME}/")
        print(f"  2. Ensure db/selene.db exists in dist/{APP_NAME}/db/ if you need existing userbots")
        print(f"  3. Run dist/{APP_NAME}/{APP_NAME}.exe")
    else:
        print("\n" + "=" * 50)
        print("  Build failed")
        print("  Check the output above")
        print("=" * 50)
        sys.exit(1)


if __name__ == "__main__":
    # Проверяем что PyInstaller установлен
    try:
        import PyInstaller
    except ImportError:
        print("PyInstaller not found. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"])

    build()
