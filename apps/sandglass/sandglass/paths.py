from __future__ import annotations

import os
import platform
import sys
from pathlib import Path


def app_root() -> Path:
    """Install / source root (apps/sandglass), or PyInstaller bundle root."""
    if getattr(sys, "frozen", False):
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
    root = app_root() / "runtime"
    candidates = [
        root / runtime_triplet() / "bin",
        root / "bin",
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return None


def _homebrew_bins() -> list[str]:
    extras: list[str] = []
    for p in (
        "/opt/homebrew/bin",
        "/usr/local/bin",
        str(Path.home() / ".local" / "bin"),
        str(Path.home() / "homebrew" / "bin"),
    ):
        # include even if missing yet — we may install into ~/.local/bin
        if Path(p).is_dir() or p.endswith("/.local/bin"):
            Path(p).mkdir(parents=True, exist_ok=True)
            extras.append(p)
    return extras


def ensure_tool_path() -> None:
    """
    GUI/.app launches often have a minimal PATH without Homebrew.
    Always prepend bundled runtime + common brew locations.
    """
    parts: list[str] = []
    bundled = bundled_runtime_dir()
    if bundled:
        parts.append(str(bundled))
        os.environ.setdefault("SANDGLASS_RUNTIME_BIN", str(bundled))
    parts.extend(_homebrew_bins())
    current = os.environ.get("PATH", "")
    for p in reversed(parts):
        if p and p not in current.split(os.pathsep):
            current = p + os.pathsep + current
        elif p and not current.startswith(p + os.pathsep) and current != p:
            # move to front
            bits = [x for x in current.split(os.pathsep) if x and x != p]
            current = os.pathsep.join([p, *bits])
    os.environ["PATH"] = current


def prepend_bundled_path() -> Path | None:
    ensure_tool_path()
    return bundled_runtime_dir()


def has_bundled_runtime() -> bool:
    bin_dir = bundled_runtime_dir()
    if not bin_dir:
        return False
    names = ("enclave", "docker", "colima")
    return any((bin_dir / n).exists() or (bin_dir / f"{n}.exe").exists() for n in names)


def which_tool(name: str) -> str | None:
    """Resolve a tool after PATH fix; also probe well-known absolute paths."""
    ensure_tool_path()
    import shutil

    found = shutil.which(name)
    if found:
        return found
    for base in _homebrew_bins():
        cand = Path(base) / name
        if cand.is_file() and os.access(cand, os.X_OK):
            return str(cand)
    bundled = bundled_runtime_dir()
    if bundled:
        cand = bundled / name
        if cand.is_file() and os.access(cand, os.X_OK):
            return str(cand)
    return None
