"""check_type 实现：统一签名 (rule, card) -> list[Conclusion]（schema 见 plan/04 §3）。

M3 全量 7 类：required_field / time_order（interval + in_window 两模式）/
process_signature / ticket_type_match / measure_coverage / five_prevention / consistency。

结论纪律（既定口径）：
- 字段缺失或值非法 → 待人工确认，不硬判；
- 任务字段缺失时 ticket_type_match 跳过（缺失语义归 required_field，防归因双计）；
- five_prevention 为形式化初查：操作序列本身可判的防误口径，判不合规；
  序列为空无法判定 → 待人工确认。
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Callable, Dict, List, Optional, Set, Tuple

from ..models import (
    VERDICT_COMPLIANT,
    VERDICT_MANUAL,
    VERDICT_VIOLATION,
    Conclusion,
    TicketCard,
)

# 票面字段中文名（证据文案用；字段键为既定口径，见 plan/04 §1）
FIELD_LABELS: Dict[str, str] = {
    "ticket_no": "编号",
    "work_unit": "工作单位",
    "work_head": "工作负责人",
    "crew": "工作班成员",
    "location": "工作地点及设备双重名称",
    "task": "工作任务",
    "plan_start": "计划开始工作时间",
    "plan_end": "计划结束工作时间",
    "permit_start": "许可开始工作时间",
    "permitor": "工作许可人",
    "issuer": "工作票签发人",
    "end_time": "工作终结时间",
    "start_time": "操作/抢修开始时间",
    "dispatcher": "发令人",
    "guardian": "监护人",
    "operator": "操作人",
}


def _label(field: str) -> str:
    return FIELD_LABELS.get(field, field)


def _compliant(rule: dict, evidence: Optional[List[str]] = None) -> Conclusion:
    basis = rule.get("basis", {})
    if not evidence:
        evidence = [f"{basis.get('standard', '')} {basis.get('clause', '')}".strip()]
    return Conclusion(
        rule_id=rule["id"],
        name=rule["name"],
        verdict=VERDICT_COMPLIANT,
        basis=basis,
        evidence=evidence,
        suggestion=rule.get("suggestion", ""),
    )


def _violation(rule: dict, evidence: List[str]) -> Conclusion:
    return Conclusion(
        rule_id=rule["id"],
        name=rule["name"],
        verdict=VERDICT_VIOLATION,
        risk=rule.get("risk"),
        basis=rule.get("basis"),
        evidence=evidence,
        suggestion=rule.get("suggestion", ""),
    )


def _manual(rule: dict, evidence: List[str]) -> Conclusion:
    return Conclusion(
        rule_id=rule["id"],
        name=rule["name"],
        verdict=VERDICT_MANUAL,
        basis=rule.get("basis"),
        evidence=evidence,
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
        return [_violation(rule, [f"缺失字段: {f}（{_label(f)}）" for f in missing])]
    return [_compliant(rule)]


def _parse_iso(value) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def check_time_order(rule: dict, card: TicketCard) -> List[Conclusion]:
    """时间逻辑，params.mode 分派：interval（默认，start<end）/ in_window（target 落区间）。"""
    params = rule.get("params", {})
    if params.get("mode", "interval") == "in_window":
        return _time_in_window(rule, card, params)
    return _time_interval(rule, card, params)


def _time_interval(rule: dict, card: TicketCard, params: dict) -> List[Conclusion]:
    start_field = params.get("start", "start_time")
    end_field = params.get("end", "end_time")
    missing = [f for f in (start_field, end_field) if f not in card.fields]
    if missing:
        return [_manual(rule, [f"字段缺失，无法校核: {f}" for f in missing])]
    start = _parse_iso(card.fields[start_field].value)
    end = _parse_iso(card.fields[end_field].value)
    if start is None or end is None:
        return [_manual(rule, ["时间值无法解析为合法时刻"])]
    if start >= end:
        return [
            _violation(
                rule,
                [
                    f"{_label(start_field)} {start.isoformat()} 晚于/等于 "
                    f"{_label(end_field)} {end.isoformat()}，时间先后逻辑不成立"
                ],
            )
        ]
    return [_compliant(rule)]


def _time_in_window(rule: dict, card: TicketCard, params: dict) -> List[Conclusion]:
    target_field = params.get("target", "permit_start")
    start_field = params.get("start", "plan_start")
    end_field = params.get("end", "plan_end")
    missing = [f for f in (target_field, start_field, end_field) if f not in card.fields]
    if missing:
        return [_manual(rule, [f"字段缺失，无法校核: {f}" for f in missing])]
    target = _parse_iso(card.fields[target_field].value)
    start = _parse_iso(card.fields[start_field].value)
    end = _parse_iso(card.fields[end_field].value)
    if target is None or start is None or end is None:
        return [_manual(rule, ["时间值无法解析为合法时刻"])]
    if start <= target <= end:
        return [_compliant(rule)]
    detail = (
        f"{_label(target_field)} {target.isoformat()} 落在 "
        f"{_label(start_field)} {start.isoformat()} 至 {_label(end_field)} {end.isoformat()} 区间之外"
    )
    if params.get("on_violation") == "manual":
        return [_manual(rule, [detail + "，超出计划工作时间应办理工作变更/延期手续"])]
    return [_violation(rule, [detail])]


def check_process_signature(rule: dict, card: TicketCard) -> List[Conclusion]:
    """签字链缺环检查：签发/许可环节人员留空（操作票双签归 required_field 语义）。"""
    fields = rule.get("params", {}).get("fields", [])
    missing = [
        f
        for f in fields
        if f not in card.fields or not str(card.fields[f].value).strip()
    ]
    if missing:
        return [
            _violation(rule, [f"签字环节缺失: {_label(f)}（{f}）" for f in missing])
        ]
    chain = " → ".join(_label(f) for f in fields)
    return [_compliant(rule, evidence=[f"签字链完整: {chain}"])]


def check_ticket_type_match(rule: dict, card: TicketCard) -> List[Conclusion]:
    """票种与停电需求匹配：第二种工作票（不需停电）的任务不得含需停电作业表述。"""
    params = rule.get("params", {})
    field = params.get("field", "task")
    fv = card.fields.get(field)
    if fv is None or not str(fv.value).strip():
        # 任务缺失时本项跳过：缺失语义归 required_field，避免同一缺陷归因双计（M3 定稿）
        return []
    text = str(fv.value)
    if any(term in text for term in params.get("exempt_terms", [])):
        return [_compliant(rule, evidence=[f"任务未见停电作业表述: {text}"])]
    hit = next((t for t in params.get("forbidden_terms", []) if t in text), None)
    if hit:
        return [
            _violation(
                rule,
                [f"任务含『{hit}』表述，与本票种适用范围（不需停电）冲突: {text}"],
            )
        ]
    return [_compliant(rule, evidence=["任务未发现与本票种适用范围冲突的表述"])]


def check_measure_coverage(rule: dict, card: TicketCard) -> List[Conclusion]:
    """技术措施四要素覆盖（停电/验电/接地/标示牌遮栏），直接消费 card.safety_measures。"""
    elements: Dict[str, List[str]] = rule.get("params", {}).get("elements", {})
    if not card.safety_measures:
        return [_violation(rule, ["未解析到任何安全措施条目，保证安全的技术措施全部缺失"])]
    missing = [
        name
        for name, keywords in elements.items()
        if not any(kw in m.text for m in card.safety_measures for kw in keywords)
    ]
    if missing:
        return [
            _violation(
                rule,
                [
                    f"安全措施缺少技术措施要素: {'、'.join(missing)}"
                    f"（共 {len(card.safety_measures)} 条措施）"
                ],
            )
        ]
    return [
        _compliant(
            rule,
            evidence=[
                f"技术措施要素覆盖齐全: {'、'.join(elements)}"
                f"（共 {len(card.safety_measures)} 条措施）"
            ],
        )
    ]


# ---------------------------------------------------------------------------
# 五防形式化检查（防误口径逐条挂规范出处；序列内可形式化判定的三类）
# ---------------------------------------------------------------------------

def _fp_load_disconnector(steps) -> List[str]:
    """防带负荷拉（合）隔离开关：拉开隔离开关前，序列中必须已有断开断路器的操作步。"""
    breaker_opened = False
    issues: List[str] = []
    for s in steps:
        text = s.action
        if "断路器" in text and "断开" in text:
            breaker_opened = True
        if text.startswith("拉开") and "隔离开关" in text and not breaker_opened:
            issues.append(
                f"第{s.no}步『{text}』：拉开隔离开关前未见断开断路器操作"
                f"（防带负荷拉（合）隔离开关）"
            )
    return issues


def _fp_ground_close(steps) -> List[str]:
    """防带接地线（开关）合闸送电：合闸前，先前装设的接地线/接地开关必须已拆除或拉开。"""
    issues: List[str] = []
    ground_at: Optional[int] = None
    for s in steps:
        text = s.action
        if "接地" in text and ("拆除" in text or "拉开" in text):
            ground_at = None
        elif "接地" in text and ("装设" in text or "挂" in text or "合上" in text):
            ground_at = s.no
        if ground_at is not None and "合上" in text and ("断路器" in text or "隔离开关" in text):
            issues.append(
                f"第{s.no}步『{text}』：合闸送电前第{ground_at}步所设接地线未见拆除"
                f"（防带接地线（开关）合闸送电）"
            )
            ground_at = None
    return issues


def _fp_grounding_after_test(steps) -> List[str]:
    """防带电挂（合）接地线（接地开关）：装设接地线前（含同一步）应已验电。"""
    issues: List[str] = []
    tested = False
    for s in steps:
        text = s.action
        if "验电" in text:
            tested = True
        if ("装设接地" in text or "挂接地线" in text or "合上接地" in text) and not tested:
            issues.append(
                f"第{s.no}步『{text}』：装设接地线前未见验电操作"
                f"（防带电挂（合）接地线（接地开关））"
            )
            tested = True
    return issues


_FIVE_PREVENTION_VARIANTS: Dict[str, Callable] = {
    "no_load_disconnector": _fp_load_disconnector,
    "no_ground_close": _fp_ground_close,
    "grounding_after_test": _fp_grounding_after_test,
}


def check_five_prevention(rule: dict, card: TicketCard) -> List[Conclusion]:
    variants = rule.get("params", {}).get("variants", [])
    if not card.operation_sequence:
        return [_manual(rule, ["操作序列为空，无法进行五防形式化检查"])]
    issues: List[str] = []
    for v in variants:
        fn = _FIVE_PREVENTION_VARIANTS.get(v)
        if fn:
            issues.extend(fn(card.operation_sequence))
    if issues:
        return [_violation(rule, issues)]
    return [
        _compliant(
            rule,
            evidence=[
                f"五防形式化检查通过（共 {len(card.operation_sequence)} 项操作，"
                f"覆盖 {len(variants)} 项防误口径）"
            ],
        )
    ]


# ---------------------------------------------------------------------------
# 一致性：设备双重名称 × 电压等级互证
# ---------------------------------------------------------------------------

# 『110kV东湖线111断路器』→（线名, 设备编号, 设备类型）与 kV 标注；同一设备多处标注应一致
_DEVICE_KV_RE = re.compile(
    r"(\d+)kV([一-鿿]{2,8}?线)([0-9\-号杆分段]{1,12}?)(断路器|隔离开关|接地开关)"
)


def check_consistency(rule: dict, card: TicketCard) -> List[Conclusion]:
    params = rule.get("params", {})
    sources = params.get("sources", ["task", "steps"])
    texts: List[str] = []
    if "task" in sources and card.fields.get("task"):
        texts.append(str(card.fields["task"].value))
    if "steps" in sources:
        texts.extend(s.action for s in card.operation_sequence)
    markings: Dict[Tuple[str, str, str], Set[str]] = {}
    for text in texts:
        for kv, line, dev, kind in _DEVICE_KV_RE.findall(text):
            markings.setdefault((line, dev, kind), set()).add(kv)
    conflicts = sorted(
        f"设备{''.join(identity)} 电压等级标注不一致: {'/'.join(sorted(kvs))}kV"
        for identity, kvs in markings.items()
        if len(kvs) > 1
    )
    if conflicts:
        return [_violation(rule, conflicts)]
    if not markings:
        return [_compliant(rule, evidence=["未发现可互证的设备电压等级标注，本项未发现冲突"])]
    return [
        _compliant(
            rule,
            evidence=[f"设备电压等级标注互证一致（{len(markings)} 处设备标注）"],
        )
    ]
