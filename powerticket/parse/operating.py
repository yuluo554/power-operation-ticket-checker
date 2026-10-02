"""倒闸操作票解析器：变电站（operating）与电力线路（line_operating）共用同一布局骨架。

布局契约见 data/ticket_templates/operating.txt 与 line_operating.txt（两者标签一致）。
"""
from __future__ import annotations

import re

from ..models import Evidence, OperationStep, TicketCard
from .common import extract_labeled_fields, extract_numbered_block, labeled_value_re

# capture 为 None 的字段取整行值（(.+)）；人名/编号类用 (\S+) 收紧
_FIELD_SPECS = {
    "ticket_no": ("编号", r"(\S+)"),
    "task": ("操作任务", None),
    "start_time": ("操作开始时间", None),
    "end_time": ("操作结束时间", None),
    "dispatcher": ("发令人", r"(\S+)"),
    "guardian": ("监护人", r"(\S+)"),
    "operator": ("操作人", r"(\S+)"),
    "remarks": ("备注", None),
}
_FIELD_PATTERNS = {
    name: labeled_value_re(label, capture or r"(.+)")
    for name, (label, capture) in _FIELD_SPECS.items()
}
_STEPS_HEADER_RE = re.compile(r"^顺序")


def parse_operating_like(text: str, ticket_type: str) -> TicketCard:
    """倒闸操作票布局 → 参数卡（ticket_type 区分变电站/电力线路）。"""
    card = TicketCard(ticket_type=ticket_type)
    extract_labeled_fields(text, card, _FIELD_PATTERNS)
    card.operation_sequence = [
        OperationStep(no=no, action=action, evidence=Evidence(region="body", quote=quote))
        for no, action, quote in extract_numbered_block(text, _STEPS_HEADER_RE)
    ]
    if not card.operation_sequence:
        card.warnings.append("未解析到操作序列")
    return card


def parse_operating_ticket(text: str) -> TicketCard:
    """变电站倒闸操作票 → 参数卡。"""
    return parse_operating_like(text, "operating")
