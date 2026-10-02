"""解析公共件：时间归一、字段入卡合法性门、行级标签/编号块抽取（7 票种共用）。"""
from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional, Tuple

from ..models import Evidence, FieldValue, TicketCard

# 时间类字段名：入卡前统一转 ISO（既定口径 YYYY-MM-DDTHH:MM）
TIME_FIELD_NAMES = {"start_time", "end_time", "plan_start", "plan_end", "permit_start"}

# 编号行：『1  内容』『2. 内容』『3、内容』均可（steps/measures 共用）
NUMBERED_LINE_RE = re.compile(r"^(\d{1,3})[\s．.、]\s*(\S.*)$")
# 安全措施栏头：『安全措施：』或『安全措施（……）：』
MEASURES_HEADER_RE = re.compile(r"^安全措施.*[：:]$")
# 票面打印时刻：2026年10月15日 08:30
CLOCK_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})")


def to_iso_time(raw: str) -> Optional[str]:
    """票面中文时刻 → ISO（YYYY-MM-DDTHH:MM）；缺失/越界/格式非法返回 None。"""
    m = CLOCK_RE.search(raw)
    if not m:
        return None
    year, month, day, hour, minute = m.groups()
    try:
        datetime(int(year), int(month), int(day), int(hour), int(minute))
    except ValueError:
        return None
    return f"{year}-{int(month):02d}-{int(day):02d}T{int(hour):02d}:{minute}"


def labeled_value_re(label: str, capture: str = r"(.+)") -> re.Pattern:
    """『<label>：值』单行抽取；值限定同行（[ \\t] 不吞换行，空值字段不得误抽下一行——M1 回归教训）。"""
    return re.compile(re.escape(label) + r"[：:][ \t]*" + capture)


def put_field(card: TicketCard, name: str, raw: str, quote: str) -> None:
    """字段入卡唯一通道：空值/非法时间一律丢弃+warnings，不得带病入卡。"""
    raw = (raw or "").strip()
    if not raw:
        card.warnings.append(f"字段缺失: {name}")
        return
    value = to_iso_time(raw) if name in TIME_FIELD_NAMES else raw
    if value is None:
        card.warnings.append(f"字段值非法已丢弃: {name}={raw!r}")
        return
    card.fields[name] = FieldValue(
        value=value, evidence=Evidence(region="body", quote=quote)
    )


def extract_labeled_fields(text: str, card: TicketCard, patterns: dict) -> None:
    """按『标签：值』正则表逐字段抽取；未命中即记字段缺失。"""
    for name, pattern in patterns.items():
        m = pattern.search(text)
        put_field(card, name, m.group(1) if m else "", m.group(0).strip() if m else "")


def extract_numbered_block(text: str, header_re: re.Pattern) -> List[Tuple[int, str, str]]:
    """收集编号行块（steps/measures）：header 命中行之后开始，遇非编号非空行即止。

    返回 (序号, 内容, 逐字摘录) 三元组列表。
    """
    items: List[Tuple[int, str, str]] = []
    in_block = False
    for line in text.split("\n"):
        stripped = line.strip()
        if not in_block:
            if header_re.match(stripped):
                in_block = True
            continue
        m = NUMBERED_LINE_RE.match(stripped)
        if m:
            items.append((int(m.group(1)), m.group(2).strip(), stripped))
        elif not stripped:
            continue
        else:
            break
    return items
