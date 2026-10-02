import json
from pathlib import Path

import pytest

from powerticket.models import FieldValue, SafetyMeasure, TicketCard
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

# M3 全量后各票种应有的 check_type 覆盖（库级断言见 test_library_covers_all_check_types）
TYPE_EXPECTED_CHECKS = {
    "operating": {"required_field", "time_order", "five_prevention", "consistency"},
    "line_operating": {"required_field", "time_order", "five_prevention", "consistency"},
    "work_first": {"required_field", "time_order", "process_signature", "measure_coverage"},
    "work_second": {"required_field", "time_order", "process_signature", "ticket_type_match"},
    "line_work_first": {"required_field", "time_order", "process_signature", "measure_coverage"},
    "line_work_second": {"required_field", "time_order", "process_signature", "ticket_type_match"},
    "emergency_repair": {"required_field", "time_order", "process_signature"},
}


def test_load_rules():
    rules = load_rules()
    assert len(rules) >= 39
    ids = [r["id"] for r in rules]
    assert len(ids) == len(set(ids)), "规则 id 重复"
    # 结论纪律：每条规则必须挂出处
    for r in rules:
        assert r["basis"]["standard"]


def test_library_covers_all_check_types_and_ticket_types():
    rules = load_rules()
    check_types = {r["check_type"] for r in rules}
    assert check_types == {
        "required_field",
        "time_order",
        "process_signature",
        "ticket_type_match",
        "measure_coverage",
        "five_prevention",
        "consistency",
    }
    for tp in TICKET_TYPES:
        types = {r["check_type"] for r in rules if tp in r["applies_to"]}
        assert TYPE_EXPECTED_CHECKS[tp] <= types, tp


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
    assert verdicts == {
        "R-OP-001": "合规",
        "R-OP-002": "合规",
        "R-OP-003": "合规",
        "R-OP-004": "合规",
    }


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


# ---------------------------------------------------------------------------
# M3 新增 check_type 行为测试（构造最小参数卡，逐类验证三态判定）
# ---------------------------------------------------------------------------

def _work_card(ticket_type: str = "work_first") -> TicketCard:
    card = TicketCard(ticket_type=ticket_type)
    card.fields = {
        "ticket_no": FieldValue(value="GZ1-2026-0001"),
        "plan_start": FieldValue(value="2026-10-15T08:00"),
        "plan_end": FieldValue(value="2026-10-15T17:00"),
        "permit_start": FieldValue(value="2026-10-15T08:10"),
        "end_time": FieldValue(value="2026-10-15T16:50"),
        "issuer": FieldValue(value="张测试"),
        "permitor": FieldValue(value="王模拟"),
    }
    card.safety_measures = [
        SafetyMeasure(no=1, text="断开110kV东湖线111断路器"),
        SafetyMeasure(no=2, text="在110kV东湖线111断路器两侧验电确无电压"),
        SafetyMeasure(no=3, text="在110kV东湖线111断路器两侧各装设接地线一组"),
        SafetyMeasure(no=4, text="悬挂“禁止合闸，有人工作！”标示牌"),
    ]
    return card


def _verdict_of(rule_id: str, card: TicketCard, rules=None) -> object:
    rules = rules if rules is not None else load_rules()
    return next(c for c in run_checks(card, rules) if c.rule_id == rule_id)


def test_permit_time_out_of_range_flagged():
    card = _work_card()
    card.fields["permit_start"] = FieldValue(value="2026-10-15T07:40")
    c = _verdict_of("R-W1-004", card)
    assert c.verdict == "不合规"
    rules = load_rules()
    rule_type = {r["id"]: r["check_type"] for r in rules}["R-W1-004"]
    assert rule_type == "time_order"
    assert "07:40" in "".join(c.evidence)


def test_permit_time_after_plan_end_flagged():
    card = _work_card()
    card.fields["permit_start"] = FieldValue(value="2026-10-15T17:30")
    c = _verdict_of("R-W1-004", card)
    assert c.verdict == "不合规"


def test_permit_time_inside_window_passes():
    c = _verdict_of("R-W1-004", _work_card())
    assert c.verdict == "合规"


def test_permit_window_missing_field_manual():
    card = _work_card()
    del card.fields["plan_end"]
    c = _verdict_of("R-W1-004", card)
    assert c.verdict == "待人工确认"


def test_end_time_over_plan_manual_with_delay_hint():
    card = _work_card()
    card.fields["end_time"] = FieldValue(value="2026-10-15T18:30")
    c = _verdict_of("R-W1-006", card)
    assert c.verdict == "待人工确认"
    assert any("延期" in e for e in c.evidence)


