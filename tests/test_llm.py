"""M4 LLM 兜底守门（全离线，零网络）：断供降级 / 摘录逐字回验 / 同一 TicketCard 出口。

锁定口径：
- 默认（不开启兜底）行为与纯规则通路完全一致，零 API 依赖；
- LLM 不可用（依赖未装/无密钥/网络断/坏响应）→ 降级纯规则通路，留痕不炸；
- LLM 字段必须携带原文逐字摘录，否则不入卡（防幻觉）。
"""
from __future__ import annotations

import json
import pathlib
import sys
from types import SimpleNamespace

import pytest

import powerticket.llm.client as client_mod
import powerticket.llm.fallback as fallback_mod
from powerticket.llm import LLMUnavailable
from powerticket.llm.client import chat, load_dotenv
from powerticket.llm.fallback import (
    card_from_llm_response,
    extract_via_llm,
    parse_ticket_with_fallback,
)
from powerticket.models import Evidence, FieldValue, TicketCard
from powerticket.parse import ParseError, parse_ticket
from powerticket.parse.cleaning import normalize_text

SAMPLE_TEXT = (
    pathlib.Path(__file__).parents[1] / "data" / "samples" / "gen" / "gen-operating-001-normal.txt"
).read_text(encoding="utf-8")
NORMALIZED = normalize_text(SAMPLE_TEXT)


def _norm_line(prefix: str) -> str:
    """归一化后原文中取整行（作为逐字摘录，保证回验通过）。"""
    for line in NORMALIZED.split("\n"):
        if line.strip().startswith(prefix):
            return line.strip()
    raise AssertionError(f"样例中找不到行前缀: {prefix}")


def _canned_response(fabricated_quote: bool = False) -> str:
    ticket_no_quote = _norm_line("编号：")
    task_quote = _norm_line("操作任务：")
    start_quote = _norm_line("操作开始时间：")
    step_quote = _norm_line("1 ")
    if fabricated_quote:
        ticket_no_quote = "这句摘录不在原文里"
    return json.dumps(
        {
            "ticket_type": "operating",
            "fields": {
                "ticket_no": {"value": "CZ-2026-0001", "evidence_quote": ticket_no_quote},
                "task": {
                    "value": "将35kV南岭线312断路器由运行转为检修",
                    "evidence_quote": task_quote,
                },
                "start_time": {"value": "2026-10-13T08:30", "evidence_quote": start_quote},
            },
            "operation_sequence": [
                {"no": 1, "action": "检查35kV南岭线312断路器确在合闸位置", "evidence_quote": step_quote}
            ],
            "safety_measures": [],
        },
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# client.chat：密钥 / 依赖 / 响应（全离线）
# ---------------------------------------------------------------------------

def test_chat_requires_api_key(monkeypatch):
    monkeypatch.setattr(client_mod, "resolve_api_key", lambda *a, **k: None)
    with pytest.raises(LLMUnavailable) as ei:
        chat([{"role": "user", "content": "hi"}])
    assert "DASHSCOPE_API_KEY" in str(ei.value)


def test_chat_without_openai_dependency(monkeypatch):
    monkeypatch.setattr(client_mod, "resolve_api_key", lambda *a, **k: "test-key")
    monkeypatch.setitem(sys.modules, "openai", None)  # import openai → ImportError
    with pytest.raises(LLMUnavailable) as ei:
        chat([{"role": "user", "content": "hi"}])
    assert "依赖未安装" in str(ei.value)


def _fake_client(content: str = "ok", recorder: dict = None):
    """结构仿 openai 客户端的假件，记录 create kwargs 供断言。"""
    completions = SimpleNamespace()

    def create(**kwargs):
        if recorder is not None:
            recorder.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    completions.create = create
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


def test_chat_uses_dashscope_defaults_and_enable_thinking_false(monkeypatch):
    recorder: dict = {}
    resp = chat(
        [{"role": "user", "content": "hi"}],
        api_key="test-key",
        client=_fake_client(content="回答", recorder=recorder),
    )
    assert resp == "回答"
    assert recorder["model"] == "qwen-plus"
    assert recorder["extra_body"] == {"enable_thinking": False}


def test_chat_reports_structural_and_empty_response_failures():
    # create 返回空 choices → 结构异常
    broken = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: SimpleNamespace(choices=[])))
    )
    with pytest.raises(LLMUnavailable) as ei:
        chat([{"role": "user", "content": "hi"}], api_key="k", client=broken)
    assert "响应结构异常" in str(ei.value)

    empty = _fake_client(content="  ")
    with pytest.raises(LLMUnavailable) as ei:
        chat([{"role": "user", "content": "hi"}], api_key="k", client=empty)
    assert "空内容" in str(ei.value)


