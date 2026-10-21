"""数据目录解析：源码态 / editable 安装 / 常规安装（wheel）三种形态统一出口。

为什么需要这个模块（2026-10-22 v0.2.0 修打包时补）：

各模块原先统一用 `Path(__file__).resolve().parents[2] / "data"` 定位数据，
这在源码态成立（`powerticket/rules/__init__.py` → 仓库根），但**装成 wheel 后不成立**：
`<venv>/Lib/site-packages/powerticket/` 的 parents[2] 是 `<venv>/Lib`，
那里没有 `data/`。实测装 wheel 后 `demo` 直接 `文件不存在: .../site-packages/data/samples/...`。

解析顺序（先命中先用）：

1. 环境变量 `POWERTICKET_DATA_DIR`（部署可覆盖，便于容器/共享盘）；
2. 源码态：包目录上溯找得到 `data/knowledge/rules` 的仓库根；
3. 已安装态：`<prefix>/share/powerticket`（由 pyproject 的
   `[tool.setuptools.data-files]` 装入；wheel 与 sdist 都覆盖）。

都找不到时返回第 3 项（不抛错）——让调用方按既有语义报「文件不存在」，
错误信息里能看到实际找过的路径，比在 import 期直接崩更利于诊断。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

ENV_VAR = "POWERTICKET_DATA_DIR"

#: 源码态判定锚：仓库根下必须有这个相对路径
_SOURCE_ANCHOR = Path("data") / "knowledge" / "rules"

#: 包目录：.../powerticket
_PACKAGE_DIR = Path(__file__).resolve().parent

_cached: Optional[Path] = None


def _source_root() -> Optional[Path]:
    """源码态仓库根：从包目录逐级上溯，找含 data/knowledge/rules 的那一层。"""
    for candidate in _PACKAGE_DIR.parents:
        if (candidate / _SOURCE_ANCHOR).is_dir():
            return candidate
    return None


def _installed_data_dir() -> Path:
    """已安装态：<prefix>/share/powerticket。

    sysconfig 的 data 方案指向 venv 根（Windows 下就是 venv 目录本身），
    因此 `share/powerticket` 落在 `<venv>/share/powerticket`。
    """
    try:
        import sysconfig

        prefix = Path(sysconfig.get_path("data"))
    except Exception:  # pragma: no cover - 极端环境兜底
        prefix = Path(sys.prefix)
    return prefix / "share" / "powerticket"


def data_dir() -> Path:
    """返回数据根目录（含 knowledge/ samples/ ticket_templates/ generator/）。"""
    global _cached
    if _cached is not None:
        return _cached

    env = os.environ.get(ENV_VAR)
    if env:
        _cached = Path(env).expanduser().resolve()
        return _cached

    src = _source_root()
    if src is not None:
        _cached = src / "data"
        return _cached

    _cached = _installed_data_dir()
    return _cached


def reset_cache() -> None:
    """清缓存（测试用：同一进程内切换源码态/已安装态）。"""
    global _cached
    _cached = None


def sub(*parts: str) -> Path:
    """`sub("samples", "gen")` → `<data>/samples/gen`，省掉到处拼 data。"""
    return data_dir().joinpath(*parts)
