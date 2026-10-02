"""事故紧急抢修单解析器（布局契约见 data/ticket_templates/emergency_repair.txt）。"""
from __future__ import annotations

from ..models import Evidence, SafetyMeasure, TicketCard
from .common import (
    MEASURES_HEADER_RE,
    extract_labeled_fields,
    extract_numbered_block,
    labeled_value_re,
)

_FIELD_SPECS = {
    "ticket_no": ("编号", r"(\S+)"),
    "work_unit": ("抢修单位", None),
    "task": ("抢修任务（设备双重名称及故障简况）", None),
    "start_time": ("抢修开始时间", None),
    "end_time": ("抢修结束时间", None),
    "work_head": ("工作负责人", r"(\S+)"),
    "crew": ("工作班成员", None),
    "permitor": ("许可人（值班负责人）", r"(\S+)"),
    "remarks": ("备注", None),
}
_FIELD_PATTERNS = {
    name: labeled_value_re(label, capture or r"(.+)")
    for name, (label, capture) in _FIELD_SPECS.items()
}


def parse_emergency_repair(text: str) -> TicketCard:
    """事故紧急抢修单 → 参数卡。"""
    card = TicketCard(ticket_type="emergency_repair")
    extract_labeled_fields(text, card, _FIELD_PATTERNS)
    card.safety_measures = [
        SafetyMeasure(no=no, text=item, evidence=Evidence(region="body", quote=quote))
        for no, item, quote in extract_numbered_block(text, MEASURES_HEADER_RE)
    ]
    if not card.safety_measures:
        card.warnings.append("未解析到安全措施")
    return card
