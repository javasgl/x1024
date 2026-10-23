from __future__ import annotations

import os
import signal
from dataclasses import dataclass
from pathlib import Path

from .enclave import enclave_command
from .paths import ensure_tool_path


@dataclass
class PtyHandle:
    pid: int
    master_fd: int
    task: asyncio.Task | None = None


def _child_env() -> dict[str, str]:
    """Ensure sandboxed enclave can find docker / colima from GUI-launched apps."""
    ensure_tool_path()
    env = os.environ.copy()
    extras = [
        "/opt/homebrew/bin",
        "/usr/local/bin",
        str(Path.home() / ".local" / "bin"),
    ]
    path = env.get("PATH", "")
    for p in reversed(extras):
        if p not in path.split(os.pathsep):
            path = p + os.pathsep + path
    env["PATH"] = path
    env.setdefault("TERM", "xterm-256color")
    # Prefer colima docker context when present
    try:
        import subprocess

        out = subprocess.run(
            ["docker", "context", "show"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if out.returncode == 0 and out.stdout.strip():
            env["DOCKER_CONTEXT"] = out.stdout.strip()
    except Exception:  # noqa: BLE001
        pass
    return env


class PtyManager:
    def __init__(self) -> None:
        self._sessions: dict[str, PtyHandle] = {}
        self._seq = 0

    def start(self, project_dir: str, tool: str, cols: int = 120, rows: int = 36) -> str:
        ensure_tool_path()
        bin_path = enclave_command()
        if not os.path.isdir(project_dir):
            raise RuntimeError(f"项目目录不存在: {project_dir}")

        master, slave = os.openpty()
        try:
            import fcntl
            import struct
            import termios

            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(master, termios.TIOCSWINSZ, winsize)
        except Exception:  # noqa: BLE001
            pass

        env = _child_env()
        pid = os.fork()
        if pid == 0:
            try:
                os.close(master)
                os.setsid()
                os.dup2(slave, 0)
                os.dup2(slave, 1)
                os.dup2(slave, 2)
                if slave > 2:
                    os.close(slave)
                os.chdir(project_dir)
                # Run agent INSIDE Enclave sandbox; TUI is attached to this PTY (shown in App)
                os.execvpe(
                    bin_path,
                    [bin_path, "--tool", tool],
                    env,
                )
            except Exception as e:  # noqa: BLE001
                os.write(2, f"exec failed: {e}\n".encode())
                os._exit(1)

        os.close(slave)
        import fcntl

        flags = fcntl.fcntl(master, fcntl.F_GETFL)
        fcntl.fcntl(master, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        self._seq += 1
        sid = f"pty-{self._seq}"
        self._sessions[sid] = PtyHandle(pid=pid, master_fd=master)
        return sid

    def write(self, sid: str, data: bytes) -> None:
        handle = self._sessions.get(sid)
        if not handle:
            raise RuntimeError("会话不存在")
        os.write(handle.master_fd, data)

    def resize(self, sid: str, cols: int, rows: int) -> None:
        handle = self._sessions.get(sid)
        if not handle:
            return
        try:
            import fcntl
            import struct
            import termios

            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(handle.master_fd, termios.TIOCSWINSZ, winsize)
            os.kill(handle.pid, signal.SIGWINCH)
        except Exception:  # noqa: BLE001
            pass

    def kill(self, sid: str) -> None:
        handle = self._sessions.pop(sid, None)
        if not handle:
            return
        try:
            os.kill(handle.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            os.close(handle.master_fd)
        except OSError:
            pass

    def get_fd(self, sid: str) -> int | None:
        handle = self._sessions.get(sid)
        return handle.master_fd if handle else None

    def get_pid(self, sid: str) -> int | None:
        handle = self._sessions.get(sid)
        return handle.pid if handle else None
