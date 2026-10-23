from __future__ import annotations

import json
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .paths import ensure_tool_path, which_tool


def _run(args: list[str], timeout: float = 8) -> subprocess.CompletedProcess[str]:
    ensure_tool_path()
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


@dataclass
class RuntimeStatus:
    ready: bool
    kind: str  # colima | docker | podman | none
    message: str
    colima_installed: bool
    colima_running: bool
    docker_cli: bool
    hints: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "kind": self.kind,
            "message": self.message,
            "colimaInstalled": self.colima_installed,
            "colimaRunning": self.colima_running,
            "dockerCli": self.docker_cli,
            "hints": self.hints,
        }


def _user_msg_engine_ready() -> str:
    return "沙箱引擎运行中"


def _colima_status() -> tuple[bool, bool, str]:
    colima = which_tool("colima")
    if not colima:
        return False, False, "未安装"
    try:
        out = _run([colima, "status", "--json"], timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            try:
                data = json.loads(out.stdout)
                status = str(data.get("status") or data.get("Status") or "").lower()
                running = status in {"running", "active"} or bool(data.get("display_name"))
                if not status and out.returncode == 0:
                    running = True
                return True, running, out.stdout.strip()[:200]
            except json.JSONDecodeError:
                pass
        text_out = _run([colima, "status"], timeout=5)
        text = (text_out.stdout + text_out.stderr).lower()
        if "not running" in text:
            return True, False, "未运行"
        if "is running" in text or ("running" in text and "not running" not in text):
            return True, True, "运行中"
        return True, False, "未运行"
    except subprocess.TimeoutExpired:
        return True, False, "状态检测超时"
    except Exception as e:  # noqa: BLE001
        return True, False, str(e)


def _docker_engine_ok() -> tuple[bool, str]:
    docker = which_tool("docker")
    if not docker:
        return False, "引擎客户端缺失"
    try:
        out = _run([docker, "info", "--format", "{{.ServerVersion}}"], timeout=3)
        if out.returncode == 0:
            return True, out.stdout.strip() or "ok"
        return False, "引擎未响应"
    except subprocess.TimeoutExpired:
        return False, "引擎响应超时"
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def detect_runtime() -> RuntimeStatus:
    ensure_tool_path()
    hints: list[str] = []
    colima_installed, colima_running, _ = _colima_status()
    docker_ok, _ = _docker_engine_ok()
    docker_cli = bool(which_tool("docker"))
    podman = bool(which_tool("podman"))

    if colima_installed:
        if colima_running and docker_ok:
            return RuntimeStatus(
                ready=True,
                kind="colima",
                message=_user_msg_engine_ready(),
                colima_installed=True,
                colima_running=True,
                docker_cli=docker_cli,
                hints=[],
            )
        if colima_running and not docker_ok:
            hints.append("沙箱引擎已启动，但尚未完全就绪。请再点一次「启动沙箱引擎」。")
            return RuntimeStatus(
                ready=False,
                kind="colima",
                message="沙箱引擎启动中，请稍候…",
                colima_installed=True,
                colima_running=True,
                docker_cli=docker_cli,
                hints=hints,
            )
        hints.append("点击「启动沙箱引擎」即可自动拉起。")
        return RuntimeStatus(
            ready=False,
            kind="colima",
            message="沙箱引擎已安装，尚未启动",
            colima_installed=True,
            colima_running=False,
            docker_cli=docker_cli,
            hints=hints,
        )

    if docker_ok:
        return RuntimeStatus(
            ready=True,
            kind="docker",
            message=_user_msg_engine_ready(),
            colima_installed=False,
            colima_running=False,
            docker_cli=True,
            hints=[],
        )

    if docker_cli:
        hints.append("将自动安装并启动轻量沙箱引擎（首次可能需要几分钟）。")
        return RuntimeStatus(
            ready=False,
            kind="docker",
            message="沙箱引擎未运行",
            colima_installed=False,
            colima_running=False,
            docker_cli=True,
            hints=hints,
        )

    if podman:
        hints.append("请点击「启动沙箱引擎」。")
        return RuntimeStatus(
            ready=False,
            kind="podman",
            message="沙箱引擎未就绪",
            colima_installed=False,
            colima_running=False,
            docker_cli=docker_cli,
            hints=hints,
        )

    from .paths import has_bundled_runtime

    if has_bundled_runtime():
        hints.append("正在准备内置沙箱引擎…")
    else:
        hints.append("首次启动将自动安装沙箱引擎组件（需要 Homebrew）。")
    return RuntimeStatus(
        ready=False,
        kind="none",
        message="沙箱引擎未就绪",
        colima_installed=False,
        colima_running=False,
        docker_cli=docker_cli,
        hints=hints,
    )


def _brew() -> str | None:
    return which_tool("brew")


def _brew_install(packages: list[str]) -> dict[str, Any]:
    brew = _brew()
    if not brew:
        return {
            "ok": False,
            "message": "无法自动安装沙箱引擎：未找到 Homebrew。请先安装 https://brew.sh 后重试。",
        }
    try:
        out = subprocess.run(
            [brew, "install", *packages],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if out.returncode != 0:
            err = (out.stderr or out.stdout or "brew install 失败").strip()[:400]
            return {"ok": False, "message": f"自动安装失败：{err}"}
        ensure_tool_path()
        return {"ok": True, "message": "组件已安装"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "message": "自动安装超时，请稍后重试「启动沙箱引擎」。"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": f"自动安装异常：{e}"}


def _install_enclave_binary() -> dict[str, Any]:
    """Enclave is not on Homebrew; install rolling macOS/linux binary into ~/.local/bin."""
    import platform

    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "darwin":
        asset = "enclave-darwin-arm64" if machine in {"arm64", "aarch64"} else "enclave-darwin-amd64"
    elif system == "linux":
        asset = "enclave-linux-arm64" if machine in {"arm64", "aarch64"} else "enclave-linux-amd64"
    else:
        return {"ok": False, "message": f"暂不支持在 {system} 上自动安装 Enclave"}

    dest_dir = Path.home() / ".local" / "bin"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "enclave"
    url = f"https://github.com/eclipse-enclave/enclave/releases/download/rolling/{asset}"
    try:
        urllib.request.urlretrieve(url, dest)
        dest.chmod(0o755)
        if system == "darwin":
            subprocess.run(["xattr", "-d", "com.apple.quarantine", str(dest)], capture_output=True)
        ensure_tool_path()
        if which_tool("enclave"):
            return {"ok": True, "message": "Enclave 已安装"}
        return {"ok": False, "message": "Enclave 下载完成但无法执行"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": f"Enclave 自动安装失败：{e}"}


def ensure_engine_components() -> dict[str, Any]:
    """Install colima/docker via brew; Enclave via GitHub rolling release."""
    ensure_tool_path()
    installed: list[str] = []

    brew_pkgs: list[str] = []
    if not which_tool("colima"):
        brew_pkgs.append("colima")
    if not which_tool("docker"):
        brew_pkgs.append("docker")

    if brew_pkgs:
        result = _brew_install(brew_pkgs)
        if not result.get("ok"):
            return result
        installed.extend(brew_pkgs)

    if not which_tool("enclave"):
        enc = _install_enclave_binary()
        if not enc.get("ok"):
            return enc
        installed.append("enclave")

    return {"ok": True, "message": "组件已齐全", "installed": installed}


def ensure_colima(cpu: int = 2, memory: int = 4) -> dict[str, Any]:
    """Install if needed, then start Colima. Product-facing one-click."""
    ensure_tool_path()

    # 1) Make sure binaries exist
    comps = ensure_engine_components()
    if not comps.get("ok"):
        return comps

    colima = which_tool("colima")
    if not colima:
        return {
            "ok": False,
            "message": "沙箱引擎安装后仍未找到，请重启应用后再试。",
        }

    status = detect_runtime()
    if status.colima_running and status.ready:
        return {"ok": True, "message": "沙箱引擎已在运行"}

    try:
        out = subprocess.run(
            [colima, "start", "--cpu", str(cpu), "--memory", str(memory)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if out.returncode != 0:
            raw = (out.stderr or out.stdout or "启动失败").strip()[:500]
            return {"ok": False, "message": f"沙箱引擎启动失败：{raw}"}
        after = detect_runtime()
        return {
            "ok": after.ready,
            "message": "沙箱引擎已启动" if after.ready else "已请求启动，请稍候再点「重新检测」",
            "runtime": after.to_dict(),
            "bootstrap": comps,
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "message": "沙箱引擎启动超时（首次需下载虚拟机组件，请再试一次）",
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": f"沙箱引擎启动异常：{e}"}
