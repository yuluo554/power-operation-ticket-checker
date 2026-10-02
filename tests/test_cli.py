import json
from pathlib import Path

from powerticket import cli

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "samples" / "sample-operating-01.txt"


def test_demo_runs(capsys):
    rc = cli.main(["demo"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "票面参数卡" in out
    assert "校核结论" in out
    assert "CZ-2026-0001" in out


def test_parse_outputs_card_json(capsys):
    rc = cli.main(["parse", str(SAMPLE)])
    out = capsys.readouterr().out
    assert rc == 0
    card = json.loads(out)
    assert card["ticket_type"] == "operating"
    assert card["ticket_type_name"] == "变电站倒闸操作票"
    assert card["fields"]["ticket_no"]["value"] == "CZ-2026-0001"


def test_check_outputs_result_json(capsys):
    rc = cli.main(["check", str(SAMPLE)])
    out = capsys.readouterr().out
    assert rc == 0
    result = json.loads(out)
    # M3 起 operating 有 4 条规则（required/time_order/five_prevention/consistency），样例全合规
    assert result["summary"] == {"合规": 4, "不合规": 0, "待人工确认": 0}
    for conclusion in result["conclusions"]:
        assert conclusion["basis"]["standard"]


def test_missing_file_friendly(capsys):
    rc = cli.main(["check", "no_such_file.txt"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "文件不存在" in captured.err


def test_parse_garbage_friendly(capsys):
    bad = ROOT / "output_garbage.tmp.txt"
    bad.write_text("无关文本", encoding="utf-8")
    try:
        rc = cli.main(["parse", str(bad)])
    finally:
        bad.unlink(missing_ok=True)
    captured = capsys.readouterr()
    assert rc == 2
    assert "无法识别票种" in captured.err


def test_stub_commands_exit_2(capsys):
    for cmd in (["run"], ["report", str(SAMPLE)], ["web"]):
        rc = cli.main(cmd)
        captured = capsys.readouterr()
        assert rc == 2, cmd
        assert "尚未实现" in captured.out


def test_benchmark_runs_and_passes_gates(capsys):
    rc = cli.main(["benchmark"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "[parse_f1]" in out and "[endtoend]" in out
    assert "F1 1.0" in out
    assert "误报率 0.0" in out
    assert "全部通过" in out


def test_benchmark_json_output(capsys):
    rc = cli.main(["benchmark", "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(out)
    assert payload["parse_f1"]["gate"]["pass"] is True
    assert payload["endtoend"]["gate"]["pass"] is True


def test_parse_llm_fallback_degrades_to_rule_path(monkeypatch, capsys):
    """--llm-fallback 在 LLM 断供（无密钥）时降级纯规则通路：可解析样例照常出卡。"""
    import powerticket.llm.client as client_mod

    monkeypatch.setattr(client_mod, "resolve_api_key", lambda *a, **k: None)
    rc = cli.main(["parse", str(SAMPLE), "--llm-fallback"])
    out = capsys.readouterr().out
    assert rc == 0
    card = json.loads(out)
    assert card["ticket_type"] == "operating"  # 纯规则通路结果


def test_check_llm_fallback_unparseable_degrades_with_trace(monkeypatch, capsys):
    """不可解析文本 + --llm-fallback 断供 → 友好报错并注明已降级。"""
    import powerticket.llm.client as client_mod

    monkeypatch.setattr(client_mod, "resolve_api_key", lambda *a, **k: None)
    bad = ROOT / "output_garbage.tmp.txt"
    bad.write_text("无关文本", encoding="utf-8")
    try:
        rc = cli.main(["check", str(bad), "--llm-fallback"])
    finally:
        bad.unlink(missing_ok=True)
    captured = capsys.readouterr()
    assert rc == 2
    assert "降级" in captured.err


def test_cli_help_lists_all_subcommands(capsys):
    import contextlib
    import io

    from powerticket.cli import build_parser

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            build_parser().parse_args(["-h"])
        except SystemExit as e:
            assert e.code == 0
    help_text = buf.getvalue()
    for cmd in ("demo", "parse", "check", "run", "report", "web", "benchmark"):
        assert cmd in help_text
