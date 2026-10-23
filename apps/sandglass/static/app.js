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
    preparing: false,
  };

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => [...document.querySelectorAll(sel)];

  function showError(msg) {
    const el = $("#error");
    if (!el) return;
    if (!msg) {
      el.classList.add("hidden");
      el.textContent = "";
      return;
    }
    el.textContent = msg;
    el.classList.remove("hidden");
  }

  function showToast(msg, isWarn = false) {
    const el = $("#toast");
    if (!el) return;
    if (!msg) {
      el.classList.add("hidden");
      el.textContent = "";
      return;
    }
    el.textContent = msg;
    el.classList.toggle("warn", !!isWarn);
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
    const parts = String(path).split(/[/\\]/).filter(Boolean);
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
      const active = nav === page || (page === "terminal" && nav === "sessions");
      btn.classList.toggle("active", active);
    });
    showError("");
  }

  function setStep(n) {
    state.step = n;
    $$("[data-step-pill]").forEach((el) => {
      el.classList.toggle("on", Number(el.getAttribute("data-step-pill")) === n);
    });
    const w1 = $("#wiz-1");
    const w2 = $("#wiz-2");
    const w3 = $("#wiz-3");
    if (w1) w1.classList.toggle("hidden", n !== 1);
    if (w2) w2.classList.toggle("hidden", n !== 2);
    if (w3) w3.classList.toggle("hidden", n !== 3);
    if (n === 3) {
      const label = state.tools.find((t) => t.id === state.tool)?.label || state.tool;
      const el = $("#confirm-text");
      if (el) {
        el.innerHTML = `将在沙箱中打开 <strong>${basename($("#project-dir")?.value)}</strong>，使用 <strong>${label}</strong>。密钥从本机注入。`;
      }
    }
  }

  function renderTools() {
    const grid = $("#tool-grid");
    if (!grid) return;
    grid.innerHTML = "";
    state.tools.forEach((t) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = `tool-card ${state.tool === t.id ? "selected" : ""}`;
      btn.textContent = t.label;
      btn.dataset.tool = t.id;
      grid.appendChild(btn);
    });
  }

  function renderSessions() {
    const box = $("#session-list");
    if (!box) return;
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
          <button type="button" class="btn secondary" data-stop="${s.name}">停止</button>
        </div>
      </div>`
      )
      .join("");
  }

  function renderHealth() {
    const h = state.health;
    const box = $("#health-list");
    if (!box) return;
    if (!h) {
      box.innerHTML = `<div class="empty">检测中…</div>`;
      return;
    }
    const engineOk = !!h.dockerOk;
    const engineMode = h.engineMode === "bundled" ? "内置" : "本机开发环境";
    box.innerHTML = `
      <div class="health-row ${engineOk ? "ok" : "bad"}">
        <div>
          <strong>沙箱引擎</strong>
          <div class="meta">${h.dockerMessage || ""}</div>
          <div class="meta">来源：${engineMode}</div>
        </div>
        <span class="badge ${engineOk ? "" : "warn"}">${engineOk ? "就绪" : "未就绪"}</span>
      </div>
      <div class="health-row ${h.enclaveOk ? "ok" : "bad"}">
        <div>
          <strong>Agent 运行时</strong>
          <div class="meta">${h.enclaveOk ? h.enclaveVersion || "已就绪" : "尚未就绪"}</div>
        </div>
        <span class="badge ${h.enclaveOk ? "" : "warn"}">${h.enclaveOk ? "就绪" : "未就绪"}</span>
      </div>
      ${
        h.hints && h.hints.length
          ? `<ul class="hints">${h.hints.map((x) => `<li>${x}</li>`).join("")}</ul>`
          : ""
      }
    `;
    const warn = $("#ready-warn");
    if (warn) warn.classList.toggle("hidden", !!h.ready);
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
      renderSessions();
    } catch (e) {
      state.sessions = [];
      renderSessions();
      const msg = String(e.message || e);
      // Don't spam users with engine-not-installed while browsing UI
      if (!/enclave|未找到|未安装/i.test(msg)) {
        showError(msg);
      }
    }
  }

  async function refreshSecrets() {
    try {
      const s = await api("/api/secrets");
      const el = $("#secret-status");
      if (el) {
        el.textContent = `已保存位置：本机密钥库\nAnthropic：${s.hasAnthropic ? "已配置" : "未配置"} · OpenAI：${s.hasOpenai ? "已配置" : "未配置"}`;
      }
    } catch (e) {
      const el = $("#secret-status");
      if (el) el.textContent = String(e.message || e);
    }
  }

  async function prepareEngine(showProgress = true) {
    if (state.preparing) return;
    state.preparing = true;
    const btn = $("#start-engine");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "启动中…";
    }
    if (showProgress) {
      showToast("正在准备沙箱引擎（首次可能自动安装，需几分钟）…", true);
    }
    try {
      const res = await api("/api/runtime/prepare", { method: "POST", body: "{}" });
      await refreshHealth();
      if (res.ready) {
        showToast(res.message || "沙箱引擎已就绪");
        showError("");
      } else {
        showToast(res.message || "沙箱引擎仍未就绪", true);
      }
    } catch (e) {
      showError(String(e.message || e));
    } finally {
      state.preparing = false;
      if (btn) {
        btn.disabled = false;
        btn.textContent = "启动沙箱引擎";
      }
    }
  }

  function disposeTerminal() {
    if (state.ws) {
      try {
        state.ws.close();
      } catch (_) {}
      state.ws = null;
    }
    disposeTerminalSoft();
    state.ptyId = null;
  }

  function disposeTerminalSoft() {
    if (state.term) {
      try {
        state.term.dispose();
      } catch (_) {}
      state.term = null;
      state.fit = null;
    }
  }

  async function launch() {
    const projectDir = ($("#project-dir")?.value || "").trim();
    if (!projectDir) {
      showToast("请先填写项目路径", true);
      setStep(1);
      return;
    }
    if (state.health && !state.health.ready) {
      showToast("沙箱引擎未就绪，正在尝试启动…", true);
      await prepareEngine(true);
      if (!state.health?.ready) {
        showError("沙箱引擎仍未就绪，请到「状态」页查看并重试。");
        return;
      }
    }
    showError("");
    showToast("正在启动会话…");
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
      const title = $("#term-title");
      if (title) title.textContent = `${state.tool} · ${basename(projectDir)}`;
      setPage("terminal");
      openTerminal(id);
      setStep(1);
      showToast("");
      refreshSessions();
    } catch (e) {
      showError(String(e.message || e));
      showToast("");
    }
  }

  function openTerminal(id) {
    disposeTerminalSoft();
    const host = $("#terminal");
    if (!host) return;
    host.innerHTML = "";

    if (typeof Terminal === "undefined") {
      host.innerHTML = `<div class="empty" style="color:#d7e2d9">终端组件未加载。请确认 static/vendor 资源存在后重启应用。</div>`;
      return;
    }

    const term = new Terminal({
      cursorBlink: true,
      fontSize: 13,
      fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
      theme: { background: "#121612", foreground: "#d7e2d9", cursor: "#8fcea8" },
    });
    const FitCtor = window.FitAddon?.FitAddon || window.FitAddon;
    const fit = FitCtor ? new FitCtor() : null;
    if (fit) term.loadAddon(fit);
    term.open(host);
    if (fit) fit.fit();
    state.term = term;
    state.fit = fit;

    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/pty/${id}`);
    ws.binaryType = "arraybuffer";
    state.ws = ws;

    ws.onmessage = (ev) => {
      if (typeof ev.data === "string") term.write(ev.data);
      else term.write(new Uint8Array(ev.data));
    };
    ws.onclose = () => {
      term.writeln("\r\n\x1b[33m[会话已结束]\x1b[0m");
    };
    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) ws.send(data);
    });

    const resize = () => {
      if (fit) fit.fit();
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(`\x00resize:${term.cols},${term.rows}`);
      }
    };
    window.addEventListener("resize", resize);
    setTimeout(resize, 50);
  }

  // Event delegation — more reliable than per-button onclick in webview
  document.addEventListener("click", async (ev) => {
    const t = ev.target.closest("button, [data-nav], [data-goto], [data-tool], [data-stop]");
    if (!t) return;

    const nav = t.getAttribute("data-nav");
    if (nav) {
      ev.preventDefault();
      if (nav === "sessions" && state.ptyId) setPage("terminal");
      else setPage(nav);
      if (nav === "settings") refreshHealth();
      if (nav === "secrets") refreshSecrets();
      if (nav === "new") showToast("请选择或粘贴项目路径，然后点下一步");
      return;
    }

    const goto = t.getAttribute("data-goto");
    if (goto) {
      ev.preventDefault();
      setPage(goto);
      if (goto === "new") showToast("请选择或粘贴项目路径，然后点下一步");
      return;
    }

    const tool = t.getAttribute("data-tool");
    if (tool) {
      ev.preventDefault();
      state.tool = tool;
      renderTools();
      return;
    }

    const stopName = t.getAttribute("data-stop");
    if (stopName) {
      ev.preventDefault();
      try {
        await api("/api/sessions/stop", {
          method: "POST",
          body: JSON.stringify({ name: stopName }),
        });
        await refreshSessions();
        showToast("已停止会话");
      } catch (e) {
        showError(String(e.message || e));
      }
      return;
    }

    const id = t.id;
    if (!id) return;

    if (id === "to-step-2") {
      ev.preventDefault();
      const dir = ($("#project-dir")?.value || "").trim();
      if (!dir) {
        showToast("请先粘贴或选择项目文件夹路径", true);
        return;
      }
      setStep(2);
      showToast("选择要运行的 Agent");
      return;
    }
    if (id === "to-step-3") {
      ev.preventDefault();
      setStep(3);
      return;
    }
    if (id === "back-1") {
      ev.preventDefault();
      setStep(1);
      return;
    }
    if (id === "back-2") {
      ev.preventDefault();
      setStep(2);
      return;
    }
    if (id === "launch") {
      ev.preventDefault();
      await launch();
      return;
    }
    if (id === "pick-folder") {
      ev.preventDefault();
      showToast("正在打开文件夹选择…");
      try {
        const res = await api("/api/pick-folder", { method: "POST", body: "{}" });
        if (res.path) {
          $("#project-dir").value = res.path;
          showToast(`已选择：${res.path}`);
        } else {
          showToast(res.error || "无法弹出系统选文件夹，请直接在上方粘贴路径", true);
        }
      } catch (e) {
        showToast("选文件夹失败，请直接粘贴路径", true);
        showError(String(e.message || e));
      }
      return;
    }
    if (id === "save-secrets") {
      ev.preventDefault();
      try {
        await api("/api/secrets", {
          method: "POST",
          body: JSON.stringify({
            anthropicKey: $("#key-anthropic")?.value || null,
            openaiKey: $("#key-openai")?.value || null,
          }),
        });
        if ($("#key-anthropic")) $("#key-anthropic").value = "";
        if ($("#key-openai")) $("#key-openai").value = "";
        const msg = $("#secret-msg");
        if (msg) {
          msg.textContent = "密钥已保存到本机";
          msg.classList.remove("hidden");
        }
        showToast("密钥已保存");
        refreshSecrets();
      } catch (e) {
        showError(String(e.message || e));
      }
      return;
    }
    if (id === "recheck") {
      ev.preventDefault();
      showToast("正在检测…");
      await refreshHealth();
      showToast(state.health?.ready ? "沙箱引擎就绪" : "仍未就绪，可点「启动沙箱引擎」", !state.health?.ready);
      return;
    }
    if (id === "start-engine" || id === "start-colima") {
      ev.preventDefault();
      await prepareEngine(true);
      return;
    }
    if (id === "kill-term") {
      ev.preventDefault();
      if (state.ptyId) {
        try {
          await api(`/api/session/${state.ptyId}/kill`, { method: "POST", body: "{}" });
        } catch (_) {}
      }
      disposeTerminal();
      setPage("sessions");
      refreshSessions();
      return;
    }
  });

  // boot
  function boot() {
    try {
      renderTools();
      setPage("sessions");
      setStep(1);
      refreshHealth().then(() => {
        if (state.health && !state.health.ready) {
          // Quiet auto-prepare in background for product feel
          prepareEngine(false);
        }
      });
      refreshSessions();
      refreshSecrets();
      setInterval(refreshSessions, 4000);
    } catch (e) {
      showError("界面初始化失败：" + (e.message || e));
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
