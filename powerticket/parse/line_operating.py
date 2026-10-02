"""电力线路倒闸操作票解析器（布局与变电站倒闸操作票一致，契约见 data/ticket_templates/line_operating.txt）。"""
from __future__ import annotations

from ..models import TicketCard
from .operating import parse_operating_like


def parse_line_operating_ticket(text: str) -> TicketCard:
    """电力线路倒闸操作票 → 参数卡。"""
    return parse_operating_like(text, "line_operating")
