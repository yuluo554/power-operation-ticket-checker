"""两票样例生成器（M1）：固定 seed、正常/缺陷注入、真值 JSON、--force 位级一致。

用法：
    py -X utf8 data/generator/generate.py                 # 默认输出 data/samples/gen/
    py -X utf8 data/generator/generate.py --force         # 先清空输出目录再重生成（先清旧行）
    py -X utf8 data/generator/generate.py --dry-run       # 只打印生成计划，不写文件

真值语义（既定口径，见 plan/05 §2 与本目录 README）：
- expect：注入项的主期望结论，check_type 粒度（对齐 defect_catalog.json）；
- also_expect：同一注入由本仓已声明规则语义强制推出的其余非 pass 结论
  （当前唯一来源：missing_field 注入时间字段 → time_order 因字段缺失判待人工确认）；
- 评测（M4）按"文档全部非 pass 集合"对账：expected = set(expect) | set(also_expect)；
- fields（ISO 时间）/operation_sequence/safety_measures 为解析真值（M2/M4 字段级 F1 对账），
  被注入缺失的字段不出现在 fields；时间倒挂时真值照实登记票面所见（交换后）的值。

多值封顶与互斥注入矩阵见 defect_catalog.json；样例内容全部虚构（设备/人名/单位非真实）。
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

GENERATOR_DIR = Path(__file__).resolve().parent
REPO_ROOT = GENERATOR_DIR.parents[1]
TEMPLATE_DIR = REPO_ROOT / "data" / "ticket_templates"
DEFAULT_OUT = REPO_ROOT / "data" / "samples" / "gen"

DEFAULT_SEED = 20261002
GENERATOR_ID = "data/generator/generate.py"
TRUTH_SCHEMA = "powerticket-truth/0.1"
MANIFEST_SCHEMA = "powerticket-gen-manifest/0.1"

PLACEHOLDER_RE = re.compile(r"\{\{([a-z_]+)\}\}")
# missing_field 注入这些时间字段时，隐含 time_order 非 pass（M0 已实现语义）
TIME_FIELDS = {"start_time", "end_time", "plan_start", "plan_end"}


class GeneratorError(Exception):
    """生成器配置或目录校验失败。"""


# ---------------------------------------------------------------------------
# 虚构内容池（设备/人名/单位均非真实）
# ---------------------------------------------------------------------------

LINES = [
    {"cn": "东湖线", "kv": 110, "breaker": "111", "dis": "111-1", "pole_a": "31", "pole_b": "33", "pole_dis": "003"},
    {"cn": "南岭线", "kv": 35, "breaker": "312", "dis": "312-1", "pole_a": "15", "pole_b": "17", "pole_dis": "015"},
    {"cn": "西江线", "kv": 220, "breaker": "221", "dis": "221-1", "pole_a": "7", "pole_b": "9", "pole_dis": "007"},
]
STATIONS = ["东湖变电站", "南岭变电站", "西江变电站"]
NAMES = ["张测试", "李演示", "王模拟", "赵演练", "钱示例", "孙占位", "周样例"]
UNITS = ["变电检修一班", "输电运检二班", "配电运检三班"]
DATE_BASE = date(2026, 10, 12)
WRONG_KV = {"110": "35", "35": "10", "220": "110"}
REMARK = "本票据为程序生成的虚构演示数据（generator seed={seed}），设备名与人名均非真实。"


def cn_time(d: date, hm: str) -> str:
    """票面打印格式：2026年10月15日 08:30"""
    return f"{d.year}年{d.month:02d}月{d.day:02d}日 {hm}"


def iso_time(d: date, hm: str) -> str:
    """真值/参数卡格式（既定口径）：2026-10-15T08:30"""
    return f"{d.isoformat()}T{hm}"


# ---------------------------------------------------------------------------
# 配置加载与校验（模板注册表 + 缺陷目录）
# ---------------------------------------------------------------------------

def load_templates() -> Dict[str, Any]:
    data = json.loads((TEMPLATE_DIR / "templates.json").read_text(encoding="utf-8"))
    return data["templates"]


def load_catalog() -> Dict[str, Any]:
    data = json.loads((GENERATOR_DIR / "defect_catalog.json").read_text(encoding="utf-8"))
    check_types = set(data["check_type_set"])
    for spec in data["defect_types"]:
        bad = [c for c in spec["expect"] if c not in check_types]
        if bad:
            raise GeneratorError(f"缺陷 {spec['defect_type']} 期望 check_type 不在对齐清单: {bad}")
    return data


def _targets_for(catalog: Dict[str, Any], defect_type: str, ticket_type: str) -> List[str]:
    for spec in catalog["defect_types"]:
        if spec["defect_type"] == defect_type:
            return spec.get("targets", {}).get(ticket_type, [])
    raise GeneratorError(f"未知缺陷类型: {defect_type}")


def _validate_plans(plans: List[Tuple[str, str, List[Tuple[str, Optional[str]]]]], catalog: Dict[str, Any]) -> None:
    """计划先验校验：目标合法性 + 互斥注入矩阵 + 双缺陷封顶。"""
    exclusions = catalog["mutual_exclusions"]
    cap = catalog["caps"]["defects_per_sample"]
    for ticket_type, slug, defects in plans:
        if len(defects) > cap["max"]:
            raise GeneratorError(f"样例 {slug} 缺陷数 {len(defects)} 超过封顶 {cap['max']}")
        for dt, target in defects:
            allowed = _targets_for(catalog, dt, ticket_type)
            if not allowed:
                raise GeneratorError(f"缺陷 {dt} 不适用于票种 {ticket_type}（样例 {slug}）")
            if target is not None and target not in allowed:
                raise GeneratorError(f"缺陷 {dt} 目标 {target} 不在 {ticket_type} 允许列表 {allowed}（样例 {slug}）")
        for ex in exclusions:
            a, b = ex["pair"]
            present = {dt for dt, _ in defects}
            if a not in present or b not in present:
                continue
            if a == "missing_field" or b == "missing_field":
                other = b if a == "missing_field" else a
                scope = ex.get("scope", "")
                if "plan_start" in scope or "plan_end" in scope:
                    m_targets = {t for dt, t in defects if dt == "missing_field"}
                    if not m_targets & {"plan_start", "plan_end"}:
                        continue
                elif other == "time_order":
                    m_targets = {t for dt, t in defects if dt == "missing_field"}
                    if not m_targets & TIME_FIELDS:
                        continue
            raise GeneratorError(
                f"样例 {slug} 违反互斥注入矩阵：{a} × {b}（{ex['reason']}）"
            )


def _expect_for(defects: List[Tuple[str, Optional[str]]], catalog: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """真值语义：expect=主期望（check_type 粒度）；also_expect=已声明语义强制推出的隐含结论。"""
    spec_map = {s["defect_type"]: s for s in catalog["defect_types"]}
    expect: List[str] = []
    also: List[str] = []
    for dt, target in defects:
        for ct in spec_map[dt]["expect"]:
            if ct not in expect:
                expect.append(ct)
        if dt == "missing_field" and target in TIME_FIELDS and "time_order" not in expect:
            if "time_order" not in also:
                also.append("time_order")
    return expect, [c for c in also if c not in expect]


# ---------------------------------------------------------------------------
# 生成计划（显式清单：35 份 = 7 正常 + 28 缺陷/组合）
# ---------------------------------------------------------------------------

def build_plans() -> List[Tuple[str, str, List[Tuple[str, Optional[str]]]]]:
    def mf(target: str) -> Tuple[str, Optional[str]]:
        return ("missing_field", target)

    return [
        ("operating", "normal", []),
        ("operating", "missing-start-time", [mf("start_time")]),
        ("operating", "missing-task", [mf("task")]),
        ("operating", "time-order", [("time_order", None)]),
        ("operating", "five-prevention", [("five_prevention_violation", None)]),
        ("operating", "name-mismatch", [("double_name_mismatch", None)]),
        ("operating", "combo-missing-guardian-name-mismatch", [mf("guardian"), ("double_name_mismatch", None)]),
        ("line_operating", "normal", []),
        ("line_operating", "missing-end-time", [mf("end_time")]),
        ("line_operating", "time-order", [("time_order", None)]),
        ("line_operating", "five-prevention", [("five_prevention_violation", None)]),
        ("line_operating", "combo-missing-task-five-prevention", [mf("task"), ("five_prevention_violation", None)]),
        ("work_first", "normal", []),
        ("work_first", "missing-task", [mf("task")]),
        ("work_first", "missing-plan-end", [mf("plan_end")]),
        ("work_first", "permit-out-of-range", [("permit_time_out_of_range", None)]),
        ("work_first", "measure-missing", [("measure_missing", None)]),
        ("work_first", "signature-gap-permitor", [("signature_gap", "permitor")]),
        ("work_first", "combo-measure-missing-signature-gap", [("measure_missing", None), ("signature_gap", "permitor")]),
        ("work_second", "normal", []),
        ("work_second", "missing-crew", [mf("crew")]),
        ("work_second", "signature-gap-issuer", [("signature_gap", "issuer")]),
        ("work_second", "type-mismatch", [("ticket_type_mismatch", None)]),
        ("line_work_first", "normal", []),
        ("line_work_first", "missing-location", [mf("location")]),
        ("line_work_first", "permit-out-of-range", [("permit_time_out_of_range", None)]),
        ("line_work_first", "measure-missing", [("measure_missing", None)]),
        ("line_work_first", "signature-gap-permitor", [("signature_gap", "permitor")]),
        ("line_work_second", "normal", []),
        ("line_work_second", "missing-task", [mf("task")]),
        ("line_work_second", "type-mismatch", [("ticket_type_mismatch", None)]),
        ("emergency_repair", "normal", []),
        ("emergency_repair", "missing-crew", [mf("crew")]),
        ("emergency_repair", "time-order", [("time_order", None)]),
        ("emergency_repair", "signature-gap-permitor", [("signature_gap", "permitor")]),
    ]


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

def render(template_text: str, values: Dict[str, str]) -> str:
    def repl(m: "re.Match") -> str:  # type: ignore[name-defined]
        v = values.get(m.group(1))
        return "" if v is None else str(v)

    out = PLACEHOLDER_RE.sub(repl, template_text)
    if "{{" in out:
        raise GeneratorError("渲染后仍残留占位符，检查模板与 values 键一致性")
    lines = [ln.rstrip() for ln in out.splitlines()]
    collapsed: List[str] = []
    for ln in lines:
        if ln == "" and (not collapsed or collapsed[-1] == ""):
            continue
        collapsed.append(ln)
    text = "\n".join(collapsed)
    if not text.endswith("\n"):
        text += "\n"
    return text


def _numbered(items: List[str]) -> str:
    return "\n".join(f"{i}  {item}" for i, item in enumerate(items, 1))


def _apply_missing(values: Dict[str, str], fields: Dict[str, str], target: str) -> None:
    values[target] = ""
    fields.pop(target, None)


def _swap_time(values: Dict[str, str], fields: Dict[str, str], a: str, b: str) -> None:
    values[a], values[b] = values[b], values[a]
    fields[a], fields[b] = fields[b], fields[a]


# ---------------------------------------------------------------------------
# 各票种样例构建：返回 (values, parse_fields, extra_truth, defect_details)
# ---------------------------------------------------------------------------

def _normal_operating_steps(kv: str, cn: str, br: str, dis: str, wrong_kv: Optional[str] = None) -> List[str]:
    kv2 = wrong_kv or kv
    return [
        f"检查{kv}kV{cn}{br}断路器确在合闸位置",
        f"断开{kv2}kV{cn}{br}断路器",
        f"检查{kv2}kV{cn}{br}断路器确在断开位置",
        f"拉开{kv}kV{cn}{dis}隔离开关",
        f"检查{kv}kV{cn}{dis}隔离开关确在拉开位置",
        f"在{kv}kV{cn}{br}断路器与{dis}隔离开关间验电确无电压并装设接地线一组",
    ]


def _build_operating_like(
    rng: random.Random,
    ticket_type: str,
    defects: List[Tuple[str, Optional[str]]],
    seq_no: int,
    seed: int,
) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, Any], List[Dict[str, Any]]]:
    line = LINES[seq_no % len(LINES)]
    station = STATIONS[seq_no % len(STATIONS)]
    kv, cn, br, dis = line["kv"], line["cn"], line["breaker"], line["dis"]
    day = DATE_BASE + timedelta(days=seq_no % 15)
    prefix = "CZ" if ticket_type == "operating" else "XZ"

    if ticket_type == "operating":
        task = f"将{kv}kV{cn}{br}断路器由运行转为检修"
    else:
        task = f"将{kv}kV{cn}{line['pole_a']}号-{line['pole_b']}号杆区段由运行转为检修"

    crew = rng.sample(NAMES, 3)
    values: Dict[str, str] = {
        "ticket_no": f"{prefix}-2026-{seq_no:04d}",
        "task": task,
        "start_time": cn_time(day, "08:30"),
        "end_time": cn_time(day, "09:40"),
        "dispatcher": NAMES[(seq_no + 2) % len(NAMES)],
        "guardian": crew[0],
        "operator": crew[1],
        "steps": "",
        "remarks": REMARK.format(seed=seed),
    }
    fields: Dict[str, str] = {
        "ticket_no": values["ticket_no"],
        "task": task,
        "start_time": iso_time(day, "08:30"),
        "end_time": iso_time(day, "09:40"),
        "dispatcher": values["dispatcher"],
        "guardian": crew[0],
        "operator": crew[1],
    }

    if ticket_type == "operating":
        steps = _normal_operating_steps(kv, cn, br, dis)
    else:
        pa, pb, pd = line["pole_a"], line["pole_b"], line["pole_dis"]
        steps = [
            f"断开{kv}kV{cn}{pa}号杆分段断路器",
            f"检查{kv}kV{cn}{pa}号杆分段断路器确在断开位置",
            f"拉开{kv}kV{cn}{pb}号杆{pd}隔离开关",
            f"检查{kv}kV{cn}{pb}号杆{pd}隔离开关确在拉开位置",
            f"在{kv}kV{cn}{pa}号-{pb}号杆区段两侧验电确无电压并各装设接地线一组",
        ]

    details: List[Dict[str, Any]] = []
    for dt, target in defects:
        if dt == "missing_field":
            _apply_missing(values, fields, target)
            details.append({"defect_type": dt, "target": target})
        elif dt == "time_order":
            _swap_time(values, fields, "start_time", "end_time")
            details.append({"defect_type": dt, "target": "start_time,end_time"})
        elif dt == "five_prevention_violation":
            # 防带负荷拉合隔离开关违例：未断开断路器即拉开隔离开关
            if ticket_type == "operating":
                steps = [
                    f"检查{kv}kV{cn}{br}断路器确在合闸位置",
                    f"拉开{kv}kV{cn}{dis}隔离开关",
                ]
            else:
                pa, pb, pd = line["pole_a"], line["pole_b"], line["pole_dis"]
                steps = [
                    f"检查{kv}kV{cn}{pa}号杆分段断路器确在合闸位置",
                    f"拉开{kv}kV{cn}{pb}号杆{pd}隔离开关",
                ]
            details.append({"defect_type": dt, "target": "steps"})
        elif dt == "double_name_mismatch":
            wrong = WRONG_KV[str(kv)]
            if ticket_type == "operating":
                steps = _normal_operating_steps(kv, cn, br, dis, wrong_kv=wrong)
            else:
                pa, pb, pd = line["pole_a"], line["pole_b"], line["pole_dis"]
                steps = [
                    f"断开{kv}kV{cn}{pa}号杆分段断路器",
                    f"检查{wrong}kV{cn}{pa}号杆分段断路器确在断开位置",
                    f"拉开{kv}kV{cn}{pb}号杆{pd}隔离开关",
                    f"检查{kv}kV{cn}{pb}号杆{pd}隔离开关确在拉开位置",
                    f"在{kv}kV{cn}{pa}号-{pb}号杆区段两侧验电确无电压并各装设接地线一组",
                ]
            details.append({"defect_type": dt, "target": "steps", "detail": {"task_kv": kv, "step_kv": wrong}})
        else:
            raise GeneratorError(f"票种 {ticket_type} 不支持缺陷 {dt}")

    values["steps"] = _numbered(steps)
    extra: Dict[str, Any] = {
        "operation_sequence": [{"no": i, "action": a} for i, a in enumerate(steps, 1)],
    }
    return values, fields, extra, details


def _wf_measures(kv: str, cn: str, br: str) -> List[str]:
    # 四要素：停电 / 验电 / 装设接地线 / 悬挂标示牌和装设遮栏
    return [
        f"断开{kv}kV{cn}{br}断路器，断开{br}-1、{br}-3隔离开关",
        f"在{kv}kV{cn}{br}断路器两侧验电确无电压",
        f"在{kv}kV{cn}{br}断路器两侧各装设接地线一组",
        "悬挂“禁止合闸，有人工作！”标示牌，装设遮栏并悬挂“止步，高压危险！”标示牌",
    ]


def _lw_measures(kv: str, cn: str, pa: str, pb: str) -> List[str]:
    return [
        f"断开{kv}kV{cn}发电厂、变电站侧断路器和两侧隔离开关",
        f"在{kv}kV{cn}{pa}号-{pb}号杆区段两端验电确无电压",
        f"在{kv}kV{cn}{pa}号-{pb}号杆区段两端各装设接地线一组",
        "悬挂“禁止合闸，线路有人工作！”标示牌",
    ]


def _second_measures(kv: str, cn: str, br: str) -> List[str]:
    return [
        f"在工作地点悬挂“在此工作！”标示牌",
        f"在相邻带电设备处装设遮栏并悬挂“止步，高压危险！”标示牌",
        f"工作地点设置安全围栏并悬挂标示牌",
    ]


def _build_work_like(
    rng: random.Random,
    ticket_type: str,
    defects: List[Tuple[str, Optional[str]]],
    seq_no: int,
    seed: int,
) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, Any], List[Dict[str, Any]]]:
    line = LINES[seq_no % len(LINES)]
    station = STATIONS[seq_no % len(STATIONS)]
    kv, cn, br = line["kv"], line["cn"], line["breaker"]
    pa, pb = line["pole_a"], line["pole_b"]
    day = DATE_BASE + timedelta(days=seq_no % 15)
    is_line = ticket_type.startswith("line_")
    is_first = ticket_type in ("work_first", "line_work_first")
    prefix = {"work_first": "GZ1", "work_second": "GZ2", "line_work_first": "XL1", "line_work_second": "XL2"}[ticket_type]

    if is_line:
        location = f"{kv}kV{cn}{pa}号-{pb}号杆区段"
        task = (
            f"更换{kv}kV{cn}{pa}号杆绝缘子（需停电）"
            if is_first
            else f"带电清扫{kv}kV{cn}{pa}号杆绝缘子（不需停电）"
        )
    else:
        location = f"{station}{kv}kV{cn}{br}断路器间隔"
        task = (
            f"对{kv}kV{cn}{br}断路器进行检修（需停电）"
            if is_first
            else f"对{kv}kV{cn}{br}断路器机构进行例行检查（不需停电，断路器在试验位置进行）"
        )

    crew = rng.sample(NAMES, 3)
    values: Dict[str, str] = {
        "ticket_no": f"{prefix}-2026-{seq_no:04d}",
        "work_unit": UNITS[seq_no % len(UNITS)],
        "work_head": NAMES[(seq_no + 4) % len(NAMES)],
        "crew": "、".join(crew),
        "location": location,
        "task": task,
        "plan_start": cn_time(day, "08:00"),
        "plan_end": cn_time(day, "17:00"),
        "measures": "",
        "issuer": NAMES[(seq_no + 1) % len(NAMES)],
        "permit_start": cn_time(day, "08:10"),
        "permitor": NAMES[(seq_no + 3) % len(NAMES)],
        "end_time": cn_time(day, "16:50"),
        "remarks": REMARK.format(seed=seed),
    }
    fields: Dict[str, str] = {
        "ticket_no": values["ticket_no"],
        "work_unit": values["work_unit"],
        "work_head": values["work_head"],
        "crew": values["crew"],
        "location": location,
        "task": task,
        "plan_start": iso_time(day, "08:00"),
        "plan_end": iso_time(day, "17:00"),
        "issuer": values["issuer"],
        "permit_start": iso_time(day, "08:10"),
        "permitor": values["permitor"],
        "end_time": iso_time(day, "16:50"),
    }

    if is_first:
        measures = _lw_measures(kv, cn, pa, pb) if is_line else _wf_measures(kv, cn, br)
    else:
        measures = _second_measures(kv, cn, br)

    details: List[Dict[str, Any]] = []
    for dt, target in defects:
        if dt == "missing_field":
            _apply_missing(values, fields, target)
            details.append({"defect_type": dt, "target": target})
        elif dt == "permit_time_out_of_range":
            mode = rng.choice(["before_start", "after_end"])
            hm = "07:40" if mode == "before_start" else "17:30"
            values["permit_start"] = cn_time(day, hm)
            fields["permit_start"] = iso_time(day, hm)
            details.append({"defect_type": dt, "target": "permit_start", "detail": {"mode": mode}})
        elif dt == "signature_gap":
            _apply_missing(values, fields, target)
            details.append({"defect_type": dt, "target": target})
        elif dt == "measure_missing":
            dropped = rng.randrange(len(measures))
            measures = [m for i, m in enumerate(measures) if i != dropped]
            details.append({"defect_type": dt, "target": "measures", "detail": {"dropped_index": dropped}})
        elif dt == "ticket_type_mismatch":
            # 第二种工作票（不需停电）的任务含需停电作业 → 票种与内容错配
            if is_line:
                values["task"] = f"更换{kv}kV{cn}{pa}号杆绝缘子（需停电作业）"
            else:
                values["task"] = f"处理{kv}kV{cn}{br}断路器机构缺陷（需将{br}断路器由运行位置转检修并停电）"
            fields["task"] = values["task"]
            details.append({"defect_type": dt, "target": "task"})
        else:
            raise GeneratorError(f"票种 {ticket_type} 不支持缺陷 {dt}")

    values["measures"] = _numbered(measures)
    extra: Dict[str, Any] = {"safety_measures": measures}
    return values, fields, extra, details


def _build_emergency(
    rng: random.Random,
    defects: List[Tuple[str, Optional[str]]],
    seq_no: int,
    seed: int,
) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, Any], List[Dict[str, Any]]]:
    day = DATE_BASE + timedelta(days=seq_no % 15)
    crew = rng.sample(NAMES, 3)
    task = "处理10kV城区线815断路器故障跳闸（保护动作，站内检查发现815断路器机构漏气）"
    values: Dict[str, str] = {
        "ticket_no": f"QX-2026-{seq_no:04d}",
        "work_unit": UNITS[seq_no % len(UNITS)],
        "task": task,
        "measures": "",
        "start_time": cn_time(day, "14:00"),
        "end_time": cn_time(day, "17:30"),
        "work_head": NAMES[(seq_no + 5) % len(NAMES)],
        "crew": "、".join(crew),
        "permitor": NAMES[(seq_no + 6) % len(NAMES)],
        "remarks": REMARK.format(seed=seed),
    }
    fields: Dict[str, str] = {
        "ticket_no": values["ticket_no"],
        "work_unit": values["work_unit"],
        "task": task,
        "start_time": iso_time(day, "14:00"),
        "end_time": iso_time(day, "17:30"),
        "work_head": values["work_head"],
        "crew": values["crew"],
        "permitor": values["permitor"],
    }
    measures = [
        "断开10kV城区线815断路器并在两侧验电确无电压",
        "在故障点两侧各装设接地线一组",
        "在操作把手上悬挂“禁止合闸，有人工作！”标示牌",
    ]

    details: List[Dict[str, Any]] = []
    for dt, target in defects:
        if dt == "missing_field":
            _apply_missing(values, fields, target)
            details.append({"defect_type": dt, "target": target})
        elif dt == "time_order":
            _swap_time(values, fields, "start_time", "end_time")
            details.append({"defect_type": dt, "target": "start_time,end_time"})
        elif dt == "signature_gap":
            _apply_missing(values, fields, target)
            details.append({"defect_type": dt, "target": target})
        else:
            raise GeneratorError(f"票种 emergency_repair 不支持缺陷 {dt}")

    values["measures"] = _numbered(measures)
    extra: Dict[str, Any] = {"safety_measures": measures}
    return values, fields, extra, details


# ---------------------------------------------------------------------------
# 总装：build_all 返回 {文件名: 文件内容}（内存态，测试直接比对位级一致）
# ---------------------------------------------------------------------------

def _render_truth(
    fname: str,
    seed: int,
    ticket_type: str,
    kind: str,
    defects: List[Dict[str, Any]],
    expect: List[str],
    also: List[str],
    fields: Dict[str, str],
    extra: Dict[str, Any],
) -> str:
    payload: Dict[str, Any] = {
        "schema": TRUTH_SCHEMA,
        "file": fname,
        "generator": GENERATOR_ID,
        "seed": seed,
        "ticket_type": ticket_type,
        "kind": kind,
        "defects": defects,
        "expect": expect,
        "also_expect": also,
        "fields": fields,
    }
    payload.update(extra)
    payload["semantics_note"] = (
        "expect/also_expect 为 check_type 粒度主期望/隐含结论，评测按『文档全部非 pass 集合』对账；"
        "fields（时间 ISO）与 operation_sequence/safety_measures 为解析真值，被注入缺失的字段不出现在 fields，"
        "时间倒挂时照实登记票面所见值；备注栏为虚构声明，不入真值。"
    )
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def build_all(seed: int = DEFAULT_SEED) -> Dict[str, str]:
    templates = load_templates()
    catalog = load_catalog()
    plans = build_plans()
    _validate_plans(plans, catalog)

    caps = catalog["caps"]
    files: Dict[str, str] = {}
    manifest_files: List[Dict[str, Any]] = []
    counts = {"total": 0, "normal": 0, "defect": 0}

    for idx, (ticket_type, slug, defects) in enumerate(plans, 1):
        tpl = templates[ticket_type]
        rng = random.Random(f"{seed}:{ticket_type}:{slug}")
        if ticket_type in ("operating", "line_operating"):
            values, fields, extra, details = _build_operating_like(rng, ticket_type, defects, idx, seed)
            if not (caps["operation_steps"]["min"] <= len(extra["operation_sequence"]) <= caps["operation_steps"]["max"]):
                raise GeneratorError(f"{slug} 操作序列数超出封顶")
        elif ticket_type == "emergency_repair":
            values, fields, extra, details = _build_emergency(rng, defects, idx, seed)
        else:
            values, fields, extra, details = _build_work_like(rng, ticket_type, defects, idx, seed)
        if "safety_measures" in extra and not (
            caps["safety_measure_items"]["min"] <= len(extra["safety_measures"]) <= caps["safety_measure_items"]["max"]
        ):
            raise GeneratorError(f"{slug} 安全措施条目数超出封顶")
        if "crew" in fields and not (caps["crew_members"]["min"] <= len(fields["crew"].split("、")) <= caps["crew_members"]["max"]):
            raise GeneratorError(f"{slug} 人员名单超出封顶")

        text = render((TEMPLATE_DIR / tpl["file"]).read_text(encoding="utf-8"), values)
        fname = f"gen-{ticket_type}-{idx:03d}-{slug}.txt"
        if "{{" in text:
            raise GeneratorError(f"{fname} 渲染残留占位符")
        expect, also = _expect_for(defects, catalog)
        kind = "normal" if not defects else "defect"
        truth = _render_truth(fname, seed, ticket_type, kind, details, expect, also, fields, extra)
        files[fname] = text
        files[f"{fname[:-4]}.truth.json"] = truth
        counts["total"] += 1
        counts[kind] += 1
        manifest_files.append(
            {
                "file": fname,
                "truth": f"{fname[:-4]}.truth.json",
                "ticket_type": ticket_type,
                "kind": kind,
                "defects": details,
                "expect": expect,
                "also_expect": also,
            }
        )

    manifest = {
        "schema": MANIFEST_SCHEMA,
        "generator": GENERATOR_ID,
        "seed": seed,
        "caps": caps,
        "counts": counts,
        "source": f"程序化自制：{GENERATOR_ID}（seed={seed}，内容全部虚构）",
        "license": "项目自带（MIT）",
        "files": manifest_files,
    }
    files["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    return files


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="generate.py",
        description="两票样例生成器：固定 seed、正常/缺陷注入、真值 JSON（详见 data/generator/README.md）",
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="输出目录（默认 data/samples/gen）")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="随机种子（默认 20261002）")
    parser.add_argument("--force", action="store_true", help="清空输出目录后重新生成（先清旧行）")
    parser.add_argument("--dry-run", action="store_true", help="只打印生成文件清单，不写文件")
    args = parser.parse_args(argv)

    try:
        files = build_all(seed=args.seed)
    except GeneratorError as e:
        print(f"生成器配置错误: {e}", file=sys.stderr)
        return 2

    out = Path(args.out)
    if args.dry_run:
        for name in sorted(files):
            print(name)
        return 0
    if out.exists() and any(out.iterdir()) and not args.force:
        print(f"输出目录非空: {out}（重生成请加 --force，将先清空目录）", file=sys.stderr)
        return 2
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        # newline="\n" 显式锁 LF（位级一致门），Path.write_text 的 newline 参数 3.10 才有
        with open(out / name, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
    print(f"已生成 {len(files)} 个文件（{sum(1 for n in files if n.endswith('.txt'))} 份票据）→ {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
