"""解析层：清洗 → 票种路由 → 槽位抽取 → 参数卡（见 plan/04 §2）。"""
from __future__ import annotations

from typing import Optional

from ..models import TicketCard
from .cleaning import normalize_text
from .operating import parse_operating_ticket


class ParseError(Exception):
    """解析失败（票种无法识别 / 解析器未实现 / 输入为空 / 文件缺失）。"""


# 各票种解析器注册表；M2 补齐其余 6 票种
_PARSERS = {
    "operating": parse_operating_ticket,
}

# 票种路由关键词（骨架版：识别即可；M2 细化变电/线路操作票与工作票子类区分）
_TYPE_KEYWORDS = [
    ("work_first", "第一种工作票"),
    ("work_second", "第二种工作票"),
    ("emergency_repair", "抢修单"),
    ("line_operating", "电力线路倒闸操作票"),
    ("operating", "倒闸操作票"),
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
    if parser is None:
        raise ParseError(f"票种 {ticket_type} 已识别，但解析器未实现（计划 M2）。")
    return parser(normalized)
