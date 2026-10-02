"""命令行入口：demo / parse / check / run / report / web / benchmark。

子命令按里程碑逐步点亮；未实现的打印计划位置后以退出码 2 返回，不抛裸 traceback。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .llm.fallback import parse_ticket_with_fallback
from .parse import ParseError
from .pipeline import run_pipeline
from .rules import RuleError

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMO_SAMPLE = _REPO_ROOT / "data" / "samples" / "sample-operating-01.txt"


def _ensure_utf8_stdio() -> None:
    # Windows 控制台默认 GBK，中文输出统一走 UTF-8（配合 py -X utf8 双保险）
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _read_ticket(path: str) -> str:
    p = Path(path)
    if not p.is_file():
        raise ParseError(f"文件不存在: {path}")
    return p.read_text(encoding="utf-8")


def _print_pipeline(result: dict) -> None:
    card = result["card"]
    print("== 票面参数卡 ==")
    print(f"票种: {card['ticket_type']}（{card['ticket_type_name']}）")
    for name, fv in card["fields"].items():
        print(f"  {name}: {fv['value']}  ｜证据｜ {fv['evidence']['quote']}")
    print(f"操作序列: {len(card['operation_sequence'])} 项")
    if card["safety_measures"]:
        print(f"安全措施: {len(card['safety_measures'])} 条")
    for w in result["warnings"]:
        print(f"  [告警] {w}")
    print("== 校核结论 ==")
    for c in result["conclusions"]:
        risk = f"（风险：{c['risk']}）" if c["risk"] else ""
        print(f"[{c['rule_id']}] {c['name']}：{c['verdict']}{risk}")
        basis = c["basis"]
        print(f"    依据：{basis['standard']} {basis['clause']}（{basis['status']}）")
    s = result["summary"]
    print(f"== 汇总 == 合规 {s['合规']} ｜ 不合规 {s['不合规']} ｜ 待人工确认 {s['待人工确认']}")


def _cmd_demo(args) -> int:
    try:
        result = run_pipeline(_read_ticket(str(_DEMO_SAMPLE)))
    except (ParseError, RuleError) as e:
        print(f"demo 失败: {e}", file=sys.stderr)
        return 2
    _print_pipeline(result)
    return 0


def _cmd_parse(args) -> int:
    try:
        card = parse_ticket_with_fallback(
            _read_ticket(args.file), allow_llm=args.llm_fallback
        )
    except ParseError as e:
        print(f"解析失败: {e}", file=sys.stderr)
        return 2
    print(json.dumps(card.to_dict(), ensure_ascii=False, indent=2))
    return 0


def _cmd_check(args) -> int:
    try:
        result = run_pipeline(_read_ticket(args.file), allow_llm_fallback=args.llm_fallback)
    except (ParseError, RuleError) as e:
        print(f"校核失败: {e}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _cmd_benchmark(args) -> int:
    from .eval.endtoend import run as run_endtoend
    from .eval.parse_f1 import run as run_parse_f1

    parse_result = run_parse_f1()
    e2e_result = run_endtoend()
    if args.json:
        # --json 输出纯净 JSON（机器可读），不带额外文案
        print(json.dumps({"parse_f1": parse_result, "endtoend": e2e_result}, ensure_ascii=False, indent=2))
        return 0 if parse_result["gate"]["pass"] and e2e_result["gate"]["pass"] else 1
    print(f"== 内置基准（{parse_result['samples']} 份样例，零 API 依赖）==")
    items = parse_result["items"]
    print(
        f"[parse_f1] 字段级：TP {items['tp']} / FP {items['fp']} / FN {items['fn']}"
        f" ｜ P {parse_result['precision']} R {parse_result['recall']} F1 {parse_result['f1']}"
        f"（门槛 ≥{parse_result['gate']['f1_min']}）"
    )
    det, acc = e2e_result["detection"], e2e_result["accuracy"]
    print(
        f"[endtoend] 检出率 {det['rate']}（{det['hit']}/{det['total']} 缺陷样例）"
        f" ｜ 误报率 {e2e_result['false_positive_rate']}（{e2e_result['false_positive_samples']} 份）"
        f" ｜ 判定准确率 {acc['rate']}（{acc['correct']}/{acc['total']}）"
    )
    for failure in e2e_result["failures"]:
        print(f"  [未命中] {failure['file']}（{failure['kind']}）漏检={failure['miss']} 误报={failure['extra']}")
    gates_ok = parse_result["gate"]["pass"] and e2e_result["gate"]["pass"]
    print(f"基准门槛（F1≥0.95、误报 0）：{'全部通过' if gates_ok else '未通过'}")
    return 0 if gates_ok else 1


def _not_implemented(title: str, milestone: str, hint: str = ""):
    def handler(args) -> int:
        print(f"{title}计划 {milestone} 提供，当前骨架尚未实现。{hint}")
        return 2

    return handler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="powerticket",
        description="电力'两票'（工作票/操作票）智能审核与合规校核系统",
    )
    parser.add_argument("--version", action="version", version=f"powerticket {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("demo", help="内置样例端到端演示（解析+校核）")
    p.set_defaults(func=_cmd_demo)

    p = sub.add_parser("parse", help="票据文本 → 票面参数卡 JSON")
    p.add_argument("file", help="票据文本文件路径")
    p.add_argument(
        "--llm-fallback",
        action="store_true",
        help="规则解析失败时尝试 LLM 兜底（需安装 .[llm] 并配置 DASHSCOPE_API_KEY；不可用自动降级纯规则通路）",
    )
    p.set_defaults(func=_cmd_parse)

    p = sub.add_parser("check", help="票据文本 → 参数卡+校核结论 JSON")
    p.add_argument("file", help="票据文本文件路径")
    p.add_argument(
        "--llm-fallback",
        action="store_true",
        help="规则解析失败时尝试 LLM 兜底（需安装 .[llm] 并配置 DASHSCOPE_API_KEY；不可用自动降级纯规则通路）",
    )
    p.set_defaults(func=_cmd_check)

    p = sub.add_parser("benchmark", help="内置基准评测（解析 F1 / 检出率 / 误报率 / 判定准确率）")
    p.add_argument("--json", action="store_true", help="以 JSON 输出原始指标")
    p.set_defaults(func=_cmd_benchmark)

    for cmd, title, ms, hint, with_file in (
        ("run", "多票端到端与目录模式", "M5", "先用 demo/parse/check 体验骨架能力。", True),
        ("report", "docx 报告导出", "M5", "", True),
        ("web", "Web 审核面板", "M5", "", False),
    ):
        p = sub.add_parser(cmd, help=f"{title}（{ms} 提供）")
        if with_file:
            p.add_argument("file", nargs="?", help="票据文本文件路径")
        p.set_defaults(func=_not_implemented(title, ms, hint))

    return parser


def main(argv=None) -> int:
    _ensure_utf8_stdio()
    args = build_parser().parse_args(argv)
    return args.func(args)
