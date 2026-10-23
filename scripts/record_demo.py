#!/usr/bin/env python3
"""Record a short Sandglass UI demo against the real local app."""

from __future__ import annotations

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps" / "sandglass"
OUT_DIR = ROOT / "demos"
URL = "http://127.0.0.1:8765"
DEMO_KEY = "sk-ant-HOST-ONLY-DEMO-KEY-do-not-leak"


def wait_server(timeout: float = 30) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(URL, timeout=0.5)
            return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("Sandglass server not reachable on :8765")


def ensure_server() -> subprocess.Popen | None:
    try:
        urllib.request.urlopen(URL, timeout=0.5)
        return None
    except Exception:
        pass
    py = APP / ".venv" / "bin" / "python"
    proc = subprocess.Popen(
        [str(py), "run.py"],
        cwd=str(APP),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    wait_server()
    return proc


def cleanup_demo_secrets() -> None:
    secrets = Path.home() / ".local/state/enclave/secrets/global.env"
    if not secrets.exists():
        return
    try:
        lines = [
            ln
            for ln in secrets.read_text().splitlines()
            if "HOST-ONLY-DEMO" not in ln and "sk-ant-demo-" not in ln
        ]
        secrets.write_text("\n".join(lines) + ("\n" if lines else ""))
    except Exception:
        pass


def main() -> int:
    from playwright.sync_api import sync_playwright

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_dir = OUT_DIR / "_raw"
    if raw_dir.exists():
        for p in raw_dir.glob("*"):
            p.unlink()
    else:
        raw_dir.mkdir(parents=True)

    server = ensure_server()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1180, "height": 780},
                record_video_dir=str(raw_dir),
                record_video_size={"width": 1180, "height": 780},
            )
            page = context.new_page()
            page.goto(URL, wait_until="networkidle")
            page.wait_for_timeout(1000)

            # 1) Isolation board
            page.click('button[data-nav="sessions"]')
            page.wait_for_timeout(1800)

            # 2) Save a distinctive key on the HOST vault
            page.click('button[data-nav="secrets"]')
            page.wait_for_timeout(1200)
            page.fill("#key-anthropic", DEMO_KEY)
            page.wait_for_timeout(700)
            page.fill("#key-openai", "sk-HOST-ONLY-DEMO-OPENAI")
            page.wait_for_timeout(700)
            page.click("#save-secrets")
            page.wait_for_timeout(1800)

            # 3) In-app sandbox terminal: prove keys are NOT visible inside
            page.evaluate("() => window.SandglassDemo.showSecretProof()")
            # wait for alpine pull + script output
            page.wait_for_timeout(14000)
            try:
                page.wait_for_selector("text=不可见", timeout=20000)
            except Exception:
                page.wait_for_timeout(3000)

            page.wait_for_timeout(4000)

            # 4) Brief engine status
            page.click('button[data-nav="settings"]')
            page.wait_for_timeout(1600)

            # 5) Back to sessions
            page.click('button[data-nav="sessions"]')
            page.wait_for_timeout(1500)

            page.close()
            context.close()
            browser.close()

        videos = list(raw_dir.glob("*.webm"))
        if not videos:
            print("No video produced", file=sys.stderr)
            return 1
        webm = videos[0]
        mp4 = OUT_DIR / "sandglass-demo.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(webm),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(mp4),
            ],
            check=True,
            capture_output=True,
        )
        cleanup_demo_secrets()
        print(mp4)
        return 0
    finally:
        cleanup_demo_secrets()
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except Exception:
                server.kill()


if __name__ == "__main__":
    raise SystemExit(main())
