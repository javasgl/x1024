use serde::{Deserialize, Serialize};
use std::fs;
use std::io::Write;
use std::path::PathBuf;

#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct SecretStatus {
    pub path: String,
    pub has_anthropic: bool,
    pub has_openai: bool,
}

fn secrets_path() -> Result<PathBuf, String> {
    let home = dirs::home_dir().ok_or_else(|| "无法定位用户主目录".to_string())?;
    Ok(home
        .join(".local")
        .join("state")
        .join("enclave")
        .join("secrets")
        .join("global.env"))
}

fn parse_env(content: &str) -> (bool, bool) {
    let mut has_anthropic = false;
    let mut has_openai = false;
    for line in content.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        if let Some((k, v)) = line.split_once('=') {
            let v = v.trim().trim_matches('"');
            if !v.is_empty() {
                match k.trim() {
                    "ANTHROPIC_API_KEY" => has_anthropic = true,
                    "OPENAI_API_KEY" => has_openai = true,
                    _ => {}
                }
            }
        }
    }
    (has_anthropic, has_openai)
}

pub fn read_secret_status() -> Result<SecretStatus, String> {
    let path = secrets_path()?;
    if !path.exists() {
        return Ok(SecretStatus {
            path: path.display().to_string(),
            has_anthropic: false,
            has_openai: false,
        });
    }
    let content = fs::read_to_string(&path).map_err(|e| format!("读取 secrets 失败: {e}"))?;
    let (has_anthropic, has_openai) = parse_env(&content);
    Ok(SecretStatus {
        path: path.display().to_string(),
        has_anthropic,
        has_openai,
    })
}

pub fn write_secrets(
    anthropic_key: Option<String>,
    openai_key: Option<String>,
) -> Result<String, String> {
    let path = secrets_path()?;
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| format!("创建 secrets 目录失败: {e}"))?;
    }

    let existing = if path.exists() {
        fs::read_to_string(&path).unwrap_or_default()
    } else {
        String::new()
    };

    let mut map = std::collections::BTreeMap::<String, String>::new();
    for line in existing.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        if let Some((k, v)) = line.split_once('=') {
            map.insert(k.trim().to_string(), v.trim().trim_matches('"').to_string());
        }
    }

    if let Some(k) = anthropic_key {
        let k = k.trim().to_string();
        if k.is_empty() {
            map.remove("ANTHROPIC_API_KEY");
        } else {
            map.insert("ANTHROPIC_API_KEY".into(), k);
        }
    }
    if let Some(k) = openai_key {
        let k = k.trim().to_string();
        if k.is_empty() {
            map.remove("OPENAI_API_KEY");
        } else {
            map.insert("OPENAI_API_KEY".into(), k);
        }
    }

    let mut file = fs::File::create(&path).map_err(|e| format!("写入 secrets 失败: {e}"))?;
    writeln!(
        file,
        "# Managed by Sandglass — keys stay on the host, not inside the sandbox agent process"
    )
    .map_err(|e| e.to_string())?;
    for (k, v) in map {
        writeln!(file, "{k}={v}").map_err(|e| e.to_string())?;
    }

    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = fs::set_permissions(&path, fs::Permissions::from_mode(0o600));
    }

    Ok(path.display().to_string())
}
