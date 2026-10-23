# Sandglass

桌面级 Agent 安全沙箱 MVP：友好 UI 包装 **Eclipse Enclave**（Docker 隔离）。

当前可运行实现是 **Python**（不依赖 Rust / npm 构建）。

## 本机依赖

1. **Python 3.10+**
2. **Docker Desktop**（运行中）
3. **Enclave CLI**（可选，缺了也能打开 UI 看状态页）
   ```bash
   brew install eclipse-enclave
   ```

## 5 分钟 Demo

```bash
cd apps/sandglass
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

浏览器打开：**http://127.0.0.1:8765**

1. **状态** — 确认 Docker / Enclave  
2. **密钥** — 写入 Anthropic / OpenAI Key（存本机 `~/.local/state/enclave/secrets/global.env`）  
3. **新建** — 选项目目录 → 选 Agent → 启动  
4. 内嵌终端与 Agent 交互；**会话**列表可停止  

## 安全模型（MVP）

- Agent 跑在 Enclave 容器内  
- API Key 写在宿主机 secrets，不要求在沙箱内粘贴  
- MCP 宿主机桥接为后续迭代  

## 目录

```
apps/sandglass/     ← 当前 MVP（Python + FastAPI）
apps/desktop/       ← 早期 Tauri 草稿（需较新 Rust，暂搁置）
```
