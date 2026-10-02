"""电力线路第二种工作票解析器（布局契约见 data/ticket_templates/line_work_second.txt）。"""
from __future__ import annotations

from ..models import TicketCard
from .work import parse_work_like


def parse_line_work_second(text: str) -> TicketCard:
    """电力线路第二种工作票 → 参数卡。"""
    return parse_work_like(text, "line_work_second", "线路名称及杆号（双重名称）")
