use crate::enclave;
use portable_pty::{native_pty_system, CommandBuilder, MasterPty, PtySize};
use std::collections::HashMap;
use std::io::{Read, Write};
use std::sync::atomic::{AtomicU64, Ordering};
use std::thread;
use tauri::{AppHandle, Emitter};

static NEXT_ID: AtomicU64 = AtomicU64::new(1);

pub struct PtySession {
    master: Box<dyn MasterPty + Send>,
    writer: Box<dyn Write + Send>,
    child: Box<dyn portable_pty::Child + Send>,
}

pub struct PtyManager {
    sessions: HashMap<String, PtySession>,
}

impl PtyManager {
    pub fn new() -> Self {
        Self {
            sessions: HashMap::new(),
        }
    }

    pub fn start(
        &mut self,
        app: AppHandle,
        project_dir: String,
        tool: String,
        cols: u16,
        rows: u16,
    ) -> Result<String, String> {
        let bin = enclave::enclave_command()?;
        let pty_system = native_pty_system();
        let pair = pty_system
            .openpty(PtySize {
                rows,
                cols,
                pixel_width: 0,
                pixel_height: 0,
            })
            .map_err(|e| format!("打开 PTY 失败: {e}"))?;

        let mut cmd = CommandBuilder::new(&bin);
        cmd.arg("--tool");
        cmd.arg(&tool);
        cmd.cwd(&project_dir);

        let child = pair
            .slave
            .spawn_command(cmd)
            .map_err(|e| format!("启动 enclave 失败: {e}"))?;
        drop(pair.slave);

        let mut reader = pair
            .master
            .try_clone_reader()
            .map_err(|e| format!("PTY reader 失败: {e}"))?;
        let writer = pair
            .master
            .take_writer()
            .map_err(|e| format!("PTY writer 失败: {e}"))?;

        let id = format!("pty-{}", NEXT_ID.fetch_add(1, Ordering::SeqCst));
        let id_clone = id.clone();
        let app_clone = app.clone();

        thread::spawn(move || {
            let mut buf = [0u8; 4096];
            loop {
                match reader.read(&mut buf) {
                    Ok(0) => break,
                    Ok(n) => {
                        let chunk = String::from_utf8_lossy(&buf[..n]).to_string();
                        let _ = app_clone.emit(
                            "pty-output",
                            serde_json::json!({ "id": id_clone, "data": chunk }),
                        );
                    }
                    Err(_) => break,
                }
            }
            let _ = app_clone.emit(
                "pty-exit",
                serde_json::json!({ "id": id_clone }),
            );
        });

        self.sessions.insert(
            id.clone(),
            PtySession {
                master: pair.master,
                writer,
                child,
            },
        );

        Ok(id)
    }

    pub fn write(&mut self, id: &str, data: &[u8]) -> Result<(), String> {
        let session = self
            .sessions
            .get_mut(id)
            .ok_or_else(|| "会话不存在".to_string())?;
        session
            .writer
            .write_all(data)
            .map_err(|e| format!("写入 PTY 失败: {e}"))?;
        session.writer.flush().map_err(|e| e.to_string())?;
        Ok(())
    }

    pub fn resize(&mut self, id: &str, cols: u16, rows: u16) -> Result<(), String> {
        let session = self
            .sessions
            .get_mut(id)
            .ok_or_else(|| "会话不存在".to_string())?;
        session
            .master
            .resize(PtySize {
                rows,
                cols,
                pixel_width: 0,
                pixel_height: 0,
            })
            .map_err(|e| format!("调整 PTY 失败: {e}"))
    }

    pub fn kill(&mut self, id: &str) -> Result<(), String> {
        if let Some(mut session) = self.sessions.remove(id) {
            let _ = session.child.kill();
        }
        Ok(())
    }
}
