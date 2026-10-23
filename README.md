# Sandglass

**自带沙箱引擎的桌面 App**：双击即用，用户不必自行安装 Docker Desktop / Colima / Enclave。

产品形态见 [docs/PRODUCT.md](docs/PRODUCT.md)。短演示视频：[demos/sandglass-demo.mp4](demos/sandglass-demo.mp4)（含「本机有密钥、沙箱终端看不到明文」）。

---

## 技术原理

### 要解决什么问题

Agent（Claude Code / Codex 等）需要真实 shell 与项目读写能力，但默认跑在宿主机上时会带来三类风险：

| 风险 | 典型后果 |
|------|----------|
| **密钥外泄** | `~/.zshrc`、密钥文件、剪贴板、环境变量被读出或写进对话日志 |
| **越权读写** | Agent 扫到 `~/Documents`、其它仓库、SSH 私钥目录 |
| **宿主污染** | 误删文件、改全局配置、装任意包影响本机 |

Sandglass 的原则不是「多做一层 UI」，而是：**把 Agent 的执行面挪进可控沙箱，宿主机只保留编排与密钥库**。

### 信任边界（Trust Boundary）

```
┌─────────────────────────────────────────────────────────┐
│  信任域 A：宿主机（用户本机）                              │
│  · Sandglass UI / 本地密钥库                             │
│  · 明文 API Key 只写在这里（0600）                        │
│  · 不把完整家目录、密钥文件挂进沙箱                        │
└──────────────────────────┬──────────────────────────────┘
                           │ 窄通道：PTY 字节流 + 显式策略注入
                           ▼
┌─────────────────────────────────────────────────────────┐
│  信任域 B：容器引擎（Colima → Lima Linux VM → containerd） │
│  · 与 macOS 内核隔离；进程、文件系统默认不共享               │
└──────────────────────────┬──────────────────────────────┘
                           │ Enclave 策略：挂载 / 网络 / secrets
                           ▼
┌─────────────────────────────────────────────────────────┐
│  信任域 C：Agent 沙箱（Eclipse Enclave 管理的容器）         │
│  · 只看见项目目录（bind mount）                           │
│  · 原始密钥默认不可见；需要时由策略注入，而非「整库映射」     │
│  · App 内终端显示的就是这里的 stdin/stdout                 │
└─────────────────────────────────────────────────────────┘
```

**原则：** UI 在 A，执行在 C；A→C 只允许窄通道，禁止「宿主机 shell 直接当 Agent 终端」。

### 分层隔离（为什么是 Colima + Enclave）

| 层 | 组件 | 原理作用 |
|----|------|----------|
| 编排层 | Sandglass（FastAPI + 桌面壳） | 启动引擎、写密钥、开会话；不执行 Agent 业务命令 |
| 沙箱控制面 | **Eclipse Enclave** | 按会话声明挂载、网络与 secrets；把「跑 Agent」变成「跑受控容器」 |
| 容器数据面 | **Colima + Lima VM** | macOS 上提供 Linux 容器运行时，无 Docker Desktop GUI/常驻托盘 |
| 客户端 | **docker CLI** | Enclave 调用 Docker API 的标准入口 |

选用 Colima 而非 Docker Desktop，是产品与隔离上的同一选择：**引擎无头、可内置、用户无感**；隔离强度来自「Linux VM + 容器」，不是来自桌面产品品牌。

相对「只用 macOS Seatbelt / sandbox-exec」：容器方案对 Agent 生态（Linux 工具链、镜像、网络策略）更匹配；Seatbelt 可作为更小安装包的后续替代，但 V1 优先可复现的容器边界。

### 密钥原理（Host Vault，不是「环境变量透传」）

