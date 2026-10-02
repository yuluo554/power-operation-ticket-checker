"""endtoend：植入缺陷检出率 / 误报率 / 判定准确率（data/samples/gen 35 份样例，M4 基准）。

口径（M3 全集精确对账，M4 定稿为基准口径，与 tests/test_data_generator.py 一致）：
- 期望结论集 = expect ∪ also_expect（check_type 粒度）；
- 实测结论集 = 规则引擎全部非 pass（≠合规）结论的 check_type 集合；
- 命中 = 实测集合与期望集合精确相等（多出=误报/归因双计，缺少=漏检）；
- 误报：正常样例任何非 pass 结论，或缺陷样例多出的 check_type；
- 检出率 = 精确命中的缺陷样例 / 缺陷样例数；
- 误报率 = 存在误报的样例 / 样例总数（门槛 0）；
- 判定准确率 = 判定完全正确的样例（缺陷精确命中 + 正常零非 pass）/ 样例总数。
零 API 依赖，可重复。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from ..parse import parse_ticket
from ..rules import load_rules, run_checks

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SAMPLES_DIR = _REPO_ROOT / "data" / "samples" / "gen"

FP_GATE = 0  # 误报样例数门槛：0


def classify_sample(
    truth: Dict[str, Any], card, rule_types: Dict[str, str], rules: List[dict]
) -> Dict[str, Any]:
    """单样例判定：返回 {hit, miss, extra}（check_type 粒度，miss/extra 有序便于定位）。"""
    conclusions = run_checks(card, rules)
    non_pass = {rule_types[c.rule_id] for c in conclusions if c.verdict != "合规"}
    expected = set(truth["expect"]) | set(truth["also_expect"])
    if truth["kind"] == "normal":
        # 正常样例：任何非 pass 结论即误报
        extra = sorted(non_pass)
        return {"hit": not extra, "miss": [], "extra": extra}
    miss = sorted(expected - non_pass)
    extra = sorted(non_pass - expected)
    return {"hit": not miss and not extra, "miss": miss, "extra": extra}


def run(samples_dir: str = None, rules_path: str = None) -> Dict[str, Any]:
    """跑全集，返回检出率/误报率/判定准确率与未命中明细。"""
    samples_dir = Path(samples_dir) if samples_dir else DEFAULT_SAMPLES_DIR
    rules = load_rules(rules_path)
    rule_types = {r["id"]: r["check_type"] for r in rules}

    samples = defect = normal = 0
    hits = defect_hits = 0
    fp_samples = 0
    failures: List[Dict[str, Any]] = []
    for truth_path in sorted(samples_dir.glob("*.truth.json")):
        truth = json.loads(truth_path.read_text(encoding="utf-8"))
        card = parse_ticket((samples_dir / truth["file"]).read_text(encoding="utf-8"))
        verdict = classify_sample(truth, card, rule_types, rules)
        samples += 1
        if truth["kind"] == "normal":
            normal += 1
        else:
            defect += 1
        if verdict["hit"]:
            hits += 1
            if truth["kind"] == "defect":
                defect_hits += 1
        if verdict["extra"]:
            fp_samples += 1
            failures.append(
                {
                    "file": truth["file"],
                    "kind": truth["kind"],
                    "miss": verdict["miss"],
                    "extra": verdict["extra"],
                }
            )
        elif verdict["miss"]:
            failures.append(
                {"file": truth["file"], "kind": truth["kind"], "miss": verdict["miss"], "extra": []}
            )

    return {
        "script": "endtoend",
        "samples_dir": str(samples_dir),
        "samples": samples,
        "defect_samples": defect,
        "normal_samples": normal,
        "detection": {
            "hit": defect_hits,
            "total": defect,
            "rate": round(defect_hits / defect, 4) if defect else 0.0,
        },
        "false_positive_samples": fp_samples,
        "false_positive_rate": round(fp_samples / samples, 4) if samples else 0.0,
        "accuracy": {
            "correct": hits,
            "total": samples,
            "rate": round(hits / samples, 4) if samples else 0.0,
        },
        "gate": {"false_positives_max": FP_GATE, "pass": fp_samples <= FP_GATE},
        "failures": failures,
    }


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="powerticket.eval.endtoend", description="端到端检出率/误报率/判定准确率基准"
    )
    parser.add_argument("--samples", default=None, help="样例目录（默认 data/samples/gen）")
    parser.add_argument("--rules", default=None, help="规则路径（默认 data/knowledge/rules）")
    ns = parser.parse_args(argv)
    result = run(ns.samples, ns.rules)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["gate"]["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
