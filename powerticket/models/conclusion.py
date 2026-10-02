"""审核结论模型：三级判定 + 风险分级 + 依据挂链（见 plan/04 §3）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

VERDICT_COMPLIANT = "合规"
VERDICT_VIOLATION = "不合规"
VERDICT_MANUAL = "待人工确认"


@dataclass
class Conclusion:
    rule_id: str
    name: str
    verdict: str
    risk: Optional[str] = None
    basis: Optional[Dict[str, Any]] = None
    evidence: List[str] = field(default_factory=list)
    suggestion: str = ""
