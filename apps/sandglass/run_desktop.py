#!/usr/bin/env python3
"""
Desktop entry — closest to the shipped product shape:

  1. Prefer bundled runtime/ binaries
  2. Auto-start Colima when needed
  3. Open a native window (pywebview) onto the local UI

Dev without pywebview: falls back to opening the system browser.
"""

from __future__ import annotations

import threading
import time
import webbrowser

import uvicorn

from sandglass.bootstrap import prepare_engine
from sandglass.main import app
from sandglass.paths import prepend_bundled_path

HOST = "127.0.0.1"
PORT = 8765
URL = f"http://{HOST}:{PORT}"


def _serve() -> None:
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


def main() -> None:
    prepend_bundled_path()
    print("Preparing sandbox engine…")
    info = prepare_engine()
    print(f"  mode={info['mode']} ready={info['ready']} — {info['message']}")

    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()

    # Wait until server accepts connections
    import urllib.request

    for _ in range(50):
        try:
            urllib.request.urlopen(URL, timeout=0.3)
            break
        except Exception:
            time.sleep(0.1)

    try:
        import webview

        webview.create_window(
            "Sandglass",
            URL,
            width=1180,
            height=780,
            min_size=(900, 600),
        )
        webview.start()
    except ImportError:
        print("pywebview 未安装，使用浏览器打开。正式包会内嵌窗口：pip install pywebview")
        webbrowser.open(URL)
        thread.join()


if __name__ == "__main__":
    main()
