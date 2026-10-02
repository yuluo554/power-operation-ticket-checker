"""规则引擎：加载规则 JSON → 票种类目门控 → check_type 分派（schema 见 plan/04 §3）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models import Conclusion, TicketCard
from . import checks

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RULES_PATH = _REPO_ROOT / "data" / "knowledge" / "rules"

CHECKS: Dict[str, Any] = {
    "required_field": checks.check_required_field,
    "time_order": checks.check_time_order,
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
        conclusions.extend(check(rule, card))
    return conclusions
