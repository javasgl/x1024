from __future__ import annotations

from typing import Any

from .paths import has_bundled_runtime, prepend_bundled_path
from .runtime import detect_runtime, ensure_colima


def prepare_engine() -> dict[str, Any]:
    """
    Called at desktop app startup:
    1) Prefer binaries shipped inside the app
    2) Ensure Colima is up so Enclave can talk to a Docker API
    """
    bundled = prepend_bundled_path()
    mode = "bundled" if has_bundled_runtime() else "system"

    rt = detect_runtime()
    started = None
    if not rt.ready:
        # Auto-start Colima — core of "double-click, no manual setup"
        started = ensure_colima()
        rt = detect_runtime()

    return {
        "mode": mode,
        "bundledBin": str(bundled) if bundled else None,
        "runtime": rt.to_dict(),
        "ensureColima": started,
        "ready": rt.ready,
        "message": (
            "内置沙箱引擎已就绪"
            if rt.ready and mode == "bundled"
            else (
                "沙箱引擎已就绪"
                if rt.ready
                else (started or {}).get("message")
                or rt.message
                or "沙箱引擎未就绪"
            )
        ),
    }
