"""变电站（发电厂）第一种工作票解析器（布局契约见 data/ticket_templates/work_first.txt）。"""
from __future__ import annotations

from ..models import TicketCard
from .work import parse_work_like


def parse_work_first(text: str) -> TicketCard:
    """变电站（发电厂）第一种工作票 → 参数卡。"""
    return parse_work_like(text, "work_first", "工作地点及设备双重名称")
