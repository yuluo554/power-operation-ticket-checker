from pathlib import Path

import pytest

from powerticket.parse import ParseError, detect_ticket_type, parse_ticket

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "samples" / "sample-operating-01.txt"
GEN = ROOT / "data" / "samples" / "gen"

# 7 票种标题（与 data/ticket_templates/*.txt 首行一致）
TITLES = {
    "operating": "变电站倒闸操作票",
    "line_operating": "电力线路倒闸操作票",
    "work_first": "变电站（发电厂）第一种工作票",
    "work_second": "变电站（发电厂）第二种工作票",
    "line_work_first": "电力线路第一种工作票",
    "line_work_second": "电力线路第二种工作票",
    "emergency_repair": "事故紧急抢修单",
}


def _gen(stem: str) -> str:
    return (GEN / f"{stem}.txt").read_text(encoding="utf-8")


def test_parse_sample_operating():
    card = parse_ticket(SAMPLE.read_text(encoding="utf-8"))
    assert card.ticket_type == "operating"
    assert card.fields["ticket_no"].value == "CZ-2026-0001"
    assert card.fields["start_time"].value == "2026-10-15T08:30"
    assert card.fields["end_time"].value == "2026-10-15T09:40"
    assert card.fields["dispatcher"].value == "王模拟（虚构）"
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


def test_parse_drops_illegal_time():
    text = SAMPLE.read_text(encoding="utf-8").replace(
        "2026年10月15日 08:30", "时间待定"
    )
    card = parse_ticket(text)
    assert "start_time" not in card.fields
    assert any("start_time" in w for w in card.warnings)


# ---------------------------------------------------------------------------
# 票种路由（M2：7 票种全覆盖 + 顺序门控负例）
# ---------------------------------------------------------------------------

def test_route_all_seven_titles():
    for code, title in TITLES.items():
        assert detect_ticket_type(title) == code, title


def test_route_line_keywords_precede_generic():
    # 顺序门控负例：线路票标题含通用关键词子串，不得误路由为变电站票
    assert detect_ticket_type("电力线路倒闸操作票 编号：XZ-2026-0001") != "operating"
    assert detect_ticket_type("电力线路第一种工作票 编号：XL1-2026-0001") != "work_first"
    assert detect_ticket_type("电力线路第二种工作票 编号：XL2-2026-0001") != "work_second"


def test_route_full_samples_cross_type_no_mismatch():
    # 交叉文本不误配：7 票种完整票样（标题+正文）各路由正确
    normal_stems = {
        "operating": "gen-operating-001-normal",
        "line_operating": "gen-line_operating-008-normal",
        "work_first": "gen-work_first-013-normal",
        "work_second": "gen-work_second-020-normal",
        "line_work_first": "gen-line_work_first-024-normal",
        "line_work_second": "gen-line_work_second-029-normal",
        "emergency_repair": "gen-emergency_repair-032-normal",
    }
    for code, stem in normal_stems.items():
        assert detect_ticket_type(_gen(stem)) == code, stem


# ---------------------------------------------------------------------------
# 各票种解析（M2：除 operating 外的代表样例抽检；35 份全集对账见 test_data_generator.py）
# ---------------------------------------------------------------------------

def test_parse_work_first_dual_time_and_measures():
    card = parse_ticket(_gen("gen-work_first-013-normal"))
    assert card.ticket_type == "work_first"
    f = card.fields
    # 双时间行：『计划工作时间：自…至…』一行拆 plan_start/plan_end，ISO 入卡
    assert f["plan_start"].value == "2026-10-25T08:00"
    assert f["plan_end"].value == "2026-10-25T17:00"
    assert f["permit_start"].value == "2026-10-25T08:10"
    assert f["end_time"].value == "2026-10-25T16:50"
    assert f["issuer"].value == "张测试"
    assert f["permitor"].value == "王模拟"
    assert f["crew"].value == "李演示、周样例、孙占位"
    # 安全措施条目独立容器（M2 定稿）
    assert [m.no for m in card.safety_measures] == [1, 2, 3, 4]
    assert card.safety_measures[0].text.startswith("断开35kV南岭线312断路器")
    assert not card.operation_sequence  # 工作票无操作序列
    assert not card.warnings
    for fv in f.values():
        assert fv.evidence is not None and fv.evidence.quote
    for m in card.safety_measures:
        assert m.evidence is not None and m.evidence.quote


def test_parse_line_work_second_location_label():
    card = parse_ticket(_gen("gen-line_work_second-029-normal"))
    assert card.ticket_type == "line_work_second"
    # 线路版工作地点栏：『线路名称及杆号（双重名称）』
    assert "杆区段" in card.fields["location"].value
    assert len(card.safety_measures) == 3
    assert not card.warnings


def test_parse_emergency_repair_sample():
    card = parse_ticket(_gen("gen-emergency_repair-032-normal"))
    assert card.ticket_type == "emergency_repair"
    # 抢修单专用标签：抢修任务/抢修开始结束时间/许可人（值班负责人）
    assert card.fields["task"].value.startswith("处理10kV城区线815断路器")
    assert card.fields["start_time"].value == "2026-10-14T14:00"
    assert card.fields["end_time"].value == "2026-10-14T17:30"
    assert card.fields["permitor"].value
    assert len(card.safety_measures) == 3
    assert not card.warnings


def test_parse_line_operating_sample():
    card = parse_ticket(_gen("gen-line_operating-008-normal"))
    assert card.ticket_type == "line_operating"
    assert card.fields["dispatcher"].value
    assert len(card.operation_sequence) == 5
    assert not card.warnings


def test_parse_missing_plan_end_half_line_kept():
    # 缺失注入只清空『至』端：plan_end 缺失告警，同行的 plan_start 不受牵连
    card = parse_ticket(_gen("gen-work_first-015-missing-plan-end"))
    assert "plan_end" not in card.fields
    assert any("plan_end" in w for w in card.warnings)
    assert "plan_start" in card.fields


def test_parse_drops_illegal_plan_time():
    text = _gen("gen-work_first-013-normal").replace("2026年10月25日 08:00", "时间待定")
    card = parse_ticket(text)
    assert "plan_start" not in card.fields
    assert any("plan_start" in w for w in card.warnings)
    assert card.fields["plan_end"].value == "2026-10-25T17:00"


def test_parse_illegal_month_dropped():
    # 合法性校验含日历越界：13 月不是合法时刻，丢弃不留卡
    text = _gen("gen-operating-001-normal").replace("2026年10月13日 08:30", "2026年13月13日 08:30")
    card = parse_ticket(text)
    assert "start_time" not in card.fields
    assert any("start_time" in w for w in card.warnings)
