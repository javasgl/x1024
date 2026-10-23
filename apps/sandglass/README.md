# Sandglass

自带沙箱引擎的桌面入口。

技术原理（信任边界、密钥、分层隔离、应用内终端）见仓库根目录 [README.md](../../README.md#技术原理)。产品形态见 [docs/PRODUCT.md](../../docs/PRODUCT.md)。

```bash
# 从仓库根目录：把 colima/docker/enclave 拷进 runtime/（模拟内置）
../../scripts/prepare_runtime_macos.sh

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run_desktop.py    # 原生窗口
# 或
python run.py            # 仅 http://127.0.0.1:8765
```

正式分发时 `runtime/` 会打进 `.app`，用户无需 brew。
