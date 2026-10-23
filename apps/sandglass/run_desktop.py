#!/usr/bin/env python3
"""
Desktop entry — closest to the shipped product shape:

  1. Prefer bundled runtime/ binaries
  2. Auto-start Colima when needed
  3. Open a native window (pywebview) onto the local UI
"""

from __future__ import annotations

import threading
import time
import webbrowser

import uvicorn

from sandglass.bootstrap import prepare_engine
from sandglass.main import app
from sandglass.paths import ensure_tool_path, prepend_bundled_path
from sandglass.pick_folder import pick_folder

HOST = "127.0.0.1"
PORT = 8765
URL = f"http://{HOST}:{PORT}"


class DesktopApi:
    """Exposed to JS as window.pywebview.api"""

    def pick_folder(self) -> dict:
        # Prefer pywebview native dialog when a window exists
        try:
            import webview

            if webview.windows:
                result = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
                if result and len(result) > 0:
                    path = result[0]
                    if isinstance(path, (list, tuple)):
                        path = path[0] if path else None
                    if path:
                        return {"path": str(path).rstrip("/")}
                return {"path": None, "error": "已取消选择"}
        except Exception:  # noqa: BLE001
            pass
        return pick_folder()


def _serve() -> None:
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


def main() -> None:
    ensure_tool_path()
    prepend_bundled_path()
    print("Preparing sandbox engine…")
    info = prepare_engine()
    print(f"  mode={info['mode']} ready={info['ready']} — {info['message']}")

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()

    import urllib.request

    for _ in range(50):
        try:
            urllib.request.urlopen(URL, timeout=0.3)
            break
        except Exception:
            time.sleep(0.1)

    try:
        import webview

        api = DesktopApi()
        webview.create_window(
            "Sandglass",
            URL,
            width=1180,
            height=780,
            min_size=(900, 600),
            js_api=api,
        )
        webview.start()
    except ImportError:
        print("pywebview 未安装，使用浏览器打开。正式包会内嵌窗口：pip install pywebview")
        webbrowser.open(URL)
        thread.join()


if __name__ == "__main__":
    main()
