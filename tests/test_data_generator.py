"""M1 数据先行守门：模板完整性 / 生成器确定性（位级一致）/ 真值语义 / 互斥矩阵 / operating 回归对账。"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

from powerticket.parse import parse_ticket

ROOT = Path(__file__).resolve().parents[1]
GEN_DIR = ROOT / "data" / "generator"
TPL_DIR = ROOT / "data" / "ticket_templates"
GEN_OUT = ROOT / "data" / "samples" / "gen"

TICKET_TYPES = [
    "operating",
    "line_operating",
    "work_first",
    "work_second",
    "line_work_first",
    "line_work_second",
    "emergency_repair",
]
PLACEHOLDER_RE = re.compile(r"\{\{([a-z_]+)\}\}")


def _load_generator():
    spec = importlib.util.spec_from_file_location("pt_generate", GEN_DIR / "generate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _truths():
    for tp in sorted(GEN_OUT.glob("*.truth.json")):
        yield json.loads(tp.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 模板完整性（占位符 ↔ 注册表一一对应，逐项挂出处）
# ---------------------------------------------------------------------------

def test_templates_complete_and_annotated():
    templates = json.loads((TPL_DIR / "templates.json").read_text(encoding="utf-8"))["templates"]
    assert set(templates) == set(TICKET_TYPES)
    for code, tpl in templates.items():
        text = (TPL_DIR / tpl["file"]).read_text(encoding="utf-8")
        keys = PLACEHOLDER_RE.findall(text)
        declared = [f["key"] for f in tpl["fields"]]
        assert sorted(keys) == sorted(declared), f"{code} 占位符与注册表不一致"
        assert len(keys) == len(set(keys)), f"{code} 占位符重复"
        assert tpl["standard"].strip() and tpl["standard_part"].strip()
        assert tpl["status"] in ("待核对", "已核对")
        for f in tpl["fields"]:
            assert f["source"].strip(), f"{code}/{f['key']} 缺出处"
            assert f["status"] in ("待核对", "已核对")
            assert f["role"] in ("scalar", "list", "ambient")
            assert isinstance(f["required"], bool) and isinstance(f["injectable_missing"], bool)


def test_defect_catalog_alignment():
    catalog = json.loads((GEN_DIR / "defect_catalog.json").read_text(encoding="utf-8"))
    assert set(catalog["check_type_set"]) == {
        "required_field",
        "time_order",
        "process_signature",
        "ticket_type_match",
        "measure_coverage",
        "five_prevention",
        "consistency",
    }
    defect_names = set()
    for spec in catalog["defect_types"]:
        defect_names.add(spec["defect_type"])
        assert spec["desc"].strip()
        assert set(spec["expect"]) <= set(catalog["check_type_set"])
        for tt, targets in spec.get("targets", {}).items():
            assert tt in TICKET_TYPES, f"{spec['defect_type']} 目标票种 {tt} 不在票种清单"
            assert targets, f"{spec['defect_type']}/{tt} 目标列表为空"
    for ex in catalog["mutual_exclusions"]:
        assert len(ex["pair"]) == 2 and set(ex["pair"]) <= defect_names
        assert ex["reason"].strip()
    for cap in catalog["caps"].values():
        assert 0 <= cap["min"] < cap["max"]


# ---------------------------------------------------------------------------
# 生成器确定性（位级一致门：内存产物 == 已提交文件）
# ---------------------------------------------------------------------------

def test_generator_matches_committed_files():
    mod = _load_generator()
    files = mod.build_all(seed=mod.DEFAULT_SEED)
    committed = {p.name: p.read_text(encoding="utf-8") for p in GEN_OUT.iterdir() if p.is_file()}
    assert set(files) == set(committed), "内存产物与已提交文件清单不一致（改模板后需 --force 重生成）"
    for name in sorted(files):
        assert files[name] == committed[name], f"位级不一致: {name}"


def test_generator_cli_bytes_identical_across_runs(tmp_path):
    mod = _load_generator()
    out1, out2 = tmp_path / "a", tmp_path / "b"
    assert mod.main(["--out", str(out1)]) == 0
    assert mod.main(["--out", str(out2)]) == 0
    names1 = sorted(p.name for p in out1.iterdir())
    names2 = sorted(p.name for p in out2.iterdir())
    assert names1 == names2
    for n in names1:
        assert (out1 / n).read_bytes() == (out2 / n).read_bytes(), n


def test_generator_refuses_nonempty_without_force(tmp_path):
    mod = _load_generator()
    out = tmp_path / "out"
    out.mkdir()
    (out / "stale.txt").write_text("x", encoding="utf-8")
    assert mod.main(["--out", str(out)]) == 2  # 非空目录拒绝
    assert (out / "stale.txt").exists()
    assert mod.main(["--out", str(out), "--force"]) == 0  # --force 先清旧行
    assert not (out / "stale.txt").exists()
    assert (out / "manifest.json").exists()


def test_manifest_matches_files():
    manifest = json.loads((GEN_OUT / "manifest.json").read_text(encoding="utf-8"))
    names = {p.name for p in GEN_OUT.iterdir() if p.is_file()}
    assert manifest["seed"] == 20261002
    assert manifest["counts"]["total"] == 35 == len(manifest["files"])
    assert manifest["counts"]["normal"] == 7 and manifest["counts"]["defect"] == 28
    assert manifest["source"].startswith("程序化自制") and "seed=20261002" in manifest["source"]
    assert manifest["license"].strip()
    for entry in manifest["files"]:
        assert entry["file"] in names and entry["truth"] in names, entry["file"]
        assert entry["kind"] in ("normal", "defect")


# ---------------------------------------------------------------------------
# 真值语义（expect/also_expect/互斥矩阵）
# ---------------------------------------------------------------------------

def test_truth_semantics():
    mod = _load_generator()
    catalog = mod.load_catalog()
    check_types = set(catalog["check_type_set"])
    truths = list(_truths())
    assert len(truths) == 35
    normal = defect = 0
    for tr in truths:
        assert tr["schema"] == mod.TRUTH_SCHEMA
        expect, also = set(tr["expect"]), set(tr["also_expect"])
        assert expect <= check_types and also <= check_types
        assert not (expect & also), tr["file"]
        if tr["kind"] == "normal":
            normal += 1
            assert tr["defects"] == [] and not expect and not also
        else:
            defect += 1
            assert expect, f"{tr['file']} 缺陷样例 expect 为空"
        # also_expect 只允许 missing_field 注入时间字段这条已声明推导
        if also:
            dts = {d["defect_type"] for d in tr["defects"]}
            targets = {d.get("target") for d in tr["defects"]}
            assert "missing_field" in dts and targets & mod.TIME_FIELDS, tr["file"]
            assert also == {"time_order"}, tr["file"]
    assert (normal, defect) == (7, 28)


def test_truth_parse_fields_consistent_shape():
    scalar_keys = {
        "operating": {"ticket_no", "task", "start_time", "end_time", "dispatcher", "guardian", "operator"},
        "line_operating": {"ticket_no", "task", "start_time", "end_time", "dispatcher", "guardian", "operator"},
        "emergency_repair": {"ticket_no", "work_unit", "task", "start_time", "end_time", "work_head", "crew", "permitor"},
    }

    def blanked(tr):
        # missing_field 与 signature_gap 都会把目标字段留空并从真值 fields 移除
        return {d["target"] for d in tr["defects"] if d["defect_type"] in ("missing_field", "signature_gap")}

    for tr in _truths():
        tt = tr["ticket_type"]
        if tt in scalar_keys:
            assert set(tr["fields"]) == scalar_keys[tt] - blanked(tr), tr["file"]
        else:
            base = {"ticket_no", "work_unit", "work_head", "crew", "location", "task", "plan_start", "plan_end", "issuer", "permit_start", "permitor", "end_time"}
            assert set(tr["fields"]) == base - blanked(tr), tr["file"]
        for v in tr["fields"].values():
            assert str(v).strip(), f"{tr['file']} 真值含空值字段"
        if "operation_sequence" in tr:
            assert tr["operation_sequence"], tr["file"]
        if "safety_measures" in tr:
            assert tr["safety_measures"], tr["file"]


def test_no_mutual_exclusion_violations_in_committed():
    mod = _load_generator()
    catalog = mod.load_catalog()
    for tp in sorted(GEN_OUT.glob("*.truth.json")):
        tr = json.loads(tp.read_text(encoding="utf-8"))
        dts = [d["defect_type"] for d in tr["defects"]]
        for ex in catalog["mutual_exclusions"]:
            a, b = ex["pair"]
            if a not in dts or b not in dts:
                continue
            if {a, b} == {"missing_field", "time_order"}:
                tg = {d["target"] for d in tr["defects"] if d["defect_type"] == "missing_field"}
                assert not tg & mod.TIME_FIELDS, f"{tp.name} 违反互斥矩阵: {ex['reason']}"
            elif {a, b} == {"missing_field", "permit_time_out_of_range"}:
                tg = {d["target"] for d in tr["defects"] if d["defect_type"] == "missing_field"}
                assert not tg & {"plan_start", "plan_end"}, f"{tp.name} 违反互斥矩阵: {ex['reason']}"
            else:
                pytest.fail(f"{tp.name} 违反互斥矩阵: {a}×{b}")


# ---------------------------------------------------------------------------
# 全 35 份样例 × 7 票种解析器/规则引擎 回归对账（M2：operating 对账推广到全集）
# ---------------------------------------------------------------------------

# 备注栏为虚构声明，不入真值（truth semantics_note），但属于注册字段、解析器照常抽取
EXTRACTED_BUT_UNTRUTHED = {"remarks"}
# 注入缺失=字段留空并从真值 fields 移除的两类缺陷
BLANKING_DEFECTS = ("missing_field", "signature_gap")
# 当前规则库 check_type 覆盖面（M3 扩展后由 M4 基准接管全集对账）
COVERED_CHECK_TYPES = {"required_field", "time_order"}


def _truth_payloads():
    for p in sorted(GEN_OUT.glob("*.truth.json")):
        yield p, json.loads(p.read_text(encoding="utf-8"))


def _blanked(tr):
    return {d["target"] for d in tr["defects"] if d["defect_type"] in BLANKING_DEFECTS}


def _covered_expected(tr):
    """当前已实现规则语义能推出的期望子集：time_order 期望仅在倒挂注入或缺时间字段时算已覆盖
    （permit_time_out_of_range 的区间校核规则属 M3 扩展）。"""
    expected = set(tr["expect"]) | set(tr["also_expect"])
    covered = set(expected & COVERED_CHECK_TYPES)
    if "time_order" in covered:
        dts = {d["defect_type"] for d in tr["defects"]}
        if not dts & {"time_order", "missing_field"}:
            covered.discard("time_order")
    return covered


TRUTHS = list(_truth_payloads())
NORMAL_TRUTHS = [(p, tr) for p, tr in TRUTHS if tr["kind"] == "normal"]
COVERED_EXPECTATION_TRUTHS = [(p, tr) for p, tr in TRUTHS if _covered_expected(tr)]


@pytest.mark.parametrize("truth_path,payload", TRUTHS, ids=[p.stem for p, _ in TRUTHS])
def test_generated_sample_parse_matches_truth(truth_path, payload):
    tr = payload
    card = parse_ticket((GEN_OUT / tr["file"]).read_text(encoding="utf-8"))
    assert card.ticket_type == tr["ticket_type"], tr["file"]
    # 注入缺失字段：不入卡且必留痕（warnings）
    for target in sorted(_blanked(tr)):
        assert target not in card.fields, (tr["file"], target)
        assert any(target in w for w in card.warnings), (tr["file"], target)
    # truth.fields vs card.fields 逐项对账（值+证据）；remarks 是唯一不入真值的已抽取字段
    assert set(card.fields) - EXTRACTED_BUT_UNTRUTHED == set(tr["fields"]), tr["file"]
    for key, want in tr["fields"].items():
        got = card.fields[key]
        assert str(got.value) == want, (tr["file"], key)
        assert got.evidence is not None and got.evidence.quote, (tr["file"], key)
    # 列表块对账（操作票对序列、工作票/抢修单对安全措施，互不越界）
    if "operation_sequence" in tr:
        assert [s.no for s in card.operation_sequence] == [
            s["no"] for s in tr["operation_sequence"]
        ], tr["file"]
        assert [s.action for s in card.operation_sequence] == [
            s["action"] for s in tr["operation_sequence"]
        ], tr["file"]
    else:
        assert not card.operation_sequence, tr["file"]
    if "safety_measures" in tr:
        assert [m.text for m in card.safety_measures] == tr["safety_measures"], tr["file"]
        assert [m.no for m in card.safety_measures] == list(
            range(1, len(tr["safety_measures"]) + 1)
        ), tr["file"]
    else:
        assert not card.safety_measures, tr["file"]


@pytest.mark.parametrize(
    "truth_path,payload", NORMAL_TRUTHS, ids=[p.stem for p, _ in NORMAL_TRUTHS]
)
def test_generated_normal_sample_no_false_alarm(truth_path, payload):
    from powerticket.rules import load_rules, run_checks

    tr = payload
    card = parse_ticket((GEN_OUT / tr["file"]).read_text(encoding="utf-8"))
    conclusions = run_checks(card, load_rules())
    non_pass = [(c.rule_id, c.verdict) for c in conclusions if c.verdict != "合规"]
    assert not non_pass, (tr["file"], non_pass)
    assert not card.warnings, tr["file"]


@pytest.mark.parametrize(
    "truth_path,payload",
    COVERED_EXPECTATION_TRUTHS,
    ids=[p.stem for p, _ in COVERED_EXPECTATION_TRUTHS],
)
def test_generated_sample_covered_expectations_fire(truth_path, payload):
    """已实现规则语义覆盖的期望（required_field/time_order）必须在缺陷样例上非 pass。"""
    from powerticket.rules import load_rules, run_checks

    tr = payload
    card = parse_ticket((GEN_OUT / tr["file"]).read_text(encoding="utf-8"))
    rules = load_rules()
    rule_types = {r["id"]: r["check_type"] for r in rules}
    non_pass = {rule_types[c.rule_id] for c in run_checks(card, rules) if c.verdict != "合规"}
    assert _covered_expected(tr) <= non_pass, (tr["file"], non_pass)
