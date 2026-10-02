"""报告章节结构构建（零依赖纯函数）：run_pipeline 结果 → 章节序列。

docx 渲染（docx_render.py）与 Web 报告预览（web/app.py）共用同一结构，
保证"报告预览 = 导出内容"。章节序按 plan/04 §5 定稿：
元信息 → 一、结论汇总 → 二、分级问题清单 → 三、逐条证据（含原文摘录）
→ 四、整改建议 → 五、待人工确认（独立成节）→ 六、签署栏。

无外链纪律：本模块输出不含任何 URL/超链接（依据只取 standard+clause+status+quote，
登记渠道 channel 等出处元数据不入报告）；判据 find_external_links 进测试。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..rules.checks import FIELD_LABELS

VERDICT_COMPLIANT = "合规"
VERDICT_VIOLATION = "不合规"
VERDICT_MANUAL = "待人工确认"

# 风险分级排序基线（M3 口径：required=低、time/signature=一般、type_match/measure=较大、five_prevention=重大）
RISK_ORDER = {"重大": 0, "较大": 1, "一般": 2, "低": 3}


def _basis_text(basis: Optional[dict], with_status: bool = True) -> str:
    if not basis:
        return "—"
    text = f"{basis.get('standard', '')} {basis.get('clause', '')}".strip()
    if with_status and basis.get("status"):
        text += f"（{basis['status']}）"
    return text or "—"


def overall_verdict(summary: Dict[str, int]) -> str:
    """总体判定：有不合规即"不合规（需整改）"；否则有待确认即"待人工确认"；否则"合规"。"""
    if summary.get("不合规", 0) > 0:
        return "不合规（需整改）"
    if summary.get("待人工确认", 0) > 0:
        return "待人工确认"
    return "合规"


def _field_value(card: dict, key: str, default: str = "—") -> str:
    fv = card.get("fields", {}).get(key)
    if not fv or fv.get("value") in (None, ""):
        return default
    return str(fv.get("value"))


def _label(field: str) -> str:
    return FIELD_LABELS.get(field, field)


def _violations(conclusions: List[dict]) -> List[dict]:
    return [c for c in conclusions if c["verdict"] == VERDICT_VIOLATION]


def _manuals(conclusions: List[dict]) -> List[dict]:
    return [c for c in conclusions if c["verdict"] == VERDICT_MANUAL]


def _sorted_by_risk(items: List[dict]) -> List[dict]:
    return sorted(items, key=lambda c: (RISK_ORDER.get(c.get("risk"), 99), c["rule_id"]))


def build_report_sections(result: dict, meta: Optional[dict] = None) -> List[Dict[str, Any]]:
    """run_pipeline 结果 → 报告章节序列（纯函数，docx 与 Web 预览共用）。

    meta 可选键：source_file（来源票据文件名）/ generated_at（审核时间）/ version（工具版本）。
    """
    meta = meta or {}
    card = result["card"]
    conclusions: List[dict] = result["conclusions"]
    summary: Dict[str, int] = result["summary"]
    warnings: List[str] = result.get("warnings", [])
    sections: List[Dict[str, Any]] = []

    violations = _sorted_by_risk(_violations(conclusions))
    manuals = _manuals(conclusions)

    # ------------------------------------------------------------------ 元信息
    sections.append({"kind": "title", "text": "电力两票智能审核报告"})
    meta_rows = [
        ["票据类型", card.get("ticket_type_name", "未知票种")],
        ["票据编号", _field_value(card, "ticket_no", "（未提取到）")],
        ["总体判定", overall_verdict(summary)],
    ]
    if meta.get("source_file"):
        meta_rows.append(["来源文件", meta["source_file"]])
    if meta.get("generated_at"):
        meta_rows.append(["审核时间", meta["generated_at"]])
    if meta.get("version"):
        meta_rows.append(["审核工具", f"powerticket {meta['version']}"])
    sections.append({"kind": "meta_table", "rows": meta_rows})

    # ------------------------------------------------------------------ 一、结论汇总
    sections.append({"kind": "heading", "level": 1, "text": "一、结论汇总"})
    sections.append(
        {
            "kind": "paragraph",
            "text": (
                f"总体判定：{overall_verdict(summary)}。"
                f"共 {len(conclusions)} 条规则结论："
                f"合规 {summary.get('合规', 0)} 条 ｜ 不合规 {summary.get('不合规', 0)} 条"
                f" ｜ 待人工确认 {summary.get('待人工确认', 0)} 条。"
            ),
        }
    )
    sections.append(
        {
            "kind": "table",
            "header": ["规则编号", "规则名称", "判定", "风险等级", "依据"],
            "rows": [
                [
                    c["rule_id"],
                    c["name"],
                    c["verdict"],
                    c.get("risk") or "—",
                    _basis_text(c.get("basis")),
                ]
                for c in conclusions
            ],
        }
    )

    # ------------------------------------------------------------------ 二、分级问题清单
    sections.append({"kind": "heading", "level": 1, "text": "二、分级问题清单（按风险等级）"})
    if not violations:
        sections.append({"kind": "paragraph", "text": "本票未发现不合规项。"})
    else:
        sections.append(
            {
                "kind": "table",
                "header": ["风险等级", "规则编号", "规则名称", "问题摘要"],
                "rows": [
                    [c.get("risk") or "—", c["rule_id"], c["name"], c["evidence"][0] if c["evidence"] else "—"]
                    for c in violations
                ],
            }
        )

    # ------------------------------------------------------------------ 三、逐条证据（含原文摘录）
    sections.append({"kind": "heading", "level": 1, "text": "三、逐条证据（含原文摘录）"})
    if violations:
        sections.append({"kind": "paragraph", "text": "以下逐条列示不合规项的证据与票面原文摘录。"})
        for c in violations:
            risk = f"｜风险等级 {c['risk']}" if c.get("risk") else ""
            sections.append({"kind": "heading", "level": 2, "text": f"{c['rule_id']} {c['name']}（{c['verdict']}{risk}）"})
            sections.append({"kind": "paragraph", "text": f"依据：{_basis_text(c.get('basis'))}"})
            basis_quote = (c.get("basis") or {}).get("quote", "")
            if basis_quote:
                sections.append({"kind": "paragraph", "text": f"规范原文：{basis_quote}"})
            sections.append({"kind": "bullets", "items": [str(e) for e in c.get("evidence", [])] or ["—"]})
    else:
        sections.append({"kind": "paragraph", "text": "无不合规项；证据明细见「待人工确认」（如有）与结论汇总表。"})

    sections.append({"kind": "heading", "level": 2, "text": "票面原文摘录"})
    sections.append({"kind": "paragraph", "text": "以下为解析所得票面原文逐字摘录（来自参数卡证据链）。"})
    field_rows = [
        [_label(key), str(fv.get("value")), fv["evidence"]["quote"]]
        for key, fv in card.get("fields", {}).items()
        if fv.get("evidence", {}) and fv["evidence"].get("quote")
    ]
    if field_rows:
        sections.append({"kind": "table", "header": ["字段", "提取值", "原文摘录"], "rows": field_rows})
    steps = card.get("operation_sequence") or []
    if steps:
        sections.append(
            {
                "kind": "table",
                "header": ["步骤", "操作内容", "原文摘录"],
                "rows": [
                    [str(s.get("no")), str(s.get("action")), (s.get("evidence") or {}).get("quote", "—")]
                    for s in steps
                ],
            }
        )
    measures = card.get("safety_measures") or []
    if measures:
        sections.append(
            {
                "kind": "table",
                "header": ["条目", "安全措施内容", "原文摘录"],
                "rows": [
                    [str(m.get("no")), str(m.get("text")), (m.get("evidence") or {}).get("quote", "—")]
                    for m in measures
                ],
            }
        )
    if not field_rows and not steps and not measures:
        sections.append({"kind": "paragraph", "text": "（无原文摘录）"})

    # ------------------------------------------------------------------ 四、整改建议
    sections.append({"kind": "heading", "level": 1, "text": "四、整改建议"})
    suggestions = [
        (c, str(c.get("suggestion") or "").strip())
        for c in violations + manuals
        if str(c.get("suggestion") or "").strip()
    ]
    if not suggestions:
        sections.append({"kind": "paragraph", "text": "无。"})
    else:
        sections.append(
            {
                "kind": "bullets",
                "items": [f"[{c['rule_id']}] {c['name']}：{text}" for c, text in suggestions],
            }
        )

    # ------------------------------------------------------------------ 五、待人工确认（独立成节）
    sections.append({"kind": "heading", "level": 1, "text": "五、待人工确认"})
    if not manuals and not warnings:
        sections.append({"kind": "paragraph", "text": "无待人工确认事项。"})
    for c in manuals:
        sections.append({"kind": "heading", "level": 2, "text": f"{c['rule_id']} {c['name']}（{c['verdict']}）"})
        sections.append({"kind": "paragraph", "text": f"依据：{_basis_text(c.get('basis'))}"})
        sections.append({"kind": "bullets", "items": [str(e) for e in c.get("evidence", [])] or ["—"]})
    if warnings:
        sections.append({"kind": "paragraph", "text": "解析告警（票面异常，建议人工复核原票）："})
        sections.append({"kind": "bullets", "items": [str(w) for w in warnings]})

    # ------------------------------------------------------------------ 六、签署栏
    sections.append({"kind": "heading", "level": 1, "text": "六、签署栏"})
    sections.append(
        {
            "kind": "table",
            "header": ["环节", "签字", "日期"],
            "rows": [["审核人", "", ""], ["复核人", "", ""], ["批准人", "", ""]],
        }
    )
    sections.append(
        {
            "kind": "paragraph",
            "text": "本报告由 powerticket 自动生成，供人工复核；最终结论以签署栏签认为准。",
        }
    )
    return sections
