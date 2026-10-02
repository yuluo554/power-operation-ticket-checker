"""parse_f1：字段级 P/R/F1（生成器真值 vs 解析结果，data/samples/gen 35 份样例，M4 基准）。

口径（M4 定稿，与 tests/test_data_generator.py 的真值对账一致）：
- 评测字段集 = truth.fields（remarks 是唯一不入真值的已抽取字段，不参与计分）；
- 标量字段逐键对账：同键同值 = TP；键缺失或值不符 = FN+FP（错值同时计漏报与误报）；
  真值之外的多余预测（如被注入缺失的字段被解析出值）= FP；
- 列表块（operation_sequence / safety_measures）按位对账，真值缺该键视为空表：
  位序/内容一致 = TP，不符 = FP+FN，多出 = FP，缺少 = FN；
- 注入缺失（missing_field/signature_gap）的字段已从真值 fields 移除，解析器留空不入卡
  即正确（不产生 FN），解析出值则计 FP。
零 API 依赖，固定 seed 数据集上可重复。门槛：F1 ≥ 0.95。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ..models import TicketCard
from ..parse import parse_ticket

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SAMPLES_DIR = _REPO_ROOT / "data" / "samples" / "gen"

# 备注栏为虚构声明，不入真值（truth semantics_note；与 test_data_generator 同口径）
EXTRACTED_BUT_UNTRUTHED = frozenset({"remarks"})

F1_GATE = 0.95


def score_parse(truth: Dict[str, Any], card: TicketCard) -> Tuple[int, int, int]:
    """单样例字段级对账，返回 (tp, fp, fn)。"""
    tp = fp = fn = 0

    predicted = {
        key: str(fv.value)
        for key, fv in card.fields.items()
        if key not in EXTRACTED_BUT_UNTRUTHED
    }
    for key, want in truth["fields"].items():
        got = predicted.pop(key, None)
        if got == want:
            tp += 1
        else:
            fn += 1
            fp += 1
    fp += len(predicted)  # 真值之外的多余预测字段

    # 操作序列：真值 [{no, action}] vs 卡内 OperationStep；安全措施：真值 [text]（no=位序）
    want_steps = [(s["no"], s["action"]) for s in truth.get("operation_sequence") or []]
    got_steps = [(s.no, s.action) for s in card.operation_sequence]
    want_measures = [(i + 1, t) for i, t in enumerate(truth.get("safety_measures") or [])]
    got_measures = [(m.no, m.text) for m in card.safety_measures]
    for want_list, got_list in ((want_steps, got_steps), (want_measures, got_measures)):
        for want, got in zip(want_list, got_list):
            if want == got:
                tp += 1
            else:
                fp += 1
                fn += 1
        extra = len(got_list) - len(want_list)
        if extra > 0:
            fp += extra
        else:
            fn += -extra
    return tp, fp, fn


def run(samples_dir: str = None) -> Dict[str, Any]:
    """跑全集，返回聚合指标（微平均：全部样例的 TP/FP/FN 合计后计算）。"""
    samples_dir = Path(samples_dir) if samples_dir else DEFAULT_SAMPLES_DIR
    tp = fp = fn = 0
    per_type: Dict[str, Dict[str, int]] = {}
    samples = 0
    for truth_path in sorted(samples_dir.glob("*.truth.json")):
        truth = json.loads(truth_path.read_text(encoding="utf-8"))
        card = parse_ticket((samples_dir / truth["file"]).read_text(encoding="utf-8"))
        t, f, n = score_parse(truth, card)
        tp += t
        fp += f
        fn += n
        samples += 1
        agg = per_type.setdefault(truth["ticket_type"], {"tp": 0, "fp": 0, "fn": 0})
        agg["tp"] += t
        agg["fp"] += f
        agg["fn"] += n

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "script": "parse_f1",
        "samples_dir": str(samples_dir),
        "samples": samples,
        "items": {"tp": tp, "fp": fp, "fn": fn},
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "gate": {"f1_min": F1_GATE, "pass": f1 >= F1_GATE},
        "per_ticket_type": per_type,
    }


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(prog="powerticket.eval.parse_f1", description="解析字段级 P/R/F1 基准")
    parser.add_argument("--samples", default=None, help="样例目录（默认 data/samples/gen）")
    ns = parser.parse_args(argv)
    result = run(ns.samples)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["gate"]["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
