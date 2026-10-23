(() => {
  const state = {
    page: "sessions",
    health: null,
    sessions: [],
    tools: [
      { id: "claude", label: "Claude Code" },
      { id: "codex", label: "Codex" },
      { id: "opencode", label: "OpenCode" },
    ],
    step: 1,
    tool: "claude",
    ptyId: null,
    term: null,
    fit: null,
    ws: null,
  };

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => [...document.querySelectorAll(sel)];

  function showError(msg) {
    const el = $("#error");
    if (!msg) {
      el.classList.add("hidden");
      el.textContent = "";
      return;
    }
    el.textContent = msg;
    el.classList.remove("hidden");
  }

  async function api(path, opts = {}) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...opts,
    });
    const text = await res.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = text;
    }
    if (!res.ok) {
      const detail = (data && data.detail) || text || res.statusText;
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return data;
  }

  function basename(path) {
    if (!path) return "";
    const parts = path.split(/[/\\]/).filter(Boolean);
    return parts[parts.length - 1] || path;
  }

  function setPage(page) {
    state.page = page;
    ["sessions", "new", "secrets", "settings", "terminal"].forEach((p) => {
      const el = $(`#page-${p}`);
      if (!el) return;
      el.classList.toggle("hidden", p !== page);
    });
    $$(".nav button").forEach((btn) => {
      const nav = btn.getAttribute("data-nav");
      const active =
        nav === page || (page === "terminal" && nav === "sessions");
      btn.classList.toggle("active", active);
    });
  }

  function setStep(n) {
    state.step = n;
    $$("[data-step-pill]").forEach((el) => {
      el.classList.toggle("on", Number(el.getAttribute("data-step-pill")) === n);
    });
    $("#wiz-1").classList.toggle("hidden", n !== 1);
    $("#wiz-2").classList.toggle("hidden", n !== 2);
    $("#wiz-3").classList.toggle("hidden", n !== 3);
    if (n === 3) {
      const label = state.tools.find((t) => t.id === state.tool)?.label || state.tool;
      $("#confirm-text").innerHTML = `将在沙箱中打开 <strong>${basename($("#project-dir").value)}</strong>，使用 <strong>${label}</strong>。API 密钥从本机注入，无需在沙箱内粘贴。`;
    }
  }

  function renderTools() {
    const grid = $("#tool-grid");
    grid.innerHTML = "";
    state.tools.forEach((t) => {
      const btn = document.createElement("button");
      btn.className = `tool-card ${state.tool === t.id ? "selected" : ""}`;
      btn.textContent = t.label;
      btn.onclick = () => {
        state.tool = t.id;
        renderTools();
      };
      grid.appendChild(btn);
    });
  }

  function renderSessions() {
    const box = $("#session-list");
    if (!state.sessions.length) {
      box.innerHTML = `<div class="empty">暂无运行中的会话。点击右上角开始。</div>`;
      return;
    }
    box.innerHTML = state.sessions
      .map(
        (s) => `
      <div class="session-card">
        <div>
          <h3><span class="badge">${s.tool || "agent"}</span>${basename(s.projectDir) || s.name}</h3>
          <div class="meta">${s.status || "running"} · ${s.name}${s.createdAt ? " · " + s.createdAt : ""}</div>
        </div>
        <div class="row-actions">
          <button class="btn secondary" data-stop="${s.name}">停止</button>
        </div>
      </div>`
      )
      .join("");
    $$("[data-stop]").forEach((btn) => {
      btn.onclick = async () => {
        try {
          await api("/api/sessions/stop", {
            method: "POST",
            body: JSON.stringify({ name: btn.getAttribute("data-stop") }),
          });
          await refreshSessions();
        } catch (e) {
          showError(String(e.message || e));
        }
      };
    });
  }

  function runtimeLabel(kind) {
    if (kind === "colima") return "Colima（推荐）";
    if (kind === "docker") return "Docker 引擎";
    if (kind === "podman") return "Podman";
    return "容器运行时";
  }

  function renderHealth() {
    const h = state.health;
    const box = $("#health-list");
    if (!h) {
      box.innerHTML = `<div class="empty">检测中…</div>`;
      return;
    }
    const kind = h.runtimeKind || "none";
    const engineMode = h.engineMode === "bundled" ? "内置引擎" : "开发机系统工具";
    box.innerHTML = `
      <div class="health-row ${h.dockerOk ? "ok" : "bad"}">
        <div>
          <strong>${runtimeLabel(kind)}</strong>
          <div class="meta">${h.dockerMessage || ""}</div>
          <div class="meta">引擎来源：${engineMode} · Colima：${h.colimaInstalled ? (h.colimaRunning ? "运行中" : "未运行") : "未安装"}</div>
        </div>
        <span class="badge ${h.dockerOk ? "" : "warn"}">${h.dockerOk ? "就绪" : "未就绪"}</span>
      </div>
      <div class="health-row ${h.enclaveOk ? "ok" : "bad"}">
        <div><strong>Enclave</strong><div class="meta">${h.enclaveVersion || h.enclavePath || "未安装"}</div></div>
        <span class="badge ${h.enclaveOk ? "" : "warn"}">${h.enclaveOk ? "就绪" : "未就绪"}</span>
      </div>
      ${
        h.hints && h.hints.length
          ? `<ul class="hints">${h.hints.map((x) => `<li>${x}</li>`).join("")}</ul>`
          : ""
      }
    `;
    $("#ready-warn").classList.toggle("hidden", !!h.ready);
  }

  async function refreshHealth() {
    try {
      state.health = await api("/api/health");
      renderHealth();
    } catch (e) {
      showError(String(e.message || e));
    }
  }

  async function refreshSessions() {
    try {
      state.sessions = await api("/api/sessions");
      showError("");
      renderSessions();
    } catch (e) {
      state.sessions = [];
      renderSessions();
      const msg = String(e.message || e);
      if (!msg.includes("未找到 enclave")) showError(msg);
    }
  }

  async function refreshSecrets() {
    try {
      const s = await api("/api/secrets");
      $("#secret-status").textContent = `存储位置：${s.path}\nAnthropic：${s.hasAnthropic ? "已配置" : "未配置"} · OpenAI：${s.hasOpenai ? "已配置" : "未配置"}`;
    } catch (e) {
      $("#secret-status").textContent = String(e.message || e);
    }
  }

  function disposeTerminal() {
    if (state.ws) {
      try {
        state.ws.close();
      } catch (_) {}
      state.ws = null;
    }
    if (state.term) {
      state.term.dispose();
      state.term = null;
      state.fit = null;
    }
    state.ptyId = null;
  }

  async function launch() {
    const projectDir = $("#project-dir").value.trim();
    if (!projectDir) return;
    if (state.health && !state.health.ready) {
      showError("请先在「状态」页完成 Docker / Enclave 准备。");
      return;
    }
    showError("");
    try {
      const { id } = await api("/api/session/start", {
        method: "POST",
        body: JSON.stringify({
          projectDir,
          tool: state.tool,
          cols: 120,
          rows: 36,
        }),
      });
      state.ptyId = id;
      $("#term-title").textContent = `${state.tool} · ${basename(projectDir)}`;
      setPage("terminal");
      openTerminal(id);
      setStep(1);
      refreshSessions();
    } catch (e) {
      showError(String(e.message || e));
    }
  }

  function openTerminal(id) {
    disposeTerminalSoft();
    const host = $("#terminal");
    host.innerHTML = "";
    const term = new Terminal({
      cursorBlink: true,
      fontSize: 13,
      fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
      theme: { background: "#121612", foreground: "#d7e2d9", cursor: "#8fcea8" },
    });
    const fit = new FitAddon.FitAddon();
    term.loadAddon(fit);
    term.open(host);
    fit.fit();
    state.term = term;
    state.fit = fit;

    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/pty/${id}`);
    ws.binaryType = "arraybuffer";
    state.ws = ws;

    ws.onmessage = (ev) => {
      if (typeof ev.data === "string") {
        term.write(ev.data);
      } else {
        term.write(new Uint8Array(ev.data));
      }
    };
    ws.onclose = () => {
      term.writeln("\r\n\x1b[33m[会话已结束]\x1b[0m");
    };

    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) ws.send(data);
    });

    const resize = () => {
      fit.fit();
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(`\x00resize:${term.cols},${term.rows}`);
      }
    };
    window.addEventListener("resize", resize);
    setTimeout(resize, 50);
  }

  function disposeTerminalSoft() {
    if (state.term) {
      state.term.dispose();
      state.term = null;
      state.fit = null;
    }
  }

  // Wire UI
  $$(".nav button").forEach((btn) => {
    btn.onclick = () => {
      const nav = btn.getAttribute("data-nav");
      if (nav === "sessions" && state.ptyId) setPage("terminal");
      else setPage(nav);
      if (nav === "settings") refreshHealth();
      if (nav === "secrets") refreshSecrets();
    };
  });
  $$("[data-goto]").forEach((btn) => {
    btn.onclick = () => setPage(btn.getAttribute("data-goto"));
  });

  $("#to-step-2").onclick = () => {
    if (!$("#project-dir").value.trim()) return;
    setStep(2);
  };
  $("#to-step-3").onclick = () => setStep(3);
  $("#back-1").onclick = () => setStep(1);
  $("#back-2").onclick = () => setStep(2);
  $("#launch").onclick = () => launch();
  $("#pick-folder").onclick = async () => {
    try {
      const res = await api("/api/pick-folder", { method: "POST", body: "{}" });
      if (res.path) $("#project-dir").value = res.path;
    } catch (e) {
      showError("文件夹选择失败，请直接粘贴路径。" + (e.message || ""));
    }
  };
  $("#save-secrets").onclick = async () => {
    try {
      const path = await api("/api/secrets", {
        method: "POST",
        body: JSON.stringify({
          anthropicKey: $("#key-anthropic").value || null,
          openaiKey: $("#key-openai").value || null,
        }),
      });
      $("#key-anthropic").value = "";
      $("#key-openai").value = "";
      const msg = $("#secret-msg");
      msg.textContent = `已保存到本机：${path.path}`;
      msg.classList.remove("hidden");
      refreshSecrets();
    } catch (e) {
      showError(String(e.message || e));
    }
  };
  $("#recheck").onclick = () => refreshHealth();
  $("#start-colima").onclick = async () => {
    showError("");
    const btn = $("#start-colima");
    btn.disabled = true;
    btn.textContent = "启动中…";
    try {
      const res = await api("/api/runtime/ensure-colima", { method: "POST", body: "{}" });
      if (!res.ok) showError(res.message || "Colima 启动失败");
      await refreshHealth();
    } catch (e) {
      showError(String(e.message || e));
    } finally {
      btn.disabled = false;
      btn.textContent = "启动 Colima";
    }
  };
  $("#kill-term").onclick = async () => {
    if (state.ptyId) {
      try {
        await api(`/api/session/${state.ptyId}/kill`, { method: "POST", body: "{}" });
      } catch (_) {}
    }
    disposeTerminal();
    setPage("sessions");
    refreshSessions();
  };

  // boot
  renderTools();
  refreshHealth();
  refreshSessions();
  refreshSecrets();
  setInterval(refreshSessions, 3000);
})();
