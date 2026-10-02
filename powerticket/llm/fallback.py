"""LLM 兜底抽取：规则解析失败/低置信度字段 → LLM → 同一 TicketCard 出口（M4）。

纪律（plan/00 结论纪律 + plan/04 §2）：
- LLM 只做非结构化抽取兜底，数值结论永远来自确定性规则；
- **缺失字段不兜底**：字段缺失本身是合规信号（required_field 判定），兜底填充会掩盖缺陷；
- **摘录逐字回验**：LLM 字段/条目必须携带原文逐字摘录（quote 为归一化原文的子串），
  否则该项不入卡 + warnings 留痕（防幻觉）；
- 时间值必须 ISO（YYYY-MM-DDTHH:MM），非法丢弃 + 留痕；
- 任何不可用（依赖/密钥/网络/坏响应）抛 LLMUnavailable，调用方降级纯规则通路
  （断供降级测试锁定）。
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Optional

from ..models import Evidence, FieldValue, OperationStep, SafetyMeasure, TicketCard
from ..models.card import TICKET_TYPE_NAMES
from ..parse import ParseError, parse_ticket
from ..parse.cleaning import normalize_text
from . import LLMUnavailable
from .client import chat as default_chat

# LLM 抽取字段置信度：低于规则解析（1.0），供下游按置信度分档（M4 定稿口径）
LLM_CONFIDENCE = 0.7
LOW_CONFIDENCE_THRESHOLD = 0.6

# 字段白名单 = 7 票种模板注册标量字段并集（data/ticket_templates/templates.json；steps/measures 走列表块）
KNOWN_FIELD_KEYS = frozenset(
    {
        "ticket_no", "work_unit", "work_head", "crew", "location", "task",
        "start_time", "end_time", "plan_start", "plan_end", "permit_start",
        "issuer", "permitor", "dispatcher", "guardian", "operator", "remarks",
    }
)
TIME_FIELDS = frozenset({"start_time", "end_time", "plan_start", "plan_end", "permit_start"})
ISO_TIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$")

TICKET_TYPE_CODES = frozenset(TICKET_TYPE_NAMES)

_SYSTEM_PROMPT = (
    "你是电力'两票'（工作票/操作票）文本抽取助手。只做信息抽取，不做合规判断，"
    "不编造票面没有的内容。输出单个 JSON 对象，不要输出任何其他文字。"
    "evidence_quote 必须是输入原文的逐字子串（原样复制，不得改写）；"
    "时间值输出 ISO 格式（YYYY-MM-DDTHH:MM）。"
)

_JSON_SCHEMA_HINT = """{
  "ticket_type": "operating|line_operating|work_first|work_second|line_work_first|line_work_second|emergency_repair",
  "fields": {"<字段名>": {"value": "<值>", "evidence_quote": "<原文逐字摘录>"}},
  "operation_sequence": [{"no": 1, "action": "<操作项>", "evidence_quote": "<原文逐字摘录>"}],
  "safety_measures": [{"no": 1, "text": "<措施条目>", "evidence_quote": "<原文逐字摘录>"}]
}
可用字段名：ticket_no, work_unit, work_head, crew, location, task, start_time, end_time,
plan_start, plan_end, permit_start, issuer, permitor, dispatcher, guardian, operator, remarks。
票面没有的字段不要输出。"""


def build_messages(source_text: str) -> List[Dict[str, str]]:
    user = (
        "请从以下票据文本抽取信息，输出 JSON（schema 见下）。\n"
        f"schema：\n{_JSON_SCHEMA_HINT}\n票据文本：\n{source_text}"
    )
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def _extract_json(content: str) -> Dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise LLMUnavailable("LLM 响应不含 JSON 对象")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMUnavailable(f"LLM 响应不是合法 JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise LLMUnavailable("LLM 响应 JSON 不是对象")
    return data


def _verified_quote(source_text: str, quote: Any) -> Optional[str]:
    """摘录逐字回验：quote 为原文逐字子串则原样返回，否则 None（调用方丢弃该项）。"""
    if isinstance(quote, str) and quote and quote in source_text:
        return quote
    return None


def _step_no(item: Dict[str, Any], fallback_no: int, warnings: List[str], key: str) -> int:
    no = item.get("no")
    if isinstance(no, bool):  # bool 是 int 子类，显式排除
        return fallback_no
    if isinstance(no, int) and no > 0:
        return no
    try:
        no = int(str(no))
    except (TypeError, ValueError):
        return fallback_no
    if no > 0:
        return no
    warnings.append(f"LLM 兜底条目序号非法已顺延: {key}={item.get('no')!r}")
    return fallback_no


def card_from_llm_response(content: str, source_text: str) -> TicketCard:
    """LLM 响应 → TicketCard（同一参数卡出口）：白名单字段 + 逐字回验 + 时间校验。"""
    warnings: List[str] = []
    data = _extract_json(content)

    ticket_type = data.get("ticket_type")
    if ticket_type not in TICKET_TYPE_CODES:
        raise LLMUnavailable(f"LLM 返回票种无法识别: {ticket_type!r}")
    card = TicketCard(ticket_type=ticket_type)

    raw_fields = data.get("fields")
    if raw_fields is not None and not isinstance(raw_fields, dict):
        raise LLMUnavailable("LLM 响应 fields 不是对象")
    for key, item in (raw_fields or {}).items():
        if key not in KNOWN_FIELD_KEYS:
            warnings.append(f"LLM 兜底返回未知字段已忽略: {key}")
            continue
        value = item.get("value") if isinstance(item, dict) else item
        if value is None or not str(value).strip():
            continue
        value = str(value).strip()
        if key in TIME_FIELDS and not ISO_TIME_RE.match(value):
            warnings.append(f"LLM 兜底字段时间格式非法已丢弃: {key}={value!r}")
            continue
        quote = _verified_quote(source_text, item.get("evidence_quote") if isinstance(item, dict) else None)
        if quote is None:
            warnings.append(f"LLM 兜底字段摘录未逐字回验，已丢弃: {key}")
            continue
        card.fields[key] = FieldValue(
            value=value, confidence=LLM_CONFIDENCE, evidence=Evidence(region="llm", quote=quote)
        )

    raw_steps = data.get("operation_sequence")
    if raw_steps is not None and not isinstance(raw_steps, list):
        raise LLMUnavailable("LLM 响应 operation_sequence 不是数组")
    for item in raw_steps or []:
        if not isinstance(item, dict):
            continue
        action = str(item.get("action") or "").strip()
        quote = _verified_quote(source_text, item.get("evidence_quote"))
        if not action or quote is None:
            warnings.append(f"LLM 兜底操作项缺少内容或摘录未逐字回验，已丢弃: {item.get('no')!r}")
            continue
        card.operation_sequence.append(
            OperationStep(
                no=_step_no(item, len(card.operation_sequence) + 1, warnings, "operation_sequence"),
                action=action,
                evidence=Evidence(region="llm", quote=quote),
            )
        )

    raw_measures = data.get("safety_measures")
    if raw_measures is not None and not isinstance(raw_measures, list):
        raise LLMUnavailable("LLM 响应 safety_measures 不是数组")
    for item in raw_measures or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        quote = _verified_quote(source_text, item.get("evidence_quote"))
        if not text or quote is None:
            warnings.append("LLM 兜底措施条目缺少内容或摘录未逐字回验，已丢弃")
            continue
        card.safety_measures.append(
            SafetyMeasure(
                no=_step_no(item, len(card.safety_measures) + 1, warnings, "safety_measures"),
                text=text,
                evidence=Evidence(region="llm", quote=quote),
            )
        )

    card.warnings.extend(warnings)
    card.warnings.append("参数卡由 LLM 兜底抽取（规则解析不可用），字段置信度以卡内 confidence 为准")
    return card


def extract_via_llm(text: str, chat_fn: Callable = None) -> TicketCard:
    """LLM 兜底抽取唯一入口：归一化 → LLM → 逐字回验 → TicketCard。

    不可用（依赖/密钥/网络/坏响应）抛 LLMUnavailable；chat_fn 供测试注入假客户端。
    """
    source = normalize_text(text)
    chat = chat_fn or default_chat
    content = chat(build_messages(source))
    return card_from_llm_response(content, source)


def parse_ticket_with_fallback(
    text: str, allow_llm: bool = False, extract_fn: Callable[[str], TicketCard] = None
) -> TicketCard:
    """规则优先解析 + 可选 LLM 兜底（M4；默认关闭，core 通路零 API 依赖）。

    - 规则解析成功且无低置信度字段 → 原样返回（与 parse_ticket 完全一致）；
    - 解析失败且 allow_llm → LLM 兜底；LLM 不可用 → 抛 ParseError（附降级说明），
      即纯规则通路行为保持不变（断供降级测试锁定）；
    - 解析成功但存在低置信度字段（confidence < 0.6）且 allow_llm → LLM 补抽：
      只补缺/替换低置信度字段与空列表块，高置信度字段不动；LLM 不可用 → 原卡返回 + 留痕。
    缺失字段不兜底：字段缺失是合规信号（required_field），兜底填充会掩盖缺陷。
    """
    try:
        card = parse_ticket(text)
    except ParseError as exc:
        if not allow_llm:
            raise
        extract = extract_fn or extract_via_llm
        try:
            return extract(text)
        except LLMUnavailable as unavailable:
            raise ParseError(
                f"{exc}；LLM 兜底不可用，已降级纯规则通路（{unavailable.reason}）"
            ) from unavailable

    low = sorted(k for k, fv in card.fields.items() if fv.confidence < LOW_CONFIDENCE_THRESHOLD)
    if not (low and allow_llm):
        return card
    extract = extract_fn or extract_via_llm
    try:
        llm_card = extract(text)
    except LLMUnavailable as unavailable:
        card.warnings.append(
            f"LLM 兜底不可用，低置信度字段维持现状: {'、'.join(low)}（{unavailable.reason}）"
        )
        return card
    filled = []
    for key, fv in llm_card.fields.items():
        if key not in card.fields or card.fields[key].confidence < LOW_CONFIDENCE_THRESHOLD:
            card.fields[key] = fv
            filled.append(key)
    if not card.operation_sequence and llm_card.operation_sequence:
        card.operation_sequence = llm_card.operation_sequence
        filled.append("operation_sequence")
    if not card.safety_measures and llm_card.safety_measures:
        card.safety_measures = llm_card.safety_measures
        filled.append("safety_measures")
    card.warnings.append(f"LLM 兜底补抽: {'、'.join(filled) if filled else '无可补字段'}")
    return card
