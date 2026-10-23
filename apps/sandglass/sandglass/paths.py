from __future__ import annotations

import os
import platform
import sys
from pathlib import Path


def app_root() -> Path:
    """Install / source root (apps/sandglass), or PyInstaller bundle root."""
    if getattr(sys, "frozen", False):
        # onedir / .app: binaries and datas live next to the executable or in _MEIPASS
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def runtime_triplet() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "darwin":
        arch = "arm64" if machine in {"arm64", "aarch64"} else "amd64"
        return f"darwin-{arch}"
    if system == "linux":
        arch = "arm64" if machine in {"arm64", "aarch64"} else "amd64"
        return f"linux-{arch}"
    return f"{system}-{machine}"


def bundled_runtime_dir() -> Path | None:
    """
    Preferred layout:
      <app_root>/runtime/<triplet>/bin/{enclave,docker,colima,...}
    Also accept:
      <app_root>/runtime/bin/...
    """
    root = app_root() / "runtime"
    candidates = [
        root / runtime_triplet() / "bin",
        root / "bin",
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return None


def prepend_bundled_path() -> Path | None:
    """Put bundled engine binaries first on PATH. Returns bin dir if used."""
    bin_dir = bundled_runtime_dir()
    if not bin_dir:
        return None
    path = os.environ.get("PATH", "")
    prefix = str(bin_dir)
    if not path.startswith(prefix + os.pathsep) and path != prefix:
        os.environ["PATH"] = prefix + os.pathsep + path
    # Help Colima/Lima find sibling tools when bundled together
    os.environ.setdefault("SANDGLASS_RUNTIME_BIN", prefix)
    return bin_dir


def has_bundled_runtime() -> bool:
    bin_dir = bundled_runtime_dir()
    if not bin_dir:
        return False
    # Consider bundled if at least docker or colima or enclave exists
    names = ("enclave", "docker", "colima")
    return any((bin_dir / n).exists() or (bin_dir / f"{n}.exe").exists() for n in names)
