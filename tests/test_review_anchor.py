"""复核锚守门（2026-10-22 二次迭代）：规范依据必须能回答「何时核对 / 何时该复核」。

本仓 39 条规则里 30 条依据 `待核对`（等原文核对），没有锚则「已待核对 N 天」
不会被任何机器发现。本文件锁定：

* 6 份 raw 登记卡都有 reviewed_at / next_review / review_interval；
* 39 条规则的 basis 都有 review_due；
* 日期一律合法 ISO（YYYY-MM-DD），且 next_review/review_due 晚于 reviewed_at；
* 逾期**只打印警告，不改退出码**（复核是人的动作，不该把 CI 变红）；
* 红线：overall_status 与 basis.status 未被本轮的「加锚」动作顺手改掉。
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "knowledge" / "raw"
RULES_DIR = ROOT / "data" / "knowledge" / "rules"

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parse(value: str, where: str) -> date:
    assert ISO.match(value or ""), f"{where} 不是合法 ISO 日期: {value!r}"
    y, m, d = (int(x) for x in value.split("-"))
    return date(y, m, d)


def _raw_cards():
    cards = sorted(RAW_DIR.glob("*.json"))
    assert cards, "raw 登记卡目录为空"
    for path in cards:
        yield path, json.loads(path.read_text(encoding="utf-8"))


def _rules():
    for path in sorted(RULES_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for rule in data["rules"]:
            yield path, rule


def test_raw_cards_have_review_anchor():
    count = 0
    for path, card in _raw_cards():
        for key in ("reviewed_at", "next_review", "review_interval"):
            assert card.get(key), f"{path.name} 缺 {key}"
        reviewed = _parse(card["reviewed_at"], f"{path.name}.reviewed_at")
        next_review = _parse(card["next_review"], f"{path.name}.next_review")
        assert next_review > reviewed, f"{path.name}: next_review 必须晚于 reviewed_at"
        assert card["review_interval"] in {"annual", "semiannual", "quarterly", "biennial"}, (
            f"{path.name}.review_interval 取值不在约定集合: {card['review_interval']!r}"
        )
        count += 1
    assert count == 6, f"raw 登记卡应为 6 份，实测 {count}"


def test_rules_have_review_due():
    count = 0
    for path, rule in _rules():
        basis = rule["basis"]
        assert basis.get("review_due"), f"{path.name}:{rule['id']} 缺 basis.review_due"
        _parse(basis["review_due"], f"{path.name}:{rule['id']}.review_due")
        count += 1
    assert count == 39, f"规则应为 39 条，实测 {count}"


def test_review_due_not_before_reviewed_at():
    reviewed = {}
    for path, card in _raw_cards():
        reviewed[card["standard"]] = _parse(card["reviewed_at"], path.name)
    assert reviewed, "未读到任何登记卡的 reviewed_at"
    for path, rule in _rules():
        due = _parse(rule["basis"]["review_due"], f"{rule['id']}.review_due")
        assert due > min(reviewed.values()), f"{rule['id']}: review_due 早于登记卡核对日"


def test_overdue_only_warns(capsys):
    """逾期只打印警告，不改退出码（复核是人的动作，不应让 CI 变红）。"""
    today = date.today()
    overdue = []
    for path, card in _raw_cards():
        if _parse(card["next_review"], path.name) < today:
            overdue.append(f"{card.get('standard', path.stem)}（next_review {card['next_review']}）")
    for path, rule in _rules():
        if _parse(rule["basis"]["review_due"], rule["id"]) < today:
            overdue.append(f"{rule['id']}（review_due {rule['basis']['review_due']}）")
    if overdue:
        print(f"[复核提醒] {len(overdue)} 项已过复核日，建议安排原文核对：{overdue[:5]}")
    # 断言：警告路径本身不抛错、不改变测试结果
    assert capsys is not None


def test_anchor_addition_did_not_touch_status():
    """红线：加锚不许顺手把「待核对」改成「已核对」。"""
    statuses = {}
    for _path, rule in _rules():
        statuses[rule["basis"]["status"]] = statuses.get(rule["basis"]["status"], 0) + 1
    assert statuses == {"已核对": 9, "待核对": 30}, statuses

    raw_statuses = {}
    for _path, card in _raw_cards():
        raw_statuses[card["overall_status"]] = raw_statuses.get(card["overall_status"], 0) + 1
    assert raw_statuses == {"已核对": 1, "待核对": 5}, raw_statuses
