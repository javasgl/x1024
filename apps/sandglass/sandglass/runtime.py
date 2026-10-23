from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any


def _run(args: list[str], timeout: float = 8) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


@dataclass
class RuntimeStatus:
    """Preferred container runtime for shipped Sandglass: Colima (not Docker Desktop)."""

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


def _colima_status() -> tuple[bool, bool, str]:
    """Returns (installed, running, detail)."""
    if not shutil.which("colima"):
        return False, False, "未安装 Colima"
    try:
        out = _run(["colima", "status", "--json"], timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            try:
                data = json.loads(out.stdout)
                # status field varies by colima version
                status = str(data.get("status") or data.get("Status") or "").lower()
                running = status in {"running", "active"} or bool(data.get("display_name"))
                # fallback: if json parses and exit 0, often means running
                if not status and out.returncode == 0:
                    running = True
                return True, running, out.stdout.strip()[:200]
            except json.JSONDecodeError:
                pass
        # plain text: "colima is running" / "colima is not running"
        text_out = _run(["colima", "status"], timeout=5)
        text = (text_out.stdout + text_out.stderr).lower()
        if "is running" in text or "running" in text and "not running" not in text:
            return True, True, (text_out.stdout or text_out.stderr).strip()[:200]
        return True, False, (text_out.stdout or text_out.stderr or "Colima 未运行").strip()[:200]
    except subprocess.TimeoutExpired:
        return True, False, "colima status 超时"
    except Exception as e:  # noqa: BLE001
        return True, False, str(e)


def _docker_engine_ok() -> tuple[bool, str]:
    if not shutil.which("docker"):
        return False, "未找到 docker CLI（安装 Colima 时请同时安装：brew install docker）"
    try:
        out = _run(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=3)
        if out.returncode == 0:
            return True, f"引擎就绪（Docker API {out.stdout.strip()}）"
        return False, f"引擎未就绪: {out.stderr.strip() or out.stdout.strip()}"
    except subprocess.TimeoutExpired:
        return False, "docker info 超时（请先启动 Colima：colima start）"
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def detect_runtime() -> RuntimeStatus:
    hints: list[str] = []
    colima_installed, colima_running, colima_detail = _colima_status()
    docker_ok, docker_msg = _docker_engine_ok()
    docker_cli = bool(shutil.which("docker"))
    podman = bool(shutil.which("podman"))

    # Prefer Colima as the product runtime.
    if colima_installed:
        if colima_running and docker_ok:
            return RuntimeStatus(
                ready=True,
                kind="colima",
                message=f"Colima 运行中 · {docker_msg}",
                colima_installed=True,
                colima_running=True,
                docker_cli=docker_cli,
                hints=[],
            )
        if colima_running and not docker_ok:
            hints.append("Colima 已开，但 docker CLI 连不上引擎；确认已安装 docker：brew install docker")
            return RuntimeStatus(
                ready=False,
                kind="colima",
                message=f"Colima 已开，引擎不可用 · {docker_msg}",
                colima_installed=True,
                colima_running=True,
                docker_cli=docker_cli,
                hints=hints,
            )
        hints.append("启动轻量容器：在「状态」页点击「启动 Colima」，或终端执行 colima start")
        return RuntimeStatus(
            ready=False,
            kind="colima",
            message=f"Colima 已安装但未运行 · {colima_detail}",
            colima_installed=True,
            colima_running=False,
            docker_cli=docker_cli,
            hints=hints,
        )

    # Fallback: any working docker (OrbStack / Desktop / etc.) — usable but not preferred for shipping.
    if docker_ok:
        hints.append("检测到非 Colima 的 Docker 引擎。正式分发推荐 Colima（更轻、无独立 Desktop UI）")
        return RuntimeStatus(
            ready=True,
            kind="docker",
            message=docker_msg,
            colima_installed=False,
            colima_running=False,
            docker_cli=True,
            hints=hints,
        )

    if podman:
        hints.append("检测到 Podman。可配置 Enclave --backend podman；产品默认仍推荐 Colima")
        return RuntimeStatus(
            ready=False,
            kind="podman",
            message="Podman 在 PATH 上，但默认健康检查走 Docker API",
            colima_installed=False,
            colima_running=False,
            docker_cli=docker_cli,
            hints=hints,
        )

    from .paths import has_bundled_runtime

    if has_bundled_runtime():
        hints.append("已检测到 App 内置运行时，正在尝试自动启动 Colima…")
    else:
        hints.append(
            "开发模式：尚未打包内置引擎。可临时执行 brew install colima docker && colima start"
        )
        hints.append("正式分发将自带 Colima+Enclave，用户无需手动安装")
    return RuntimeStatus(
        ready=False,
        kind="none",
        message="未找到可用容器运行时",
        colima_installed=False,
        colima_running=False,
        docker_cli=docker_cli,
        hints=hints,
    )


def ensure_colima(cpu: int = 2, memory: int = 4) -> dict[str, Any]:
    """Start Colima if installed and not running. Intended for GUI one-click."""
    if not shutil.which("colima"):
        return {
            "ok": False,
            "message": "未安装 Colima。请执行：brew install colima docker",
        }
    status = detect_runtime()
    if status.colima_running and status.ready:
        return {"ok": True, "message": "Colima 已在运行"}

    try:
        # Default profile: modest resources for agent sandboxes
        out = subprocess.run(
            [
                "colima",
                "start",
                "--cpu",
                str(cpu),
                "--memory",
                str(memory),
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if out.returncode != 0:
            return {
                "ok": False,
                "message": (out.stderr or out.stdout or "colima start 失败").strip()[:500],
            }
        after = detect_runtime()
        return {
            "ok": after.ready,
            "message": after.message if after.ready else (out.stdout or "已执行 colima start，请重新检测").strip()[:500],
            "runtime": after.to_dict(),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "message": "colima start 超时（首次启动会下载 Linux 镜像，请再试一次）"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": str(e)}
