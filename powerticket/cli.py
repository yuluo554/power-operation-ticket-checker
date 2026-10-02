"""命令行入口：demo / parse / check / run / report / web / benchmark。

core 通路（demo/parse/check/run）零第三方依赖；report/web 懒加载 extras 依赖，
不可用时打印安装提示以退出码 2 返回，不抛裸 traceback。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
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


def _report_meta(source_file: str) -> dict:
    return {
        "source_file": source_file,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "version": __version__,
    }


def _render_report(result: dict, out_path: Path, source_file: str) -> Path:
    from .report.docx_render import render_docx_report

    return render_docx_report(result, out_path, _report_meta(source_file))


def _cmd_run(args) -> int:
    """run：单票端到端（同 demo 形态）或目录批量 check → 汇总输出（core 零依赖）。"""
    path = Path(args.file)
    if path.is_file():
        return _run_single(path, args)
    if path.is_dir():
        return _run_directory(path, args)
    print(f"路径不存在: {path}", file=sys.stderr)
    return 2


def _run_single(path: Path, args) -> int:
    try:
        result = run_pipeline(
            path.read_text(encoding="utf-8"), allow_llm_fallback=args.llm_fallback
        )
    except (ParseError, RuleError) as e:
        print(f"校核失败: {e}", file=sys.stderr)
        return 2
    report_path = None
    if args.report:
        out = Path(args.report)
        if out.is_dir():
            print(
                "--report 需为 docx 文件路径（单票模式）；目录模式请对目录运行 run",
                file=sys.stderr,
            )
            return 2
        try:
            report_path = _render_report(result, out, path.name)
        except Exception as e:
            print(_report_error_text(e), file=sys.stderr)
            return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if report_path is not None:
            print(f"报告已生成: {report_path}", file=sys.stderr)
    else:
        _print_pipeline(result)
        if report_path is not None:
            print(f"报告已生成: {report_path}")
    return 0


def _run_directory(path: Path, args) -> int:
    files = sorted(path.glob("*.txt"))
    if not files:
        print(f"目录下没有 .txt 票据: {path}", file=sys.stderr)
        return 2
    report_dir = None
    if args.report:
        report_dir = Path(args.report)
        if report_dir.is_file():
            print("--report 在目录模式下需为目录路径（每票一份 docx）", file=sys.stderr)
            return 2
        # 批量开始前先探测报告依赖，避免处理到一半失败
        try:
            from .report.docx_render import ensure_docx_available

            ensure_docx_available()
        except Exception as e:
            print(_report_error_text(e), file=sys.stderr)
            return 2

    records = []
    for f in files:
        try:
            result = run_pipeline(
                f.read_text(encoding="utf-8"), allow_llm_fallback=args.llm_fallback
            )
        except (ParseError, RuleError) as e:
            records.append({"file": f.name, "status": "error", "error": str(e)})
            continue
        records.append({"file": f.name, "status": "ok", **result})
        if report_dir is not None:
            try:
                _render_report(result, report_dir / f"{f.stem}.docx", f.name)
            except Exception as e:
                print(_report_error_text(e), file=sys.stderr)
                return 2

    clean = sum(
        1
        for r in records
        if r["status"] == "ok"
        and r["summary"]["不合规"] == 0
        and r["summary"]["待人工确认"] == 0
    )
    failed = sum(1 for r in records if r["status"] == "error")
    aggregate = {
        "total": len(files),
        "clean": clean,
        "with_findings": len(records) - clean - failed,
        "failed": failed,
    }
    if args.json:
        print(
            json.dumps(
                {"mode": "directory", "directory": str(path), "aggregate": aggregate, "results": records},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"== 目录批量审核（{path}，共 {len(files)} 份）==")
        for r in records:
            if r["status"] == "error":
                print(f"[失败] {r['file']} ｜ {r['error']}")
                continue
            s = r["summary"]
            non_pass = [c["rule_id"] for c in r["conclusions"] if c["verdict"] != "合规"]
            mark = "通过" if not non_pass else "问题"
            print(
                f"[{mark}] {r['file']} ｜ {r['card']['ticket_type']} ｜"
                f" 合规 {s['合规']} / 不合规 {s['不合规']} / 待人工确认 {s['待人工确认']}"
                + (f" ｜ {'、'.join(non_pass)}" if non_pass else "")
            )
        print(
            f"== 批量汇总 == 共 {aggregate['total']} 份 ｜ 全部合规 {clean}"
            f" ｜ 存在问题 {aggregate['with_findings']} ｜ 处理失败 {failed}"
        )
        if report_dir is not None:
            print(f"逐票报告目录: {report_dir.resolve()}")
    return 1 if failed else 0


def _report_error_text(e: Exception) -> str:
    from .report import ReportUnavailable

    if isinstance(e, ReportUnavailable):
        return str(e)
    return f"报告生成失败: {e}"


def _cmd_report(args) -> int:
    try:
        result = run_pipeline(
            _read_ticket(args.file), allow_llm_fallback=args.llm_fallback
        )
    except (ParseError, RuleError) as e:
        print(f"校核失败: {e}", file=sys.stderr)
        return 2
    src = Path(args.file)
    out = Path(args.out) if args.out else src.parent / f"{src.stem}-审核报告.docx"
    try:
        report_path = _render_report(result, out, src.name)
    except Exception as e:
        print(_report_error_text(e), file=sys.stderr)
        return 2
    print(f"报告已生成: {report_path.resolve()}")
    return 0


def _cmd_web(args) -> int:
    try:
        import uvicorn

        from .web.app import create_app
    except ImportError as e:
        print(
            f"Web 面板不可用（{e}）。依赖安装：py -m pip install -e .[web]",
            file=sys.stderr,
        )
        return 2
    print(f"Web 面板启动: http://{args.host}:{args.port}（Ctrl+C 退出）")
    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="info")
    return 0


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

    p = sub.add_parser(
        "run", help="端到端审核：单票明细或目录批量（汇总输出，core 零依赖）"
    )
    p.add_argument("file", help="票据文本文件或票据目录")
    p.add_argument("--json", action="store_true", help="以 JSON 输出（非 JSON 提示走 stderr）")
    p.add_argument(
        "--report",
        default=None,
        help="同时导出 docx 报告：单票模式为文件路径；目录模式为目录（每票一份）",
    )
    p.add_argument(
        "--llm-fallback",
        action="store_true",
        help="规则解析失败时尝试 LLM 兜底（需安装 .[llm] 并配置 DASHSCOPE_API_KEY；不可用自动降级纯规则通路）",
    )
    p.set_defaults(func=_cmd_run)

    p = sub.add_parser("report", help="单票 docx 审核报告导出（需 .[report]）")
    p.add_argument("file", help="票据文本文件路径")
    p.add_argument(
        "--out", default=None, help="输出 docx 路径（默认与票据同目录 <票名>-审核报告.docx）"
    )
    p.add_argument(
        "--llm-fallback",
        action="store_true",
        help="规则解析失败时尝试 LLM 兜底（需安装 .[llm] 并配置 DASHSCOPE_API_KEY；不可用自动降级纯规则通路）",
    )
    p.set_defaults(func=_cmd_report)

    p = sub.add_parser("web", help="启动 Web 审核面板（FastAPI，需 .[web]）")
    p.add_argument("--host", default="127.0.0.1", help="监听地址（默认 127.0.0.1）")
    p.add_argument("--port", type=int, default=8000, help="监听端口（默认 8000）")
    p.set_defaults(func=_cmd_web)

    return parser


def main(argv=None) -> int:
    _ensure_utf8_stdio()
    args = build_parser().parse_args(argv)
    return args.func(args)
