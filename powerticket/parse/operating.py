"""变电站倒闸操作票解析器（骨架版：覆盖 demo 样例槽位，M2 全量细化）。"""
from __future__ import annotations

import re

from ..models import Evidence, FieldValue, OperationStep, TicketCard

_FIELD_PATTERNS = {
    "ticket_no": re.compile(r"编号[：:]\s*(\S+)"),
    "task": re.compile(r"操作任务[：:]\s*(.+)"),
    "start_time": re.compile(r"开始时间[：:]\s*(.+)"),
    "end_time": re.compile(r"结束时间[：:]\s*(.+)"),
    "guardian": re.compile(r"监护人[：:]\s*(\S+)"),
    "operator": re.compile(r"操作人[：:]\s*(\S+)"),
}
_STEP_PATTERN = re.compile(r"^\s*(\d{1,3})[\s．.、]\s*(\S.*)$")
_TIME_PATTERN = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})")


def _to_iso_time(raw: str):
    m = _TIME_PATTERN.search(raw)
    if not m:
        return None
    year, month, day, hour, minute = m.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}T{int(hour):02d}:{minute}"


def parse_operating_ticket(text: str) -> TicketCard:
    card = TicketCard(ticket_type="operating")
    for name, pattern in _FIELD_PATTERNS.items():
        m = pattern.search(text)
        if not m:
            card.warnings.append(f"字段缺失: {name}")
            continue
        raw = m.group(1).strip()
        value = _to_iso_time(raw) if name in ("start_time", "end_time") else raw
        if value is None:
            # 合法性校验：格式非法即丢弃，不得带病入卡
            card.warnings.append(f"字段值非法已丢弃: {name}={raw!r}")
            continue
        card.fields[name] = FieldValue(
            value=value, evidence=Evidence(region="body", quote=m.group(0).strip())
        )

    in_steps = False
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("顺序"):
            in_steps = True
            continue
        if stripped.startswith("备注"):
            in_steps = False
            continue
        if not in_steps:
            continue
        m = _STEP_PATTERN.match(line)
        if m:
            card.operation_sequence.append(
                OperationStep(
                    no=int(m.group(1)),
                    action=m.group(2).strip(),
                    evidence=Evidence(region="body", quote=stripped),
                )
            )
    if not card.operation_sequence:
        card.warnings.append("未解析到操作序列")
    return card