def test_end_time_earlier_than_permit_flagged():
    card = _work_card()
    card.fields["end_time"] = FieldValue(value="2026-10-15T08:05")
    c = _verdict_of("R-W1-005", card)
    assert c.verdict == "不合规"


def test_signature_gap_flagged():
    card = _work_card()
    del card.fields["permitor"]
    c = _verdict_of("R-W1-003", card)
    assert c.verdict == "不合规"
    assert any("permitor" in e for e in c.evidence)


def test_signature_chain_complete_passes():
    c = _verdict_of("R-W1-003", _work_card())
    assert c.verdict == "合规"


def test_measure_missing_flagged_with_element_names():
    card = _work_card()
    card.safety_measures = [m for m in card.safety_measures if "验电" not in m.text]
    c = _verdict_of("R-W1-007", card)
    assert c.verdict == "不合规"
    assert any("验电" in e for e in c.evidence)


def test_measure_four_elements_passes():
    c = _verdict_of("R-W1-007", _work_card())
    assert c.verdict == "合规"


def test_no_measures_flagged():
    card = _work_card()
    card.safety_measures = []
    c = _verdict_of("R-W1-007", card)
    assert c.verdict == "不合规"


def test_ticket_type_mismatch_flagged():
    card = TicketCard(ticket_type="work_second")
    card.fields = {"task": FieldValue(value="处理220kV西江线221断路器机构缺陷（需将221断路器由运行位置转检修并停电）")}
    c = _verdict_of("R-W2-007", card)
    assert c.verdict == "不合规"
    assert any("停电" in e for e in c.evidence)


def test_ticket_type_match_exempt_task_passes():
    card = TicketCard(ticket_type="work_second")
    card.fields = {"task": FieldValue(value="对221断路器机构进行例行检查（不需停电，断路器在试验位置进行）")}
    c = _verdict_of("R-W2-007", card)
    assert c.verdict == "合规"


def test_ticket_type_match_skips_when_task_missing():
    # 任务缺失归 required_field 语义，本类跳过不产出结论（防归因双计）
    card = TicketCard(ticket_type="line_work_second")
    rules = load_rules()
    conclusions = [c for c in run_checks(card, rules) if c.rule_id == "R-LW2-007"]
    assert conclusions == []


def test_five_prevention_load_disconnector_flagged():
    card = TicketCard(ticket_type="operating")
    card.operation_sequence = [
        type("S", (), {"no": 1, "action": "检查220kV西江线221断路器确在合闸位置"}),
        type("S", (), {"no": 2, "action": "拉开220kV西江线221-1隔离开关"}),
    ]
    c = _verdict_of("R-OP-003", card)
    assert c.verdict == "不合规"
    assert any("带负荷" in e for e in c.evidence)


def test_five_prevention_ground_close_flagged():
    card = TicketCard(ticket_type="operating")
    card.operation_sequence = [
        type("S", (), {"no": 1, "action": "在110kV东湖线111断路器两侧装设接地线一组"}),
        type("S", (), {"no": 2, "action": "合上110kV东湖线111断路器"}),
    ]
    c = _verdict_of("R-OP-003", card)
    assert c.verdict == "不合规"
    assert any("带接地线" in e for e in c.evidence)


def test_five_prevention_grounding_needs_test_flagged():
    card = TicketCard(ticket_type="operating")
    card.operation_sequence = [
        type("S", (), {"no": 1, "action": "在110kV东湖线111断路器两侧装设接地线一组"}),
    ]
    c = _verdict_of("R-OP-003", card)
    assert c.verdict == "不合规"
    assert any("验电" in e for e in c.evidence)


def test_five_prevention_normal_sequence_passes():
    card = parse_ticket(SAMPLE.read_text(encoding="utf-8"))
    c = _verdict_of("R-OP-003", card)
    assert c.verdict == "合规"


def test_five_prevention_empty_sequence_manual():
    card = TicketCard(ticket_type="operating")
    c = _verdict_of("R-OP-003", card)
    assert c.verdict == "待人工确认"


def test_consistency_kv_mismatch_flagged():
    card = parse_ticket(SAMPLE.read_text(encoding="utf-8"))
    card.operation_sequence[2].action = "检查35kV东湖线111断路器确在断开位置"
    c = _verdict_of("R-OP-004", card)
    assert c.verdict == "不合规"
    assert any("35" in e and "110" in e for e in c.evidence)


def test_consistency_consistent_markings_pass():
    c = _verdict_of("R-OP-004", parse_ticket(SAMPLE.read_text(encoding="utf-8")))
    assert c.verdict == "合规"
