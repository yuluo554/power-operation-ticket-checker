"""依据闸（status gate）双对照：plan/04:70/100 的「待核对不得下确定性结论」落地验证。

阳性：basis.status != 「已核对」的规则，其「不合规」结论必须降级为「待人工确认」。
阴性：同一条规则改成「已核对」后必须仍是「不合规」——证明闸门不是「把所有东西都降级」。

口径（本轮 DEC-1 = A1 窄闸）：只降「不合规」；「合规」与既有「待人工确认」不动。
闸门位置在 run_checks 的 check() 之后 —— 若写成「跳过规则不执行」，
required_field 的缺失检测会整块消失（字段缺失本身就是判据）。
"""
from __future__ import annotations

import json
from pathlib import Path

from powerticket.models import FieldValue, TicketCard
from powerticket.rules import load_rules, run_checks

ROOT = Path(__file__).resolve().parents[1]


def _rule(status: str) -> dict:
    """一条必然判「不合规」的 required_field 规则：卡片缺 ticket_no 必报缺失。"""
    return {
        "id": "R-GATE-001",
        "name": "依据闸测试规则（必填项完整性）",
        "check_type": "required_field",
        "applies_to": ["operating"],
        "params": {"fields": ["ticket_no"]},
        "basis": {
            "standard": "Q/GDW 1799.1-2013",
            "clause": "附录 倒闸操作票格式",
            "status": status,
        },
    }


def _card() -> TicketCard:
    card = TicketCard(ticket_type="operating")
    card.fields = {"task": FieldValue(value="将35kV南岭线312断路器由运行转为检修")}
    return card


def _verdict(rule: dict) -> str:
    conclusions = run_checks(_card(), [rule])
    assert len(conclusions) == 1, conclusions
    return conclusions[0].verdict


def test_pending_rule_violation_downgraded_to_manual():
    """阳性对照：待核对规则判出的「不合规」必须降级为「待人工确认」。"""
    assert _verdict(_rule("待核对")) == "待人工确认"


def test_verified_rule_violation_kept():
    """阴性对照：同一条规则改成已核对，结论必须仍是「不合规」（闸门不越权）。"""
    assert _verdict(_rule("已核对")) == "不合规"


def test_gate_does_not_swallow_missing_field_detection():
    """闸门不得变成「跳过规则」：降级后结论仍存在，且证据仍指向缺失字段。"""
    conclusions = run_checks(_card(), [_rule("待核对")])
    assert conclusions, "待核对规则被整条跳过 = 漏检（required_field 缺失检测消失）"
    assert any("ticket_no" in e for e in conclusions[0].evidence)


def test_gate_keeps_compliant_verdict():
    """窄闸口径：待核对规则的「合规」结论保留，不降级。"""
    card = TicketCard(ticket_type="operating")
    card.fields = {"ticket_no": FieldValue(value="CZ-2026-0001")}
    rule = _rule("待核对")
    conclusions = run_checks(card, [rule])
    assert len(conclusions) == 1
    assert conclusions[0].verdict == "合规"


def test_production_rules_never_yield_violation_when_pending():
    """生产规则库全量回归：basis.status 非「已核对」的规则不得产出「不合规」。"""
    rules = load_rules()
    samples = sorted((ROOT / "data" / "samples" / "gen").glob("*.txt"))
    assert samples, "样例目录为空"
    from powerticket.parse import parse_ticket

    bad = []
    for f in samples:
        card = parse_ticket(f.read_text(encoding="utf-8"))
        for c in run_checks(card, rules):
            status = (c.basis or {}).get("status")
            if status != "已核对" and c.verdict == "不合规":
                bad.append((f.name, c.rule_id, status))
    assert not bad, bad[:5]


def test_production_rules_still_have_pending_entries():
    """红线守卫：数据侧仍应是 9 已核对 / 30 待核对（不许把待核对改成已核对）。"""
    rules = load_rules()
    statuses = {}
    for r in rules:
        statuses[r["basis"]["status"]] = statuses.get(r["basis"]["status"], 0) + 1
    assert statuses.get("待核对") == 30, statuses
    assert statuses.get("已核对") == 9, statuses
    # 与真值台账交叉核对，防止测试被"改数据"绕过
    raw_total = 0
    for f in sorted((ROOT / "data" / "knowledge" / "rules").glob("*.json")):
        raw_total += len(json.loads(f.read_text(encoding="utf-8"))["rules"])
    assert raw_total == len(rules) == 39, (raw_total, len(rules))
