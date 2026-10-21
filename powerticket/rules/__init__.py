"""规则引擎：加载规则 JSON → 票种类目门控 → check_type 分派（schema 见 plan/04 §3）。

M3 起全 7 类 check_type 分派；正式规则库分文件放 data/knowledge/rules/。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models import VERDICT_MANUAL, VERDICT_VIOLATION, Conclusion, TicketCard
from . import checks

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RULES_PATH = _REPO_ROOT / "data" / "knowledge" / "rules"

CHECKS: Dict[str, Any] = {
    "required_field": checks.check_required_field,
    "time_order": checks.check_time_order,
    "process_signature": checks.check_process_signature,
    "ticket_type_match": checks.check_ticket_type_match,
    "measure_coverage": checks.check_measure_coverage,
    "five_prevention": checks.check_five_prevention,
    "consistency": checks.check_consistency,
}

_REQUIRED_KEYS = ("id", "name", "check_type", "applies_to", "basis")


class RuleError(Exception):
    """规则库加载失败（路径不存在 / 必填字段缺失 / 依据无出处）。"""


def load_rules(path: Optional[str] = None) -> List[dict]:
    rules_path = Path(path) if path else DEFAULT_RULES_PATH
    if rules_path.is_dir():
        files = sorted(rules_path.glob("*.json"))
        if not files:
            raise RuleError(f"规则目录为空: {rules_path}")
    elif rules_path.is_file():
        files = [rules_path]
    else:
        raise RuleError(f"规则路径不存在: {rules_path}")

    rules: List[dict] = []
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        for rule in data.get("rules", []):
            missing = [k for k in _REQUIRED_KEYS if not rule.get(k)]
            if missing:
                raise RuleError(f"规则缺少必填字段 {missing}: {f.name}")
            # 结论纪律：无出处的规则不得落库
            if not rule["basis"].get("standard"):
                raise RuleError(f"规则 {rule['id']} 依据无出处（不得落库）: {f.name}")
            rules.append(rule)
    return rules


def run_checks(card: TicketCard, rules: List[dict]) -> List[Conclusion]:
    conclusions: List[Conclusion] = []
    for rule in rules:
        # 类目门控：applies_to 对全部 check_type 生效，防跨票种误查
        if card.ticket_type not in rule.get("applies_to", []):
            continue
        check = CHECKS.get(rule["check_type"])
        if check is None:
            card.warnings.append(f"未知 check_type 已跳过: {rule['id']}({rule['check_type']})")
            continue
        produced = check(rule, card)
        # 依据闸（plan/04:70/100 落地）：basis.status 非「已核对」的规则不得下确定性「不合规」，
        # 一律降级为「待人工确认」；「合规」与既有「待人工确认」不动。
        # 闸门必须在 check() 之后 —— 跳过规则不执行会让 required_field 的缺失检测整块消失。
        if (rule.get("basis") or {}).get("status") != "已核对":
            for c in produced:
                if c.verdict == VERDICT_VIOLATION:
                    c.verdict = VERDICT_MANUAL
        conclusions.extend(produced)
    return conclusions
