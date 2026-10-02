"""工作票共用解析骨架：第一/二种 × 变电站/电力线路四票种仅工作地点栏标签不同。

布局契约见 data/ticket_templates/work_first.txt / work_second.txt /
line_work_first.txt / line_work_second.txt。
"""
from __future__ import annotations

import re

from ..models import Evidence, SafetyMeasure, TicketCard
from .common import (
    MEASURES_HEADER_RE,
    extract_labeled_fields,
    extract_numbered_block,
    labeled_value_re,
    put_field,
)

# 『计划工作时间：自…至…』一行双时刻：自/至 为槽位分隔拆 plan_start/plan_end（M2 定稿）
_PLAN_TIME_RE = re.compile(r"计划工作时间[：:][ \t]*自([^至]*)至(.*)")

_SCALAR_SPECS = {
    "ticket_no": ("编号", r"(\S+)"),
    "work_unit": ("工作单位", None),
    "work_head": ("工作负责人", r"(\S+)"),
    "crew": ("工作班成员", None),
    "task": ("工作任务", None),
    "issuer": ("工作票签发人", r"(\S+)"),
    "permit_start": ("许可开始工作时间", None),
    "permitor": ("工作许可人", r"(\S+)"),
    "end_time": ("工作终结时间", None),
    "remarks": ("备注", None),
}


def parse_work_like(text: str, ticket_type: str, location_label: str) -> TicketCard:
    """工作票布局 → 参数卡；location_label 区分变电站/线路版工作地点栏。"""
    card = TicketCard(ticket_type=ticket_type)
    patterns = {
        name: labeled_value_re(label, capture or r"(.+)")
        for name, (label, capture) in _SCALAR_SPECS.items()
    }
    patterns["location"] = labeled_value_re(location_label)
    extract_labeled_fields(text, card, patterns)

    m = _PLAN_TIME_RE.search(text)
    if m:
        quote = m.group(0).strip()
        put_field(card, "plan_start", m.group(1), quote)
        put_field(card, "plan_end", m.group(2), quote)
    else:
        card.warnings.extend(["字段缺失: plan_start", "字段缺失: plan_end"])

    card.safety_measures = [
        SafetyMeasure(no=no, text=item, evidence=Evidence(region="body", quote=quote))
        for no, item, quote in extract_numbered_block(text, MEASURES_HEADER_RE)
    ]
    if not card.safety_measures:
        card.warnings.append("未解析到安全措施")
    return card
