import { invoke } from "@tauri-apps/api/core";

export type Health = {
  enclaveOk: boolean;
  enclaveVersion: string | null;
  enclavePath: string | null;
  dockerOk: boolean;
  dockerMessage: string;
  ready: boolean;
  hints: string[];
};

export type SessionInfo = {
  name: string;
  tool: string | null;
  projectDir: string | null;
  status: string | null;
  sessionName: string | null;
  background: boolean | null;
  createdAt: string | null;
};

export type ToolInfo = {
  id: string;
  label: string;
};

export type SecretStatus = {
  path: string;
  hasAnthropic: boolean;
  hasOpenai: boolean;
};

export const api = {
  checkHealth: () => invoke<Health>("check_health"),
  listSessions: (includeStopped = false) =>
    invoke<SessionInfo[]>("list_sessions", { includeStopped }),
  stopSession: (name: string) => invoke<void>("stop_session", { name }),
  listTools: () => invoke<ToolInfo[]>("list_tools"),
  writeSecrets: (anthropicKey?: string, openaiKey?: string) =>
    invoke<string>("write_secrets", { anthropicKey, openaiKey }),
  readSecretStatus: () => invoke<SecretStatus>("read_secret_status"),
  startSession: (projectDir: string, tool: string, cols: number, rows: number) =>
    invoke<string>("start_session", { projectDir, tool, cols, rows }),
  ptyWrite: (id: string, data: string) => invoke<void>("pty_write", { id, data }),
  ptyResize: (id: string, cols: number, rows: number) =>
    invoke<void>("pty_resize", { id, cols, rows }),
  ptyKill: (id: string) => invoke<void>("pty_kill", { id }),
};
