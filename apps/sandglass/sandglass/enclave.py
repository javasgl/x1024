from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any


@dataclass
class HealthStatus:
    enclave_ok: bool
    enclave_version: str | None
    enclave_path: str | None
    docker_ok: bool
    docker_message: str
    ready: bool
    hints: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "enclaveOk": self.enclave_ok,
            "enclaveVersion": self.enclave_version,
            "enclavePath": self.enclave_path,
            "dockerOk": self.docker_ok,
            "dockerMessage": self.docker_message,
            "ready": self.ready,
            "hints": self.hints,
        }


def _run(args: list[str], timeout: float = 8) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def enclave_bin() -> str | None:
    return shutil.which("enclave")


def check_health() -> HealthStatus:
    hints: list[str] = []
    path = enclave_bin()
    enclave_ok = False
    version: str | None = None

    if not path:
        hints.append("安装 Enclave：brew install eclipse-enclave")
    else:
        try:
            out = _run([path, "version", "--json"])
            if out.returncode == 0 and out.stdout.strip():
                try:
                    data = json.loads(out.stdout)
                    version = str(data.get("version") or data.get("Version") or out.stdout.strip())
                except json.JSONDecodeError:
                    version = out.stdout.strip()
                enclave_ok = True
            else:
                out2 = _run([path, "version"])
                if out2.returncode == 0:
                    version = (out2.stdout or out2.stderr).strip()
                    enclave_ok = True
                else:
                    hints.append(f"enclave version 失败: {(out.stderr or out2.stderr).strip()}")
        except Exception as e:  # noqa: BLE001
            hints.append(f"无法执行 enclave: {e}")

    docker_ok = False
    docker_message = "未找到 docker"
    if shutil.which("docker"):
        try:
            out = _run(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=3)
            if out.returncode == 0:
                docker_ok = True
                docker_message = f"Docker {out.stdout.strip()}"
            else:
                docker_message = f"Docker 未就绪: {out.stderr.strip()}"
                hints.append("请启动 Docker Desktop")
        except subprocess.TimeoutExpired:
            docker_message = "Docker 无响应（请确认 Docker Desktop 已启动）"
            hints.append("请启动 Docker Desktop")
        except Exception as e:  # noqa: BLE001
            docker_message = str(e)
            hints.append("请启动 Docker Desktop")
    else:
        hints.append("未找到 docker，请安装 Docker Desktop")

    return HealthStatus(
        enclave_ok=enclave_ok,
        enclave_version=version,
        enclave_path=path,
        docker_ok=docker_ok,
        docker_message=docker_message,
        ready=enclave_ok and docker_ok,
        hints=hints,
    )


def list_sessions(include_stopped: bool = False) -> list[dict[str, Any]]:
    path = enclave_bin()
    if not path:
        raise RuntimeError("未找到 enclave。请先安装：brew install eclipse-enclave")
    args = [path, "ps", "--json"]
    if include_stopped:
        args.append("--all")
    out = _run(args)
    if out.returncode != 0:
        raise RuntimeError(f"enclave ps 错误: {out.stderr.strip()}")
    raw = out.stdout.strip()
    if not raw or raw == "null":
        return []
    data = json.loads(raw)
    if isinstance(data, dict):
        data = [data]
    sessions = []
    for v in data:
        sessions.append(
            {
                "name": v.get("name") or v.get("Name") or "unknown",
                "tool": v.get("tool") or v.get("Tool"),
                "projectDir": v.get("projectDir") or v.get("project_dir"),
                "status": v.get("status") or v.get("Status"),
                "sessionName": v.get("sessionName") or v.get("session_name"),
                "background": v.get("background"),
                "createdAt": v.get("createdAt") or v.get("created_at"),
            }
        )
    return sessions


def stop_session(name: str) -> None:
    path = enclave_bin()
    if not path:
        raise RuntimeError("未找到 enclave")
    out = _run([path, "stop", name])
    if out.returncode != 0:
        raise RuntimeError(f"enclave stop 错误: {out.stderr.strip()}")


def list_tools() -> list[dict[str, str]]:
    defaults = [
        {"id": "claude", "label": "Claude Code"},
        {"id": "codex", "label": "Codex"},
        {"id": "opencode", "label": "OpenCode"},
    ]
    path = enclave_bin()
    if not path:
        return defaults
    try:
        out = _run([path, "tools"])
        if out.returncode != 0:
            return defaults
        text = out.stdout.lower()
        found = [t for t in defaults if t["id"] in text]
        return found or defaults
    except Exception:  # noqa: BLE001
        return defaults


def enclave_command() -> str:
    path = enclave_bin()
    if not path:
        raise RuntimeError("未找到 enclave。请先安装：brew install eclipse-enclave")
    return path
