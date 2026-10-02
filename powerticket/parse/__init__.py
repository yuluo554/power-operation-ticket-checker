"""解析层：清洗 → 票种路由 → 槽位抽取 → 参数卡（见 plan/04 §2）。"""
from __future__ import annotations

from typing import Optional

from ..models import TicketCard
from .cleaning import normalize_text
from .emergency_repair import parse_emergency_repair
from .line_operating import parse_line_operating_ticket
from .line_work_first import parse_line_work_first
from .line_work_second import parse_line_work_second
from .operating import parse_operating_ticket
from .work_first import parse_work_first
from .work_second import parse_work_second


class ParseError(Exception):
    """解析失败（票种无法识别 / 解析器未注册 / 输入为空）。"""


# 7 票种解析器注册表（M2 全覆盖）
_PARSERS = {
    "operating": parse_operating_ticket,
    "line_operating": parse_line_operating_ticket,
    "work_first": parse_work_first,
    "work_second": parse_work_second,
    "line_work_first": parse_line_work_first,
    "line_work_second": parse_line_work_second,
    "emergency_repair": parse_emergency_repair,
}

# 票种路由关键词——顺序门控：线路专用关键词必须排在同款通用关键词之前，
# 『电力线路第一种工作票』含『第一种工作票』子串、『电力线路倒闸操作票』含『倒闸操作票』子串，
# 先命中先返回，倒序会把线路票误路由成变电站票（负例测试锁定）
_TYPE_KEYWORDS = [
    ("line_operating", "电力线路倒闸操作票"),
    ("line_work_first", "电力线路第一种工作票"),
    ("line_work_second", "电力线路第二种工作票"),
    ("operating", "倒闸操作票"),
    ("work_first", "第一种工作票"),
    ("work_second", "第二种工作票"),
    ("emergency_repair", "抢修单"),
]


def detect_ticket_type(text: str) -> Optional[str]:
    for code, keyword in _TYPE_KEYWORDS:
        if keyword in text:
            return code
    return None


def parse_ticket(text: str) -> TicketCard:
    if not text or not text.strip():
        raise ParseError("输入为空：请提供票据文本。")
    normalized = normalize_text(text)
    ticket_type = detect_ticket_type(normalized)
    if ticket_type is None:
        raise ParseError("无法识别票种：未命中任何票样关键词（支持票种见 plan/04 §1）。")
    parser = _PARSERS.get(ticket_type)
    if parser is None:  # 防御：关键词表与注册表失同步时显式报错，不走裸 traceback
        raise ParseError(f"票种 {ticket_type} 已识别，但解析器未注册。")
    return parser(normalized)
