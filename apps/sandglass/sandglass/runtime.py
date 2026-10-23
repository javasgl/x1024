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


def _user_msg_engine_ready(detail: str = "") -> str:
    return "沙箱引擎运行中" + (f"（{detail}）" if detail else "")


def _colima_status() -> tuple[bool, bool, str]:
    """Returns (installed, running, detail)."""
    if not shutil.which("colima"):
        return False, False, "未安装"
    try:
        out = _run(["colima", "status", "--json"], timeout=5)
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
        text_out = _run(["colima", "status"], timeout=5)
        text = (text_out.stdout + text_out.stderr).lower()
        if "not running" in text:
            return True, False, (text_out.stdout or text_out.stderr or "未运行").strip()[:200]
        if "is running" in text or ("running" in text and "not running" not in text):
            return True, True, (text_out.stdout or text_out.stderr).strip()[:200]
        return True, False, (text_out.stdout or text_out.stderr or "未运行").strip()[:200]
    except subprocess.TimeoutExpired:
        return True, False, "状态检测超时"
    except Exception as e:  # noqa: BLE001
        return True, False, str(e)


def _docker_engine_ok() -> tuple[bool, str]:
    if not shutil.which("docker"):
        return False, "引擎客户端缺失"
    try:
        out = _run(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=3)
        if out.returncode == 0:
            return True, out.stdout.strip() or "ok"
        return False, "引擎未响应"
    except subprocess.TimeoutExpired:
        return False, "引擎响应超时"
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def detect_runtime() -> RuntimeStatus:
    hints: list[str] = []
    colima_installed, colima_running, colima_detail = _colima_status()
    docker_ok, docker_detail = _docker_engine_ok()
    docker_cli = bool(shutil.which("docker"))
    podman = bool(shutil.which("podman"))

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
            hints.append("沙箱引擎已启动，但尚未完全就绪。请点「启动沙箱引擎」重试。")
            return RuntimeStatus(
                ready=False,
                kind="colima",
                message="沙箱引擎启动中，请稍候…",
                colima_installed=True,
                colima_running=True,
                docker_cli=docker_cli,
                hints=hints,
            )
        hints.append("点击「启动沙箱引擎」即可，无需安装其他软件。")
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

    # docker CLI present but daemon not up — don't confuse users with podman wording
    if docker_cli:
        hints.append("请点击「启动沙箱引擎」。若仍失败，开发环境请先运行 prepare_runtime 脚本。")
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
        hints.append("正在准备内置沙箱引擎，请点「启动沙箱引擎」或稍后重试。")
    else:
        hints.append("开发环境：尚未放入内置引擎。请运行 scripts/prepare_runtime_macos.sh 或安装 colima。")
    return RuntimeStatus(
        ready=False,
        kind="none",
        message="沙箱引擎未就绪",
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
            "message": "内置沙箱引擎不可用。开发期请先运行 prepare_runtime 脚本。",
        }
    status = detect_runtime()
    if status.colima_running and status.ready:
        return {"ok": True, "message": "沙箱引擎已在运行"}

    try:
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
            raw = (out.stderr or out.stdout or "启动失败").strip()[:500]
            return {
                "ok": False,
                "message": f"沙箱引擎启动失败：{raw}",
            }
        after = detect_runtime()
        return {
            "ok": after.ready,
            "message": "沙箱引擎已启动" if after.ready else "已请求启动，请稍候再点「重新检测」",
            "runtime": after.to_dict(),
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "message": "沙箱引擎启动超时（首次可能需要下载组件，请再试一次）",
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": f"沙箱引擎启动异常：{e}"}
