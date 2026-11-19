# 预设（presets）

预设就是放在这个目录里的配置文件，格式和根目录的 `config.json` 完全一样。用 `--preset 名称` 启动时，程序读取 `presets/名称.json`，不读 `config.json`。

| 文件 | 说明 | 启动命令 |
|---|---|---|
| `soxl-soxs.json` | **SOXL / SOXS Float**：本项目最早的版本，盯 SOXL（3 倍做多半导体）和 SOXS（3 倍做空半导体） | `./scripts/start.sh soxl-soxs` |

## 新建预设

1. 复制 `soxl-soxs.json`，改个文件名，比如 `ai.json`。
2. 把 `symbols` 改成你要看的代码，比如 `["NVDA", "AMD", "SMCI"]`；`name` 字段只是给自己看的备注，可以随便写。
3. 启动：`./scripts/start.sh ai`；开机自启：`./scripts/install_autostart.sh ai`。
