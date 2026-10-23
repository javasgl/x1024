use serde::{Deserialize, Serialize};
use std::process::Command;

#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct HealthStatus {
    pub enclave_ok: bool,
    pub enclave_version: Option<String>,
    pub enclave_path: Option<String>,
    pub docker_ok: bool,
    pub docker_message: String,
    pub ready: bool,
    pub hints: Vec<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct SessionInfo {
    pub name: String,
    pub tool: Option<String>,
    pub project_dir: Option<String>,
    pub status: Option<String>,
    pub session_name: Option<String>,
    pub background: Option<bool>,
    pub created_at: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct ToolInfo {
    pub id: String,
    pub label: String,
}

fn enclave_bin() -> Result<String, String> {
    which::which("enclave")
        .map(|p| p.display().to_string())
        .map_err(|_| {
            "未找到 enclave。请先安装：brew install eclipse-enclave".to_string()
        })
}

pub fn check_health() -> HealthStatus {
    let mut hints = Vec::new();
    let enclave_path = which::which("enclave").ok().map(|p| p.display().to_string());
    let (enclave_ok, enclave_version) = if let Some(ref path) = enclave_path {
        match Command::new(path).args(["version", "--json"]).output() {
            Ok(out) if out.status.success() => {
                let raw = String::from_utf8_lossy(&out.stdout);
                let version = serde_json::from_str::<serde_json::Value>(&raw)
                    .ok()
                    .and_then(|v| {
                        v.get("version")
                            .or_else(|| v.get("Version"))
                            .and_then(|x| x.as_str())
                            .map(|s| s.to_string())
                    })
                    .or_else(|| {
                        let line = String::from_utf8_lossy(&out.stdout);
                        let trimmed = line.trim();
                        if trimmed.is_empty() {
                            Some(String::from_utf8_lossy(&out.stderr).trim().to_string())
                        } else {
                            Some(trimmed.to_string())
                        }
                    });
                (true, version)
            }
            Ok(out) => {
                // Some builds print plain text without --json
                let fallback = Command::new(path).arg("version").output();
                match fallback {
                    Ok(f) if f.status.success() => {
                        let v = String::from_utf8_lossy(&f.stdout).trim().to_string();
                        (true, Some(v))
                    }
                    _ => {
                        hints.push(format!(
                            "enclave version 失败: {}",
                            String::from_utf8_lossy(&out.stderr).trim()
                        ));
                        (false, None)
                    }
                }
            }
            Err(e) => {
                hints.push(format!("无法执行 enclave: {e}"));
                (false, None)
            }
        }
    } else {
        hints.push("安装 Enclave：brew install eclipse-enclave".into());
        (false, None)
    };

    let (docker_ok, docker_message) = match Command::new("docker").args(["info", "--format", "{{.ServerVersion}}"]).output() {
        Ok(out) if out.status.success() => {
            let ver = String::from_utf8_lossy(&out.stdout).trim().to_string();
            (true, format!("Docker {ver}"))
        }
        Ok(out) => {
            hints.push("请启动 Docker Desktop".into());
            (
                false,
                format!(
                    "Docker 未就绪: {}",
                    String::from_utf8_lossy(&out.stderr).trim()
                ),
            )
        }
        Err(_) => {
            hints.push("未找到 docker，请安装 Docker Desktop".into());
            (false, "未找到 docker".into())
        }
    };

    HealthStatus {
        ready: enclave_ok && docker_ok,
        enclave_ok,
        enclave_version,
        enclave_path,
        docker_ok,
        docker_message,
        hints,
    }
}

pub fn list_sessions(include_stopped: bool) -> Result<Vec<SessionInfo>, String> {
    let bin = enclave_bin()?;
    let mut args = vec!["ps", "--json"];
    if include_stopped {
        args.push("--all");
    }
    let out = Command::new(&bin)
        .args(&args)
        .output()
        .map_err(|e| format!("enclave ps 失败: {e}"))?;
    if !out.status.success() {
        return Err(format!(
            "enclave ps 错误: {}",
            String::from_utf8_lossy(&out.stderr).trim()
        ));
    }
    let raw = String::from_utf8_lossy(&out.stdout);
    let trimmed = raw.trim();
    if trimmed.is_empty() || trimmed == "null" {
        return Ok(vec![]);
    }
    let value: serde_json::Value =
        serde_json::from_str(trimmed).map_err(|e| format!("解析 ps JSON 失败: {e}\n{trimmed}"))?;
    let arr = match value {
        serde_json::Value::Array(a) => a,
        other => vec![other],
    };
    Ok(arr
        .into_iter()
        .map(|v| SessionInfo {
            name: v
                .get("name")
                .or_else(|| v.get("Name"))
                .and_then(|x| x.as_str())
                .unwrap_or("unknown")
                .to_string(),
            tool: v
                .get("tool")
                .or_else(|| v.get("Tool"))
                .and_then(|x| x.as_str())
                .map(|s| s.to_string()),
            project_dir: v
                .get("projectDir")
                .or_else(|| v.get("project_dir"))
                .and_then(|x| x.as_str())
                .map(|s| s.to_string()),
            status: v
                .get("status")
                .or_else(|| v.get("Status"))
                .and_then(|x| x.as_str())
                .map(|s| s.to_string()),
            session_name: v
                .get("sessionName")
                .or_else(|| v.get("session_name"))
                .and_then(|x| x.as_str())
                .map(|s| s.to_string()),
            background: v
                .get("background")
                .and_then(|x| x.as_bool()),
            created_at: v
                .get("createdAt")
                .or_else(|| v.get("created_at"))
                .and_then(|x| x.as_str())
                .map(|s| s.to_string()),
        })
        .collect())
}

pub fn stop_session(name: &str) -> Result<(), String> {
    let bin = enclave_bin()?;
    let out = Command::new(&bin)
        .args(["stop", name])
        .output()
        .map_err(|e| format!("enclave stop 失败: {e}"))?;
    if !out.status.success() {
        return Err(format!(
            "enclave stop 错误: {}",
            String::from_utf8_lossy(&out.stderr).trim()
        ));
    }
    Ok(())
}

pub fn list_tools() -> Result<Vec<ToolInfo>, String> {
    // Prefer enclave tools output; fall back to built-in MVP set.
    let defaults = vec![
        ToolInfo {
            id: "claude".into(),
            label: "Claude Code".into(),
        },
        ToolInfo {
            id: "codex".into(),
            label: "Codex".into(),
        },
        ToolInfo {
            id: "opencode".into(),
            label: "OpenCode".into(),
        },
    ];

    let Ok(bin) = enclave_bin() else {
        return Ok(defaults);
    };

    let out = Command::new(&bin).args(["tools"]).output();
    let Ok(out) = out else {
        return Ok(defaults);
    };
    if !out.status.success() {
        return Ok(defaults);
    }
    let text = String::from_utf8_lossy(&out.stdout);
    let mut found = Vec::new();
    for line in text.lines() {
        let lower = line.to_lowercase();
        for d in &defaults {
            if lower.contains(&d.id) && !found.iter().any(|t: &ToolInfo| t.id == d.id) {
                found.push(d.clone());
            }
        }
    }
    if found.is_empty() {
        Ok(defaults)
    } else {
        Ok(found)
    }
}

pub fn enclave_command() -> Result<String, String> {
    enclave_bin()
}
