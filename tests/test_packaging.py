"""打包自足性守门（2026-10-22 v0.2.0）：装成 wheel 后必须真能跑。

本轮发现并修复的缺陷：`data/`（规则库/样例/模板/知识库，2.0 MB / 97 文件）从未入包，
所有模块用 `Path(__file__).parents[2] / "data"` 定位，装成 wheel 后指向
`<venv>/Lib` 下的不存在路径 —— `demo` 直接报「文件不存在」。
而源码态与 editable 安装都正常，所以 217 项测试一路是绿的。

因此这里锁定三件事：

1. `powerticket.paths.data_dir()` 在源码态解析正确，且 `POWERTICKET_DATA_DIR` 能覆盖；
2. 关键数据文件真实存在于解析结果下（规则库 39 条、样例 71 文件、chunks 26 块、模板）；
3. `pyproject.toml` 的 `[tool.setuptools.data-files]` 覆盖全部 7 个数据子目录
   —— 少一个就红（防止以后有人加数据目录忘了登记）。

真正的「装 wheel 后跑命令」由 CI 的 packaging 作业做（要真装到干净 venv，见
`.github/workflows/ci.yml`），本文件只做零依赖的静态 + 解析断言。
"""
from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import powerticket
from powerticket import paths

ROOT = Path(__file__).resolve().parents[1]

#: 必须随包分发的数据子目录（与 pyproject 的 data-files 键一一对应）
REQUIRED_DATA_SUBDIRS = [
    "knowledge/raw",
    "knowledge/rules",
    "knowledge/chunks",
    "samples",
    "samples/gen",
    "ticket_templates",
    "generator",
]


def test_data_dir_resolves_in_source_tree():
    d = paths.data_dir()
    assert d.is_dir(), d
    assert (d / "knowledge" / "rules").is_dir(), d
    # 源码态下应指向仓库根的 data/（不是 site-packages）
    assert d.resolve() == (ROOT / "data").resolve(), d


def test_data_dir_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv(paths.ENV_VAR, str(tmp_path))
    paths.reset_cache()
    try:
        assert paths.data_dir() == tmp_path.resolve()
        assert paths.sub("knowledge", "rules") == tmp_path.resolve() / "knowledge" / "rules"
    finally:
        monkeypatch.delenv(paths.ENV_VAR)
        paths.reset_cache()
    assert paths.data_dir().resolve() == (ROOT / "data").resolve()


def test_key_data_files_present():
    rules = list(paths.sub("knowledge", "rules").glob("*.json"))
    assert len(rules) == 3, rules
    total = sum(
        len(json.loads(p.read_text(encoding="utf-8"))["rules"]) for p in rules
    )
    assert total == 39, total

    samples = sorted(paths.sub("samples", "gen").glob("*.txt"))
    truths = sorted(paths.sub("samples", "gen").glob("*.truth.json"))
    assert len(samples) == 35 and len(truths) == 35, (len(samples), len(truths))

    assert paths.sub("samples", "sample-operating-01.txt").is_file()
    assert paths.sub("knowledge", "chunks", "chunks.json").is_file()
    assert len(list(paths.sub("ticket_templates").glob("*"))) >= 9


def test_pyproject_data_files_covers_every_subdir():
    """data-files 必须覆盖 REQUIRED_DATA_SUBDIRS 全集，少一个即红。"""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    section = pyproject.get("tool", {}).get("setuptools", {}).get("data-files")
    assert section, "pyproject.toml 缺 [tool.setuptools.data-files]"
    # 键形如 "share/powerticket/<subdir>"
    covered = set()
    for key in section:
        prefix = "share/powerticket/"
        assert key.startswith(prefix), f"data-files 键必须落在 {prefix} 下: {key}"
        covered.add(key[len(prefix):])
    missing = [d for d in REQUIRED_DATA_SUBDIRS if d not in covered]
    assert not missing, f"data-files 未覆盖这些数据子目录: {missing}"


def test_no_module_resolves_data_via_parents():
    """回归守卫：不许再有模块自己拼 `parents[N] / "data"`（必须走 paths）。"""
    offenders = []
    for py in (ROOT / "powerticket").rglob("*.py"):
        if py.name == "paths.py":
            continue  # 解析器本体，其 docstring 就在解释这个反例
        text = py.read_text(encoding="utf-8")
        if re.search(r'parents\[\d+\]\s*/\s*"data"', text):
            offenders.append(str(py.relative_to(ROOT)))
    assert not offenders, "这些模块绕过 powerticket.paths 直接拼 data/：" + ", ".join(offenders)


def test_version_gate_still_present():
    """版本单源守门仍生效（防止本轮改动把它弄丢）。"""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == powerticket.__version__
