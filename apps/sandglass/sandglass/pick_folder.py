from __future__ import annotations

import platform
import subprocess
from typing import Any


def pick_folder() -> dict[str, str | None]:
    """
    Native folder picker. Prefer macOS AppleScript (works without Tk),
    then Tk, then clear error asking user to paste a path.
    """
    system = platform.system().lower()
    if system == "darwin":
        path = _macos_osascript()
        if path:
            return {"path": path}
        # fall through to tk / error

    path = _tk_dialog()
    if path:
        return {"path": path}

    if system == "darwin":
        return {
            "path": None,
            "error": "未能打开系统选文件夹对话框。请直接粘贴路径，例如 /Users/你/项目",
        }
    return {
        "path": None,
        "error": "当前环境无法弹出选文件夹窗口，请直接粘贴路径",
    }


def _macos_osascript() -> str | None:
    script = (
        'try\n'
        '  set p to choose folder with prompt "选择项目文件夹"\n'
        '  return POSIX path of p\n'
        'on error\n'
        '  return ""\n'
        'end try'
    )
    try:
        out = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if out.returncode != 0:
            return None
        path = (out.stdout or "").strip()
        if not path:
            return None
        # AppleScript POSIX path often ends with /
        return path.rstrip("/") or path
    except Exception:  # noqa: BLE001
        return None


def _tk_dialog() -> str | None:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:  # noqa: BLE001
        return None

    root = tk.Tk()
    root.withdraw()
    try:
        try:
            root.attributes("-topmost", True)
        except Exception:  # noqa: BLE001
            pass
        path = filedialog.askdirectory(title="选择项目文件夹")
        return path or None
    finally:
        try:
            root.destroy()
        except Exception:  # noqa: BLE001
            pass
