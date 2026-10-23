mod enclave;
mod pty;
mod secrets;

use enclave::{HealthStatus, SessionInfo, ToolInfo};
use parking_lot::Mutex;
use pty::PtyManager;
use std::sync::Arc;
use tauri::Manager;

struct AppState {
    ptys: Arc<Mutex<PtyManager>>,
}

#[tauri::command]
fn check_health() -> HealthStatus {
    enclave::check_health()
}

#[tauri::command]
fn list_sessions(include_stopped: bool) -> Result<Vec<SessionInfo>, String> {
    enclave::list_sessions(include_stopped)
}

#[tauri::command]
fn stop_session(name: String) -> Result<(), String> {
    enclave::stop_session(&name)
}

#[tauri::command]
fn list_tools() -> Result<Vec<ToolInfo>, String> {
    enclave::list_tools()
}

#[tauri::command]
fn write_secrets(anthropic_key: Option<String>, openai_key: Option<String>) -> Result<String, String> {
    secrets::write_secrets(anthropic_key, openai_key)
}

#[tauri::command]
fn read_secret_status() -> Result<secrets::SecretStatus, String> {
    secrets::read_secret_status()
}

#[tauri::command]
fn start_session(
    app: tauri::AppHandle,
    state: tauri::State<'_, AppState>,
    project_dir: String,
    tool: String,
    cols: u16,
    rows: u16,
) -> Result<String, String> {
    let mut ptys = state.ptys.lock();
    ptys.start(app, project_dir, tool, cols, rows)
}

#[tauri::command]
fn pty_write(state: tauri::State<'_, AppState>, id: String, data: String) -> Result<(), String> {
    state.ptys.lock().write(&id, data.as_bytes())
}

#[tauri::command]
fn pty_resize(state: tauri::State<'_, AppState>, id: String, cols: u16, rows: u16) -> Result<(), String> {
    state.ptys.lock().resize(&id, cols, rows)
}

#[tauri::command]
fn pty_kill(state: tauri::State<'_, AppState>, id: String) -> Result<(), String> {
    state.ptys.lock().kill(&id)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(AppState {
            ptys: Arc::new(Mutex::new(PtyManager::new())),
        })
        .invoke_handler(tauri::generate_handler![
            check_health,
            list_sessions,
            stop_session,
            list_tools,
            write_secrets,
            read_secret_status,
            start_session,
            pty_write,
            pty_resize,
            pty_kill,
        ])
        .setup(|app| {
            let _ = app.get_webview_window("main");
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Sandglass");
}
