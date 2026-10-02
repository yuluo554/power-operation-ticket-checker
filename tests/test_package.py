import json
from pathlib import Path

import powerticket

ROOT = Path(__file__).resolve().parents[1]


def test_version():
    assert powerticket.__version__


RULES_DIR = ROOT / "data" / "knowledge" / "rules"


def test_rules_files_registered():
    # M3 正式规则库：rules-form / rules-time / rules-content 三文件（demo-operating.json 已退役）
    names = {p.name for p in RULES_DIR.glob("*.json")}
    assert {"rules-form.json", "rules-time.json", "rules-content.json"} <= names
    ids = []
    for path in sorted(RULES_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["rules"], path.name
        for rule in data["rules"]:
            assert rule["basis"]["standard"]
            ids.append(rule["id"])
    assert len(ids) == len(set(ids)), "规则 id 跨文件重复"


def test_demo_sample_registered_in_ledger():
    ledger = (ROOT / "data" / "README.md").read_text(encoding="utf-8")
    assert "sample-operating-01.txt" in ledger
