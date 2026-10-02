"""check_type 实现：统一签名 (rule, card) -> list[Conclusion]。"""
from __future__ import annotations

from datetime import datetime
from typing import List

from ..models import (
    VERDICT_COMPLIANT,
    VERDICT_MANUAL,
    VERDICT_VIOLATION,
    Conclusion,
    TicketCard,
)


def _compliant(rule: dict) -> Conclusion:
    basis = rule.get("basis", {})
    return Conclusion(
        rule_id=rule["id"],
        name=rule["name"],
        verdict=VERDICT_COMPLIANT,
        basis=basis,
        evidence=[f"{basis.get('standard', '')} {basis.get('clause', '')}".strip()],
        suggestion=rule.get("suggestion", ""),
    )


def check_required_field(rule: dict, card: TicketCard) -> List[Conclusion]:
    fields = rule.get("params", {}).get("fields", [])
    missing = [
        f
        for f in fields
        if f not in card.fields or not str(card.fields[f].value).strip()
    ]
    if missing:
        return [
            Conclusion(
                rule_id=rule["id"],
                name=rule["name"],
                verdict=VERDICT_VIOLATION,
                risk=rule.get("risk"),
                basis=rule.get("basis"),
                evidence=[f"缺失字段: {f}" for f in missing],
                suggestion=rule.get("suggestion", ""),
            )
        ]
    return [_compliant(rule)]


def check_time_order(rule: dict, card: TicketCard) -> List[Conclusion]:
    params = rule.get("params", {})
    start_field = params.get("start", "start_time")
    end_field = params.get("end", "end_time")
    missing = [f for f in (start_field, end_field) if f not in card.fields]
    if missing:
        return [
            Conclusion(
                rule_id=rule["id"],
                name=rule["name"],
                verdict=VERDICT_MANUAL,
                basis=rule.get("basis"),
                evidence=[f"字段缺失，无法校核: {f}" for f in missing],
                suggestion=rule.get("suggestion", ""),
            )
        ]
    try:
        start = datetime.fromisoformat(str(card.fields[start_field].value))
        end = datetime.fromisoformat(str(card.fields[end_field].value))
    except ValueError:
        return [
            Conclusion(
                rule_id=rule["id"],
                name=rule["name"],
                verdict=VERDICT_MANUAL,
                basis=rule.get("basis"),
                evidence=["时间值无法解析为合法时刻"],
                suggestion=rule.get("suggestion", ""),
            )
        ]
    if start >= end:
        return [
            Conclusion(
                rule_id=rule["id"],
                name=rule["name"],
                verdict=VERDICT_VIOLATION,
                risk=rule.get("risk"),
                basis=rule.get("basis"),
                evidence=[f"开始时刻 {start.isoformat()} 晚于/等于结束时刻 {end.isoformat()}"],
                suggestion=rule.get("suggestion", ""),
            )
        ]
    return [_compliant(rule)]