def test_load_dotenv_parses_and_respects_existing(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        '# 注释\nDASHSCOPE_API_KEY="sk-test-123"  # 行内注释\nEMPTY=\nBAD LINE\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    loaded = load_dotenv(env_file, override=True)
    assert loaded["DASHSCOPE_API_KEY"] == "sk-test-123"
    import os

    assert os.environ["DASHSCOPE_API_KEY"] == "sk-test-123"
    # 不覆盖已有环境变量（override=False 默认）
    loaded2 = load_dotenv(env_file)  # 已在环境里，值保持
    assert loaded2["DASHSCOPE_API_KEY"] == "sk-test-123"
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)


# ---------------------------------------------------------------------------
# 兜底抽取：响应 → TicketCard（白名单 + 逐字回验 + 时间校验）
# ---------------------------------------------------------------------------

def test_extract_via_llm_builds_ticket_card():
    captured = {}

    def fake_chat(messages):
        captured["messages"] = messages
        return _canned_response()

    card = extract_via_llm(SAMPLE_TEXT, chat_fn=fake_chat)
    assert card.ticket_type == "operating"
    assert card.fields["ticket_no"].value == "CZ-2026-0001"
    assert card.fields["start_time"].value == "2026-10-13T08:30"  # ISO 口径
    assert card.fields["ticket_no"].confidence < 1.0  # LLM 置信度低于规则解析
    assert card.fields["ticket_no"].evidence.quote in NORMALIZED  # 逐字摘录
    assert [s.no for s in card.operation_sequence] == [1]
    assert any("兜底抽取" in w for w in card.warnings)  # 出口留痕
    # 提示词含 schema 与归一化原文
    assert "evidence_quote" in captured["messages"][0]["content"]
    assert "编号：CZ-2026-0001" in captured["messages"][1]["content"]


def test_fabricated_quote_drops_field():
    card = card_from_llm_response(_canned_response(fabricated_quote=True), NORMALIZED)
    assert "ticket_no" not in card.fields  # 摘录未逐字回验 → 不入卡
    assert "task" in card.fields
    assert any("逐字回验" in w and "ticket_no" in w for w in card.warnings)


def test_bad_field_and_time_inputs_dropped_with_trace():
    bad = json.dumps(
        {
            "ticket_type": "operating",
            "fields": {
                "not_a_field": {"value": "x", "evidence_quote": "x"},
                "start_time": {"value": "2026年10月13日 08:30", "evidence_quote": _norm_line("操作开始时间：")},
                "task": {"value": "", "evidence_quote": _norm_line("操作任务：")},
            },
        },
        ensure_ascii=False,
    )
    card = card_from_llm_response(bad, NORMALIZED)
    assert not card.fields  # 未知字段丢弃 / 时间格式非法丢弃 / 空值不入
    assert any("未知字段" in w for w in card.warnings)
    assert any("时间格式非法" in w for w in card.warnings)


def test_code_fenced_and_garbage_responses():
    card = card_from_llm_response(f"```json\n{_canned_response()}\n```", NORMALIZED)
    assert card.ticket_type == "operating"
    with pytest.raises(LLMUnavailable):
        card_from_llm_response("抱歉，我无法完成该任务。", NORMALIZED)
    with pytest.raises(LLMUnavailable):
        card_from_llm_response('{"ticket_type": "unknown_type", "fields": {}}', NORMALIZED)


# ---------------------------------------------------------------------------
# parse_ticket_with_fallback：断供降级（M4 锁定项）
# ---------------------------------------------------------------------------

def _boom_extract(text):
    raise LLMUnavailable("未配置 DASHSCOPE_API_KEY")


def test_fallback_off_by_default_never_calls_llm():
    calls = []

    def spy(text):
        calls.append(text)
        raise AssertionError("不应调用 LLM")

    # 规则可解析样例：默认关兜底 → 与 parse_ticket 完全一致
    card = parse_ticket_with_fallback(SAMPLE_TEXT, allow_llm=False, extract_fn=spy)
    assert card.ticket_type == "operating"
    assert not calls
    # 规则不可解析：默认关兜底 → 原样 ParseError
    with pytest.raises(ParseError):
        parse_ticket_with_fallback("无关文本", allow_llm=False, extract_fn=spy)
    assert not calls


