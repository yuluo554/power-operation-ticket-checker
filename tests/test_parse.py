from pathlib import Path

import pytest

from powerticket.parse import ParseError, parse_ticket

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "samples" / "sample-operating-01.txt"


def test_parse_sample_operating():
    card = parse_ticket(SAMPLE.read_text(encoding="utf-8"))
    assert card.ticket_type == "operating"
    assert card.fields["ticket_no"].value == "CZ-2026-0001"
    assert card.fields["start_time"].value == "2026-10-15T08:30"
    assert card.fields["end_time"].value == "2026-10-15T09:40"
    assert card.fields["guardian"].value == "张测试（虚构）"
    assert len(card.operation_sequence) == 5
    assert card.operation_sequence[0].action.startswith("检查")
    # 每个字段必须带证据（区域+原文摘录）
    for fv in card.fields.values():
        assert fv.evidence is not None
        assert fv.evidence.quote
    assert not card.warnings


def test_parse_rejects_empty():
    with pytest.raises(ParseError):
        parse_ticket("   \n  ")


def test_parse_rejects_unknown_type():
    with pytest.raises(ParseError) as ei:
        parse_ticket("这是一段无关文本，没有任何票样关键词。")
    assert "无法识别票种" in str(ei.value)


def test_parse_rejects_unimplemented_type():
    with pytest.raises(ParseError) as ei:
        parse_ticket("变电站（发电厂）第一种工作票 编号：GZ-2026-0001")
    assert "未实现" in str(ei.value)


def test_parse_drops_illegal_time():
    text = SAMPLE.read_text(encoding="utf-8").replace(
        "2026年10月15日 08:30", "时间待定"
    )
    card = parse_ticket(text)
    assert "start_time" not in card.fields
    assert any("start_time" in w for w in card.warnings)


def test_detect_routes_ticket_types():
    from powerticket.parse import detect_ticket_type

    assert detect_ticket_type("电力线路倒闸操作票 编号：X-1") == "line_operating"
    assert detect_ticket_type("事故紧急抢修单") == "emergency_repair"
    assert detect_ticket_type("没有关键词") is None
