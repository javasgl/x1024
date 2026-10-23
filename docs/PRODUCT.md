# Sandglass 产品形态

## 一句话

**自带沙箱引擎的桌面 App**：用户双击即可用，不必自行安装 Docker Desktop / Colima / Enclave。

## V1 引擎策略（已选定）

在 App 内捆绑并托管：

| 组件 | 作用 |
|------|------|
| **Eclipse Enclave** | Agent 容器沙箱、网络策略、secrets 注入 |
| **Colima + Lima** | 轻量无头容器引擎（替代 Docker Desktop） |
| **docker CLI** | Enclave 调 Docker API 的客户端 |

App 启动时：

1. 把内置 `runtime/` 加到 `PATH`  
2. 若 Colima 未运行 → 静默 `colima start`  
3. 打开桌面窗口（内嵌 Web UI）  

用户无感「装引擎」；代价是安装包体积较大（含 Linux 镜像时通常数百 MB 级）。

## 明确不做（V1）

- 要求用户 `brew install` 一堆工具  
- 依赖 Docker Desktop / OrbStack 作为正式分发前提  
- 把配置文件丢给用户手改  

## 后续可选

若安装包必须更小：用 OS 级沙箱（Seatbelt 等）替换 Enclave+Colima，仍保持「双击即用」产品形态。

## 目录约定

```
apps/sandglass/
  runtime/                 # 不进 git；prepare 脚本生成
    darwin-arm64/
      bin/enclave
      bin/docker
      bin/colima
      ...
  sandglass/
  static/
  run.py                   # 开发：仅 HTTP
  run_desktop.py           # 桌面窗口入口（接近分发形态）
scripts/prepare_runtime_macos.sh
```
