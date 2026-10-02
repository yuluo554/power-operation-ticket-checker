"""M4 基准评测守门：parse_f1 / endtoend 门槛与口径；评分函数单元用例。

基准纪律：零 API 依赖可重复；门槛 F1≥0.95、误报 0。
"""
from __future__ import annotations

import json
from pathlib import Path

from powerticket.eval.endtoend import classify_sample, main as endtoend_main, run as endtoend_run
from powerticket.eval.parse_f1 import main as parse_f1_main, run as parse_f1_run, score_parse
from powerticket.models import Evidence, FieldValue, OperationStep, SafetyMeasure, TicketCard
from powerticket.parse import parse_ticket
from powerticket.rules import load_rules

ROOT = Path(__file__).resolve().parents[1]
GEN_DIR = ROOT / "data" / "samples" / "gen"


# ---------------------------------------------------------------------------
# 评分函数单元用例（合成数据，不依赖样例集）
# ---------------------------------------------------------------------------

def _card_with(**fields):
    card = TicketCard(ticket_type="operating")
    for key, value in fields.items():
        card.fields[key] = FieldValue(
            value=value, evidence=Evidence(region="body", quote=f"{key}：{value}")
        )
    return card


def test_score_parse_field_counts():
    # a 正确=TP；b 缺报=FN+FP；c 多报=FP；remarks 不计分
    card = _card_with(a="1", c="3", remarks="备注声明")
    truth = {"fields": {"a": "1", "b": "2"}}
    assert score_parse(truth, card) == (1, 2, 1)


def test_score_parse_value_mismatch_counts_both():
    card = _card_with(a="wrong")
    truth = {"fields": {"a": "right"}}
    assert score_parse(truth, card) == (0, 1, 1)


def test_score_parse_operation_sequence_positional():
    card = TicketCard(ticket_type="operating")
    card.operation_sequence = [
        OperationStep(no=1, action="x"),
        OperationStep(no=2, action="y"),
    ]
    truth = {"fields": {}, "operation_sequence": [{"no": 1, "action": "x"}]}
    # 位 1 命中=TP；位 2 多出=FP
    assert score_parse(truth, card) == (1, 1, 0)


def test_score_parse_safety_measures_and_missing():
    card = TicketCard(ticket_type="work_first")
    card.safety_measures = [SafetyMeasure(no=1, text="m1")]
    truth = {"fields": {}, "safety_measures": ["m1", "m2"]}
    # 位 1 命中=TP；位 2 缺少=FN
    assert score_parse(truth, card) == (1, 0, 1)


def test_score_parse_truth_without_list_blocks():
    # 操作票卡不应带安全措施：真值缺键视为空表，卡内多出即 FP
    card = TicketCard(ticket_type="operating")
    card.safety_measures = [SafetyMeasure(no=1, text="m1")]
    truth = {"fields": {}}
    assert score_parse(truth, card) == (0, 1, 0)


# ---------------------------------------------------------------------------
# 全集基准（35 份样例，门槛锁定）
# ---------------------------------------------------------------------------

def test_parse_f1_perfect_on_committed_set():
    result = parse_f1_run()
    assert result["samples"] == 35
    assert result["items"]["tp"] > 0
    assert result["items"]["fp"] == 0 and result["items"]["fn"] == 0
    assert result["precision"] == 1.0 and result["recall"] == 1.0 and result["f1"] == 1.0
    assert result["gate"]["pass"] is True
    assert set(result["per_ticket_type"]) == {
        "operating", "line_operating", "work_first", "work_second",
        "line_work_first", "line_work_second", "emergency_repair",
    }


def test_endtoend_perfect_on_committed_set():
    result = endtoend_run()
    assert result["samples"] == 35
    assert result["defect_samples"] == 28 and result["normal_samples"] == 7
    assert result["detection"] == {"hit": 28, "total": 28, "rate": 1.0}
    assert result["false_positive_samples"] == 0
    assert result["false_positive_rate"] == 0.0
    assert result["accuracy"] == {"correct": 35, "total": 35, "rate": 1.0}
    assert result["failures"] == []
    assert result["gate"]["pass"] is True


def test_classify_sample_on_real_samples():
    rules = load_rules()
    rule_types = {r["id"]: r["check_type"] for r in rules}

    # 缺陷样例（time-order）：实测集合 == 期望集合 → 命中
    defect_truth = json.loads(
        (GEN_DIR / "gen-operating-004-time-order.truth.json").read_text(encoding="utf-8")
    )
    defect_card = parse_ticket((GEN_DIR / defect_truth["file"]).read_text(encoding="utf-8"))
    verdict = classify_sample(defect_truth, defect_card, rule_types, rules)
    assert verdict["hit"] is True and verdict["miss"] == [] and verdict["extra"] == []

    # 正常样例：任何非 pass 即 extra
    normal_truth = json.loads(
        (GEN_DIR / "gen-operating-001-normal.truth.json").read_text(encoding="utf-8")
    )
    normal_card = parse_ticket((GEN_DIR / normal_truth["file"]).read_text(encoding="utf-8"))
    verdict = classify_sample(normal_truth, normal_card, rule_types, rules)
    assert verdict["hit"] is True and verdict["extra"] == []


def test_eval_mains_exit_zero(capsys):
    assert parse_f1_main([]) == 0
    assert json.loads(capsys.readouterr().out)["gate"]["pass"] is True
    assert endtoend_main([]) == 0
    assert json.loads(capsys.readouterr().out)["gate"]["pass"] is True
