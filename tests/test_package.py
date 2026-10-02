import json
import re
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


def test_extras_cover_test_dependencies():
    # M6 干净环境实测：fastapi TestClient 还需要 httpx，extras 未声明时 test_web 被
    # importorskip 整模块静默跳过（203→194），CI 与干净 venv 均查不到；新增测试期依赖
    # 时同步更新本表。
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r"\[project\.optional-dependencies\]\n(.*?)\n\[", text, re.S)
    assert m, "pyproject 缺 [project.optional-dependencies] 段"
    extras = dict(re.findall(r"^(\w+)\s*=\s*\[(.*?)\]", m.group(1), re.S | re.M))
    required = {
        "dev": ["pytest", "httpx"],
        "web": ["fastapi", "uvicorn", "python-multipart"],
        "report": ["python-docx"],
        "llm": ["openai"],
    }
    for extra, pkgs in required.items():
        assert extra in extras, f"缺 extras[{extra}]"
        for pkg in pkgs:
            assert pkg in extras[extra], f"extras[{extra}] 缺 {pkg}"
