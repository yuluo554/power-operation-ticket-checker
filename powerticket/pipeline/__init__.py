"""端到端编排：解析（可选 LLM 兜底）→ 校核 → 汇总（CLI 与 Web 共用）。"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Optional

from ..llm.fallback import parse_ticket_with_fallback
from ..models import Conclusion
from ..rules import load_rules, run_checks


def run_pipeline(
    text: str, rules_path: Optional[str] = None, allow_llm_fallback: bool = False
) -> Dict[str, Any]:
    """allow_llm_fallback 默认关闭：core 通路零 API 依赖、纯确定性（M4 口径）。"""
    card = parse_ticket_with_fallback(text, allow_llm=allow_llm_fallback)
    rules = load_rules(rules_path)
    conclusions = run_checks(card, rules)
    summary: Dict[str, int] = {"合规": 0, "不合规": 0, "待人工确认": 0}
    for c in conclusions:
        summary[c.verdict] = summary.get(c.verdict, 0) + 1
    return {
        "card": card.to_dict(),
        "warnings": list(card.warnings),
        "conclusions": [asdict(c) for c in conclusions],
        "summary": summary,
    }
