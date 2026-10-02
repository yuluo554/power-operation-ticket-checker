import json
from pathlib import Path

import powerticket

ROOT = Path(__file__).resolve().parents[1]


def test_version():
    assert powerticket.__version__


def test_demo_rules_file_registered():
    rules_file = ROOT / "data" / "knowledge" / "rules" / "demo-operating.json"
    data = json.loads(rules_file.read_text(encoding="utf-8"))
    assert len(data["rules"]) >= 2


def test_demo_sample_registered_in_ledger():
    ledger = (ROOT / "data" / "README.md").read_text(encoding="utf-8")
    assert "sample-operating-01.txt" in ledger
