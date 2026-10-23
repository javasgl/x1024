from __future__ import annotations

import os
from pathlib import Path


def secrets_path() -> Path:
    home = Path.home()
    return home / ".local" / "state" / "enclave" / "secrets" / "global.env"


def read_secret_status() -> dict:
    path = secrets_path()
    has_anthropic = False
    has_openai = False
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            v = v.strip().strip('"')
            if not v:
                continue
            if k.strip() == "ANTHROPIC_API_KEY":
                has_anthropic = True
            elif k.strip() == "OPENAI_API_KEY":
                has_openai = True
    return {
        "path": str(path),
        "hasAnthropic": has_anthropic,
        "hasOpenai": has_openai,
    }


def write_secrets(anthropic_key: str | None = None, openai_key: str | None = None) -> str:
    path = secrets_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    data: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip().strip('"')

    if anthropic_key is not None:
        k = anthropic_key.strip()
        if k:
            data["ANTHROPIC_API_KEY"] = k
        else:
            data.pop("ANTHROPIC_API_KEY", None)

    if openai_key is not None:
        k = openai_key.strip()
        if k:
            data["OPENAI_API_KEY"] = k
        else:
            data.pop("OPENAI_API_KEY", None)

    lines = [
        "# Managed by Sandglass — keys stay on the host, not inside the sandbox",
    ]
    for k, v in data.items():
        lines.append(f"{k}={v}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)
    return str(path)
