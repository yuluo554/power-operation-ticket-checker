"""端到端编排：解析 → 校核 → 汇总（CLI 与 Web 共用）。"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Optional

from ..models import Conclusion
from ..parse import parse_ticket
from ..rules import load_rules, run_checks


def run_pipeline(text: str, rules_path: Optional[str] = None) -> Dict[str, Any]:
    card = parse_ticket(text)
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
