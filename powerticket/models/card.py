"""票面参数卡：统一中间表示（schema v0.1，见 plan/04）。"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

TICKET_TYPE_NAMES = {
    "operating": "变电站倒闸操作票",
    "line_operating": "电力线路倒闸操作票",
    "work_first": "变电站（发电厂）第一种工作票",
    "work_second": "变电站（发电厂）第二种工作票",
    "line_work_first": "电力线路第一种工作票",
    "line_work_second": "电力线路第二种工作票",
    "emergency_repair": "事故紧急抢修单",
}


@dataclass
class Evidence:
    """证据：票面区域 + 原文逐字摘录。"""

    region: str
    quote: str


@dataclass
class FieldValue:
    value: Any
    confidence: float = 1.0
    evidence: Optional[Evidence] = None


@dataclass
class OperationStep:
    no: int
    action: str
    evidence: Optional[Evidence] = None


@dataclass
class SafetyMeasure:
    """安全措施条目（工作票/抢修单逐条措施，M2 定稿：独立容器与 operation_sequence 对称）。"""

    no: int
    text: str
    evidence: Optional[Evidence] = None


@dataclass
class TicketCard:
    ticket_type: str
    fields: Dict[str, FieldValue] = field(default_factory=dict)
    operation_sequence: List[OperationStep] = field(default_factory=list)
    safety_measures: List[SafetyMeasure] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["ticket_type_name"] = TICKET_TYPE_NAMES.get(self.ticket_type, "未知票种")
        return data
