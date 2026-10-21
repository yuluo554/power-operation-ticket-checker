import json
import re
import tomllib
from pathlib import Path

import powerticket

ROOT = Path(__file__).resolve().parents[1]


def test_version():
    """版本单源：pyproject.version 必须与 powerticket.__version__ 完全相等。

    2026-10-22 二次迭代：原断言 `assert powerticket.__version__` 恒真（非空字符串即过），
    等于没有守门。改为真比对——抬版本时漏改任一侧即红。
    """
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = pyproject["project"]["version"]
    assert declared, "pyproject.toml 缺 [project].version"
    assert powerticket.__version__ == declared, (
        f"版本不一致：pyproject.toml={declared!r} vs "
        f"powerticket.__version__={powerticket.__version__!r}"
    )


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
