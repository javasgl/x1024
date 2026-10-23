from __future__ import annotations

from typing import Any

from .paths import ensure_tool_path, has_bundled_runtime, prepend_bundled_path
from .runtime import detect_runtime, ensure_colima


def prepare_engine() -> dict[str, Any]:
    """
    Desktop / one-click startup:
    1) Fix PATH (Homebrew + bundled)
    2) Install missing engine bits via brew if needed
    3) Start Colima
    """
    ensure_tool_path()
    bundled = prepend_bundled_path()
    mode = "bundled" if has_bundled_runtime() else "system"

    rt = detect_runtime()
    started = None
    if not rt.ready:
        started = ensure_colima()
        rt = detect_runtime()

    return {
        "mode": mode,
        "bundledBin": str(bundled) if bundled else None,
        "runtime": rt.to_dict(),
        "ensureColima": started,
        "ready": rt.ready,
        "message": (
            "沙箱引擎已就绪"
            if rt.ready
            else (started or {}).get("message") or rt.message or "沙箱引擎未就绪"
        ),
    }
