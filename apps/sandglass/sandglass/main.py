from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import enclave, secrets
from .bootstrap import prepare_engine
from .paths import app_root, ensure_tool_path, has_bundled_runtime, prepend_bundled_path
from .pty_session import PtyManager
from .runtime import ensure_colima

ensure_tool_path()
prepend_bundled_path()

ROOT = app_root()
STATIC = ROOT / "static"
if not STATIC.is_dir():
    # Dev / editable fallback
    STATIC = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="Sandglass", version="0.1.0")
ptys = PtyManager()


class StopBody(BaseModel):
    name: str


class SecretsBody(BaseModel):
    anthropicKey: str | None = None
    openaiKey: str | None = None


class StartBody(BaseModel):
    projectDir: str
    tool: str
    cols: int = 120
    rows: int = 36


@app.get("/api/health")
def api_health() -> dict[str, Any]:
    data = enclave.check_health().to_dict()
    data["engineMode"] = "bundled" if has_bundled_runtime() else "system"
    return data


@app.post("/api/runtime/ensure-colima")
def api_ensure_colima() -> dict[str, Any]:
    """Start Colima (bundled or system)."""
    prepend_bundled_path()
    return ensure_colima()


@app.post("/api/runtime/prepare")
def api_prepare_engine() -> dict[str, Any]:
    """Desktop startup: use bundled PATH and auto-start Colima if needed."""
    return prepare_engine()


@app.get("/api/sessions")
def api_sessions(all: bool = False) -> list[dict[str, Any]]:
    try:
        return enclave.list_sessions(include_stopped=all)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/api/sessions/stop")
def api_stop(body: StopBody) -> dict[str, str]:
    try:
        enclave.stop_session(body.name)
        return {"ok": "true"}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/tools")
def api_tools() -> list[dict[str, str]]:
    return enclave.list_tools()


@app.get("/api/secrets")
def api_secrets_status() -> dict[str, Any]:
    return secrets.read_secret_status()


@app.post("/api/secrets")
def api_secrets_write(body: SecretsBody) -> dict[str, str]:
    path = secrets.write_secrets(body.anthropicKey, body.openaiKey)
    return {"path": path}


@app.post("/api/pick-folder")
def api_pick_folder() -> dict[str, str | None]:
    """Native folder dialog (macOS osascript / Tk)."""
    from .pick_folder import pick_folder

    return pick_folder()


@app.post("/api/session/start")
def api_start(body: StartBody) -> dict[str, str]:
    try:
        sid = ptys.start(body.projectDir, body.tool, body.cols, body.rows)
        return {"id": sid}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/api/session/{sid}/kill")
def api_kill(sid: str) -> dict[str, str]:
    ptys.kill(sid)
    return {"ok": "true"}


@app.websocket("/ws/pty/{sid}")
async def ws_pty(websocket: WebSocket, sid: str) -> None:
    await websocket.accept()
    fd = ptys.get_fd(sid)
    if fd is None:
        await websocket.close(code=4000)
        return

    async def reader() -> None:
        loop = asyncio.get_event_loop()

        def _read_chunk() -> bytes | None:
            import select

            try:
                ready, _, _ = select.select([fd], [], [], 0.2)
                if not ready:
                    return b""
                return os.read(fd, 4096)
            except OSError:
                return None

        try:
            while True:
                data = await loop.run_in_executor(None, _read_chunk)
                if data is None:
                    break
                if data:
                    await websocket.send_bytes(data)
                else:
                    # check child still alive
                    pid = ptys.get_pid(sid)
                    if pid is None:
                        break
                    try:
                        os.waitpid(pid, os.WNOHANG)
                    except ChildProcessError:
                        break
        except Exception:  # noqa: BLE001
            pass
        try:
            await websocket.close()
        except Exception:  # noqa: BLE001
            pass

    task = asyncio.create_task(reader())
    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if "bytes" in message and message["bytes"] is not None:
                ptys.write(sid, message["bytes"])
            elif "text" in message and message["text"] is not None:
                text = message["text"]
                if text.startswith("\x00resize:"):
                    # \x00resize:cols,rows
                    try:
                        _, rest = text.split(":", 1)
                        cols_s, rows_s = rest.split(",", 1)
                        ptys.resize(sid, int(cols_s), int(rows_s))
                    except Exception:  # noqa: BLE001
                        pass
                else:
                    ptys.write(sid, text.encode("utf-8", errors="ignore"))
    except WebSocketDisconnect:
        pass
    finally:
        task.cancel()
        ptys.kill(sid)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")


def run() -> None:
    import uvicorn

    uvicorn.run(
        "sandglass.main:app",
        host="127.0.0.1",
        port=8765,
        reload=False,
    )


if __name__ == "__main__":
    run()
