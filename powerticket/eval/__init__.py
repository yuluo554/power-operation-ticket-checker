"""内置基准评测（M4，两脚本见 parse_f1.py / endtoend.py）：

- parse_f1：字段级 P/R/F1（生成器真值 vs 解析结果）
- endtoend：植入缺陷检出率 / 误报率 / 判定准确率（M3 全集精确对账口径）
纪律：零 API 依赖可重复；门槛 F1≥0.95、误报 0；指标写入 README。

子模块懒加载（PEP 562）：`py -m powerticket.eval.parse_f1` 直跑时不预导入兄弟模块，
避免 runpy 的 sys.modules 重复导入告警。
"""
from typing import Any

_MODULE_EXPORTS = {
    "run_parse_f1": "parse_f1",
    "run_endtoend": "endtoend",
}

__all__ = list(_MODULE_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _MODULE_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    return getattr(importlib.import_module(f".{target}", __name__), "run")
