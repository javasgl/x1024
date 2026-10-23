import { useCallback, useEffect, useMemo, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { api, Health, SecretStatus, SessionInfo, ToolInfo } from "./api";
import { TerminalView } from "./TerminalView";

type Page = "sessions" | "new" | "secrets" | "settings" | "terminal";

const FALLBACK_TOOLS: ToolInfo[] = [
  { id: "claude", label: "Claude Code" },
  { id: "codex", label: "Codex" },
  { id: "opencode", label: "OpenCode" },
];

export default function App() {
  const [page, setPage] = useState<Page>("sessions");
  const [health, setHealth] = useState<Health | null>(null);
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [tools, setTools] = useState<ToolInfo[]>(FALLBACK_TOOLS);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // wizard
  const [step, setStep] = useState(1);
  const [projectDir, setProjectDir] = useState("");
  const [tool, setTool] = useState("claude");

  // terminal
  const [ptyId, setPtyId] = useState<StringLike>(null);
  const [activeLabel, setActiveLabel] = useState("");

  // secrets
  const [secretStatus, setSecretStatus] = useState<SecretStatus | null>(null);
  const [anthropicKey, setAnthropicKey] = useState("");
  const [openaiKey, setOpenaiKey] = useState("");
  const [secretMsg, setSecretMsg] = useState<string | null>(null);

  const refreshHealth = useCallback(async () => {
    try {
      setHealth(await api.checkHealth());
    } catch (e) {
      setHealth(null);
      setError(String(e));
    }
  }, []);

  const refreshSessions = useCallback(async () => {
    try {
      setSessions(await api.listSessions(false));
      setError(null);
    } catch (e) {
      setSessions([]);
      // soft-fail when enclave missing
      const msg = String(e);
      if (!msg.includes("未找到 enclave")) setError(msg);
    }
  }, []);

  useEffect(() => {
    void refreshHealth();
    void refreshSessions();
    void api.listTools().then(setTools).catch(() => setTools(FALLBACK_TOOLS));
    void api.readSecretStatus().then(setSecretStatus).catch(() => undefined);

    const t = window.setInterval(() => {
      void refreshSessions();
    }, 3000);
    return () => window.clearInterval(t);
  }, [refreshHealth, refreshSessions]);

  const projectName = useMemo(() => {
    if (!projectDir) return "";
    const parts = projectDir.split(/[/\\]/).filter(Boolean);
    return parts[parts.length - 1] ?? projectDir;
  }, [projectDir]);

  async function pickFolder() {
    const selected = await open({ directory: true, multiple: false });
    if (typeof selected === "string") {
      setProjectDir(selected);
    }
  }

  async function launchSession() {
    if (!projectDir || !tool) return;
    setBusy(true);
    setError(null);
    try {
      const id = await api.startSession(projectDir, tool, 120, 36);
      setPtyId(id);
      setActiveLabel(`${tool} · ${projectName}`);
      setPage("terminal");
      setStep(1);
      void refreshSessions();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function stop(name: string) {
    setBusy(true);
    try {
      await api.stopSession(name);
      await refreshSessions();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function killTerminal() {
    if (ptyId) {
      try {
        await api.ptyKill(ptyId);
      } catch {
        /* ignore */
      }
    }
    setPtyId(null);
    setPage("sessions");
    void refreshSessions();
  }

  async function saveSecrets() {
    setBusy(true);
    setSecretMsg(null);
    try {
      const path = await api.writeSecrets(
        anthropicKey || undefined,
        openaiKey || undefined,
      );
      setSecretStatus(await api.readSecretStatus());
      setAnthropicKey("");
      setOpenaiKey("");
      setSecretMsg(`已保存到本机：${path}`);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">Sandglass</div>
          <div className="brand-sub">在沙箱里跑 Agent，密钥留在本机</div>
        </div>
        <nav className="nav">
          <button
            className={page === "sessions" || page === "terminal" ? "active" : ""}
            onClick={() => setPage(ptyId ? "terminal" : "sessions")}
          >
            会话
          </button>
          <button className={page === "new" ? "active" : ""} onClick={() => setPage("new")}>
            新建
          </button>
          <button
            className={page === "secrets" ? "active" : ""}
            onClick={() => setPage("secrets")}
          >
            密钥
          </button>
          <button
            className={page === "settings" ? "active" : ""}
            onClick={() => {
              setPage("settings");
              void refreshHealth();
            }}
          >
            状态
          </button>
        </nav>
      </aside>

      <main className="main">
        {error && <p className="error">{error}</p>}

        {page === "sessions" && (
          <>
            <div className="page-head">
              <div>
                <h1>会话</h1>
                <p>在隔离环境中运行 Claude Code、Codex 等 Agent，项目文件仍在你本机。</p>
              </div>
              <button className="btn" onClick={() => setPage("new")}>
                在沙箱中打开项目
              </button>
            </div>

            {health && !health.ready && (
              <div className="notice warn" style={{ marginBottom: 16 }}>
                环境未就绪。请到「状态」页按提示安装 Docker / Enclave。
              </div>
            )}

            <div className="panel session-grid">
              {sessions.length === 0 ? (
                <div className="empty">暂无运行中的会话。点击右上角开始。</div>
              ) : (
                sessions.map((s) => (
                  <div className="session-card" key={s.name}>
                    <div>
                      <h3>
                        <span className="badge">{s.tool ?? "agent"}</span>
                        {basename(s.projectDir) || s.name}
                      </h3>
                      <div className="meta">
                        {s.status ?? "running"} · {s.name}
                        {s.createdAt ? ` · ${s.createdAt}` : ""}
                      </div>
                    </div>
                    <div className="row-actions">
                      <button className="btn secondary" disabled={busy} onClick={() => stop(s.name)}>
                        停止
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </>
        )}

        {page === "new" && (
          <>
            <div className="page-head">
              <div>
                <h1>新建会话</h1>
                <p>三步即可：选项目、选 Agent、启动沙箱。</p>
              </div>
            </div>
            <div className="panel wizard">
              <div className="steps">
                <div className={`step-pill ${step === 1 ? "on" : ""}`}>1 项目</div>
                <div className={`step-pill ${step === 2 ? "on" : ""}`}>2 Agent</div>
                <div className={`step-pill ${step === 3 ? "on" : ""}`}>3 启动</div>
              </div>

              {step === 1 && (
                <div className="field">
                  <label>项目文件夹</label>
                  <input value={projectDir} readOnly placeholder="选择要打开的代码目录" />
                  <div className="row-actions">
                    <button className="btn secondary" onClick={() => void pickFolder()}>
                      选择文件夹
                    </button>
                    <button
                      className="btn"
                      disabled={!projectDir}
                      onClick={() => setStep(2)}
                    >
                      下一步
                    </button>
                  </div>
                </div>
              )}

              {step === 2 && (
                <>
                  <div className="tool-grid">
                    {tools.map((t) => (
                      <button
                        key={t.id}
                        className={`tool-card ${tool === t.id ? "selected" : ""}`}
                        onClick={() => setTool(t.id)}
                      >
                        {t.label}
                      </button>
                    ))}
                  </div>
                  <div className="row-actions">
                    <button className="btn secondary" onClick={() => setStep(1)}>
                      上一步
                    </button>
                    <button className="btn" onClick={() => setStep(3)}>
                      下一步
                    </button>
                  </div>
                </>
              )}

              {step === 3 && (
                <>
                  <div className="notice">
                    将在沙箱中打开 <strong>{projectName}</strong>，使用{" "}
                    <strong>{tools.find((t) => t.id === tool)?.label ?? tool}</strong>。
                    API 密钥从本机注入，无需在沙箱内粘贴。
                  </div>
                  <div className="row-actions">
                    <button className="btn secondary" onClick={() => setStep(2)}>
                      上一步
                    </button>
                    <button className="btn" disabled={busy || !health?.ready} onClick={() => void launchSession()}>
                      {busy ? "启动中…" : "启动沙箱"}
                    </button>
                  </div>
                  {health && !health.ready && (
                    <p className="error">请先在「状态」页完成 Docker / Enclave 准备。</p>
                  )}
                </>
              )}
            </div>
          </>
        )}

        {page === "terminal" && ptyId && (
          <div className="terminal-page">
            <div className="page-head">
              <div>
                <h1>{activeLabel || "会话终端"}</h1>
                <p>Agent 在沙箱内运行。关闭或停止不会把密钥写进容器配置。</p>
              </div>
              <button className="btn danger" onClick={() => void killTerminal()}>
                结束终端
              </button>
            </div>
            <TerminalView ptyId={ptyId} />
          </div>
        )}

        {page === "secrets" && (
          <>
            <div className="page-head">
              <div>
                <h1>密钥</h1>
                <p>密钥只保存在本机 Enclave secrets，由网关按需注入。沙箱内无需填写。</p>
              </div>
            </div>
            <div className="panel wizard">
              {secretStatus && (
                <div className="notice">
                  存储位置：{secretStatus.path}
                  <br />
                  Anthropic：{secretStatus.hasAnthropic ? "已配置" : "未配置"} · OpenAI：
                  {secretStatus.hasOpenai ? "已配置" : "未配置"}
                </div>
              )}
              <div className="field">
                <label>Anthropic API Key</label>
                <input
                  type="password"
                  value={anthropicKey}
                  onChange={(e) => setAnthropicKey(e.target.value)}
                  placeholder="sk-ant-…（留空则不改）"
                />
              </div>
              <div className="field">
                <label>OpenAI API Key</label>
                <input
                  type="password"
                  value={openaiKey}
                  onChange={(e) => setOpenaiKey(e.target.value)}
                  placeholder="sk-…（留空则不改）"
                />
              </div>
              <button className="btn" disabled={busy} onClick={() => void saveSecrets()}>
                保存到本机
              </button>
              {secretMsg && <div className="notice">{secretMsg}</div>}
            </div>
          </>
        )}

        {page === "settings" && (
          <>
            <div className="page-head">
              <div>
                <h1>状态</h1>
                <p>启动沙箱前需要本机 Docker 与 Enclave CLI。</p>
              </div>
              <button className="btn secondary" onClick={() => void refreshHealth()}>
                重新检测
              </button>
            </div>
            <div className="panel health-list">
              <div className={`health-row ${health?.dockerOk ? "ok" : "bad"}`}>
                <div>
                  <strong>Docker</strong>
                  <div className="meta">{health?.dockerMessage ?? "检测中…"}</div>
                </div>
                <span className={`badge ${health?.dockerOk ? "" : "warn"}`}>
                  {health?.dockerOk ? "就绪" : "未就绪"}
                </span>
              </div>
              <div className={`health-row ${health?.enclaveOk ? "ok" : "bad"}`}>
                <div>
                  <strong>Enclave</strong>
                  <div className="meta">
                    {health?.enclaveVersion ?? health?.enclavePath ?? "未安装"}
                  </div>
                </div>
                <span className={`badge ${health?.enclaveOk ? "" : "warn"}`}>
                  {health?.enclaveOk ? "就绪" : "未就绪"}
                </span>
              </div>
              {health?.hints?.length ? (
                <ul className="hints">
                  {health.hints.map((h) => (
                    <li key={h}>{h}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          </>
        )}
      </main>
    </div>
  );
}

type StringLike = string | null;

function basename(path: string | null | undefined): string {
  if (!path) return "";
  const parts = path.split(/[/\\]/).filter(Boolean);
  return parts[parts.length - 1] ?? path;
}
