import json
from pathlib import Path

import pytest

from powerticket.models import FieldValue, TicketCard
from powerticket.parse import parse_ticket
from powerticket.rules import RuleError, load_rules, run_checks

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "samples" / "sample-operating-01.txt"

TICKET_TYPES = [
    "operating",
    "line_operating",
    "work_first",
    "work_second",
    "line_work_first",
    "line_work_second",
    "emergency_repair",
]


def test_load_demo_rules():
    rules = load_rules()
    ids = {r["id"] for r in rules}
    assert {"R-OP-001", "R-OP-002"} <= ids
    # 结论纪律：每条规则必须挂出处
    for r in rules:
        assert r["basis"]["standard"]


def test_basic_rules_cover_all_ticket_types():
    # M2：required_field + time_order 基础通路覆盖全部 7 票种
    rules = load_rules()
    for tp in TICKET_TYPES:
        types = {r["check_type"] for r in rules if tp in r["applies_to"]}
        assert {"required_field", "time_order"} <= types, tp


def test_gating_no_cross_ticket_type_fire():
    # 类目门控：空 work_first 卡只命中 work_first 自己的规则，operating 系不得跨票种触发
    rules = load_rules()
    card = TicketCard(ticket_type="work_first")
    fired = {c.rule_id for c in run_checks(card, rules)}
    assert fired, "work_first 基础规则应对空卡报必填缺失"
    op_rule_ids = {r["id"] for r in rules if "operating" in r["applies_to"]}
    assert not fired & op_rule_ids, sorted(fired & op_rule_ids)


def test_compliant_sample():
    card = parse_ticket(SAMPLE.read_text(encoding="utf-8"))
    verdicts = {c.rule_id: c.verdict for c in run_checks(card, load_rules())}
    assert verdicts == {"R-OP-001": "合规", "R-OP-002": "合规"}


def test_missing_field_flagged():
    card = parse_ticket(SAMPLE.read_text(encoding="utf-8"))
    del card.fields["guardian"]
    c = next(x for x in run_checks(card, load_rules()) if x.rule_id == "R-OP-001")
    assert c.verdict == "不合规"
    assert any("guardian" in e for e in c.evidence)


def test_time_reversed_flagged():
    card = parse_ticket(SAMPLE.read_text(encoding="utf-8"))
    card.fields["end_time"] = FieldValue(value="2026-10-15T07:00")
    c = next(x for x in run_checks(card, load_rules()) if x.rule_id == "R-OP-002")
    assert c.verdict == "不合规"
    assert c.risk == "一般"


def test_unknown_check_type_skipped():
    rules = load_rules()
    rules.append(
        {
            "id": "R-X",
            "name": "未来规则",
            "check_type": "not_yet",
            "applies_to": ["operating"],
            "basis": {"standard": "X", "clause": "y", "status": "待核对"},
        }
    )
    card = parse_ticket(SAMPLE.read_text(encoding="utf-8"))
    run_checks(card, rules)  # 不应抛异常
    assert any("R-X" in w for w in card.warnings)


def test_rule_without_basis_rejected(tmp_path):
    bad = tmp_path / "bad.json"
    rule = {
        "id": "R-BAD",
        "name": "n",
        "check_type": "required_field",
        "applies_to": ["operating"],
        "basis": {"standard": "", "clause": "", "status": "待核对"},
    }
    bad.write_text(
        json.dumps({"rules": [rule]}, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(RuleError):
        load_rules(str(bad))


def test_rules_path_missing_rejected(tmp_path):
    with pytest.raises(RuleError):
        load_rules(str(tmp_path / "no_such.json"))