1. **明文只落在宿主机**：`~/.local/state/enclave/secrets/global.env`（权限 `0600`），由 App「密钥」页写入。  
2. **沙箱默认看不到该文件**：未挂载家目录密钥路径时，容器内 `cat` 不到、环境变量也无明文。  
3. **需要给模型用时**：由 Enclave **按策略注入**到会话（控制面决定），而不是把宿主 `environ` 整份拷进每个容器。  
4. **演示可证伪**：Demo 在应用内终端起一个**故意不传 `-e`、不挂密钥文件**的 alpine，打印 `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` 为「空 / 不可见」——证明「终端在沙箱里」时看不到本机原始密钥。

```
本机密钥库 ──(策略注入，可选)──► Agent 会话
     │
     └──✗── 默认不挂载 / 不透传 ──► 普通沙箱终端 / 演示容器
```

### 文件系统与网络原则

- **最小挂载**：会话只绑定用户选中的项目目录；其它本机路径对 Agent 不可见（隔离看板与文案与此一致）。  
- **工作目录 = 挂载根**：Agent 的 cwd 落在项目内，降低「相对路径逃逸到宿主」的操作面。  
- **网络可策略化**：出站由沙箱控制面约束（允许调模型 API、限制任意扫内网等），与「密钥是否注入」正交。

### 应用内终端原理

用户看到的不是「本机 iTerm」，而是：

```
xterm.js  ←WebSocket→  App 后端  ←PTY→  enclave --tool <agent>
                                              │
                                              └─► 容器内进程的 stdio
```

- **PTY**：保留交互式 TUI（Claude Code 等）所需的真实终端语义（窗口尺寸、信号）。  
- **语义**：字节流来自沙箱内进程；因此「在终端里查密钥」测的是信任域 C，而不是宿主 shell。  
- **启动顺序**：引擎就绪后先打开应用内终端，再附着会话，避免「工具其实在本机终端里跑、App 只是遥控器」的错觉。

### 与「实现清单」的区别

| 原理（不变的设计约束） | 当前实现（可替换） |
|------------------------|-------------------|
| 执行面与密钥库分属不同信任域 | Enclave + Colima + `global.env` |
| 终端必须附着沙箱 stdio | Python `openpty` + WebSocket + xterm.js |
| 密钥默认不可见、按策略注入 | 不挂密钥文件；demo 用 alpine 证伪 |
| 双击即用、用户不装引擎 | `runtime/` 内置 + 启动时 `colima start` |
| 桌面壳可换 | 现用 pywebview；曾评估 Tauri |

---

## V1 引擎（打进 App）

- **Eclipse Enclave** — Agent 容器沙箱  
- **Colima** — 轻量无头容器引擎（替代 Docker Desktop）  
- **docker CLI** — 供 Enclave 调用  

## 开发

```bash
# 可选：把本机 brew 安装的引擎拷进 App runtime/（模拟「内置」）
./scripts/prepare_runtime_macos.sh

cd apps/sandglass
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 浏览器调试
python run.py

# 桌面窗口（接近分发形态；启动时尝试自动拉起 Colima）
python run_desktop.py
```

打开后走：状态 → 密钥 → 新建会话。

录制 UI 演示（含密钥隔离片段）：

```bash
# 需本机 Playwright + ffmpeg；会短暂写 DEMO 密钥并清理
apps/sandglass/.venv/bin/python scripts/record_demo.py
```

## 打成可双击的 macOS App

```bash
# 本机最好已有 colima/docker/enclave，脚本会拷进 runtime/ 一并打包
./scripts/build_macos_app.sh
open apps/sandglass/dist/Sandglass.app
```

## 分发路线图

1. **现在** — UI + 引擎编排 + `Sandglass.app` 打包脚本  
2. **下一步** — 签名/公证；预置 Lima VM 镜像，首次双击也不再联网下载  
3. **再下一步** — 安装器（dmg）与自动更新  

## 目录

```
apps/sandglass/     Python UI + 引擎 bootstrap + PTY
docs/PRODUCT.md     产品形态
demos/              UI 演示视频
scripts/            打包 / 准备运行时 / 录 demo
apps/desktop/       搁置的 Tauri 草稿
```