def test_parseable_sample_degrades_to_rule_path_when_llm_down():
    """断供降级锁定：LLM 不可用时纯规则通路照常出卡出结论。"""
    card = parse_ticket_with_fallback(SAMPLE_TEXT, allow_llm=True, extract_fn=_boom_extract)
    rule_card = parse_ticket(SAMPLE_TEXT)
    assert card.ticket_type == rule_card.ticket_type
    assert set(card.fields) == set(rule_card.fields)
    assert not card.warnings  # 可解析样例兜底全程未被触发
    # 同一出口可进规则引擎出结论
    from powerticket.rules import load_rules, run_checks

    conclusions = run_checks(card, load_rules())
    assert conclusions, "规则通路应照常出结论"


def test_unparseable_text_degrades_to_parse_error_when_llm_down():
    with pytest.raises(ParseError) as ei:
        parse_ticket_with_fallback("无关文本", allow_llm=True, extract_fn=_boom_extract)
    assert "降级" in str(ei.value)


def test_unparseable_text_uses_llm_card_when_available():
    llm_card = TicketCard(
        ticket_type="line_operating",
        fields={
            "ticket_no": FieldValue(
                value="XL-9", confidence=0.7, evidence=Evidence(region="llm", quote="编号：XL-9")
            )
        },
        warnings=["参数卡由 LLM 兜底抽取（规则解析不可用），字段置信度以卡内 confidence 为准"],
    )

    def fake_extract(text):
        assert text == "某线路倒闸工作凭证\n编号：XL-9\n任务：检修"
        return llm_card

    card = parse_ticket_with_fallback(
        "某线路倒闸工作凭证\n编号：XL-9\n任务：检修", allow_llm=True, extract_fn=fake_extract
    )
    assert card is llm_card
    assert card.fields["ticket_no"].value == "XL-9"


def test_low_confidence_fields_merged_from_llm(monkeypatch):
    """低置信度字段触发补抽：只补缺/替低置信度，高置信度不动。"""
    rule_card = TicketCard(
        ticket_type="operating",
        fields={
            "task": FieldValue(value="低置信任务", confidence=0.3, evidence=Evidence(region="body", quote="任务行")),
            "guardian": FieldValue(value="高置信监护人", confidence=1.0, evidence=Evidence(region="body", quote="监护人：高置信监护人")),
        },
    )
    monkeypatch.setattr(fallback_mod, "parse_ticket", lambda text: rule_card)

    llm_card = TicketCard(
        ticket_type="operating",
        fields={
            "task": FieldValue(value="LLM任务", confidence=0.7, evidence=Evidence(region="llm", quote="任务行")),
            "ticket_no": FieldValue(value="CZ-1", confidence=0.7, evidence=Evidence(region="llm", quote="编号：CZ-1")),
            "guardian": FieldValue(value="LLM监护人", confidence=0.7, evidence=Evidence(region="llm", quote="监护人：高置信监护人")),
        },
    )
    card = parse_ticket_with_fallback(
        SAMPLE_TEXT, allow_llm=True, extract_fn=lambda text: llm_card
    )
    assert card.fields["task"].value == "LLM任务"  # 低置信被替换
    assert card.fields["ticket_no"].value == "CZ-1"  # 缺失被补（非注入缺失场景）
    assert card.fields["guardian"].value == "高置信监护人"  # 高置信不动
    assert any("补抽" in w for w in card.warnings)


def test_low_confidence_fields_kept_when_llm_down(monkeypatch):
    rule_card = TicketCard(
        ticket_type="operating",
        fields={"task": FieldValue(value="低置信任务", confidence=0.3, evidence=Evidence(region="body", quote="任务行"))},
    )
    monkeypatch.setattr(fallback_mod, "parse_ticket", lambda text: rule_card)
    card = parse_ticket_with_fallback(SAMPLE_TEXT, allow_llm=True, extract_fn=_boom_extract)
    assert card.fields["task"].value == "低置信任务"  # 原值维持
    assert any("LLM 兜底不可用" in w for w in card.warnings)  # 留痕


def test_missing_fields_never_filled_by_llm(monkeypatch):
    """缺失字段不兜底（合规信号，required_field 判定）——补抽只针对卡内低置信字段。"""
    rule_card = TicketCard(ticket_type="operating")  # 无任何字段
    monkeypatch.setattr(fallback_mod, "parse_ticket", lambda text: rule_card)
    llm_card = TicketCard(
        ticket_type="operating",
        fields={"task": FieldValue(value="LLM任务", confidence=0.7)},
    )
    card = parse_ticket_with_fallback(SAMPLE_TEXT, allow_llm=True, extract_fn=lambda t: llm_card)
    assert "task" not in card.fields  # 不填充缺失字段
