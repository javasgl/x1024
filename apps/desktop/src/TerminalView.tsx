import { useEffect, useRef } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { listen } from "@tauri-apps/api/event";
import { api } from "./api";
import "@xterm/xterm/css/xterm.css";

type Props = {
  ptyId: string;
};

export function TerminalView({ ptyId }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);

  useEffect(() => {
    if (!hostRef.current) return;
    const term = new Terminal({
      cursorBlink: true,
      fontSize: 13,
      fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
      theme: {
        background: "#121612",
        foreground: "#d7e2d9",
        cursor: "#8fcea8",
      },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(hostRef.current);
    fit.fit();
    termRef.current = term;

    const onData = term.onData((data) => {
      void api.ptyWrite(ptyId, data);
    });

    const resize = () => {
      fit.fit();
      void api.ptyResize(ptyId, term.cols, term.rows);
    };
    resize();
    window.addEventListener("resize", resize);

    let unlistenOutput: (() => void) | undefined;
    let unlistenExit: (() => void) | undefined;

    void listen<{ id: string; data: string }>("pty-output", (ev) => {
      if (ev.payload.id === ptyId) {
        term.write(ev.payload.data);
      }
    }).then((fn) => {
      unlistenOutput = fn;
    });

    void listen<{ id: string }>("pty-exit", (ev) => {
      if (ev.payload.id === ptyId) {
        term.writeln("\r\n\x1b[33m[会话已结束]\x1b[0m");
      }
    }).then((fn) => {
      unlistenExit = fn;
    });

    return () => {
      onData.dispose();
      window.removeEventListener("resize", resize);
      unlistenOutput?.();
      unlistenExit?.();
      term.dispose();
      termRef.current = null;
    };
  }, [ptyId]);

  return <div className="terminal-wrap" ref={hostRef} />;
}
