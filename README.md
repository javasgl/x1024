# Sandglass

**自带沙箱引擎的桌面 App**：双击即用，用户不必自行安装 Docker Desktop / Colima / Enclave。

产品说明见 [docs/PRODUCT.md](docs/PRODUCT.md)。

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
apps/sandglass/     Python UI + 引擎 bootstrap
docs/PRODUCT.md     产品形态
scripts/            打包/准备运行时
apps/desktop/       搁置的 Tauri 草稿
```
