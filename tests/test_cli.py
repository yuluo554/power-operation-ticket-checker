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


def test_run_single_file_human_output(capsys):
    rc = cli.main(["run", str(SAMPLE)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "票面参数卡" in out
    assert "== 汇总 ==" in out


def test_run_single_file_json(capsys):
    rc = cli.main(["run", str(SAMPLE), "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    result = json.loads(out)  # --json 输出必须是纯净 JSON
    assert result["card"]["ticket_type"] == "operating"
    assert result["summary"] == {"合规": 4, "不合规": 0, "待人工确认": 0}


def test_run_single_with_report(capsys, tmp_path):
    out_docx = tmp_path / "report.docx"
    rc = cli.main(["run", str(SAMPLE), "--json", "--report", str(out_docx)])
    captured = capsys.readouterr()
    assert rc == 0
    json.loads(captured.out)  # JSON 纯净：报告路径提示走 stderr
    assert "报告已生成" in captured.err
    assert out_docx.exists() and out_docx.read_bytes()[:2] == b"PK"


def test_run_missing_path(capsys):
    rc = cli.main(["run", "no_such_dir_or_file"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "路径不存在" in captured.err


def test_run_directory_batch(capsys, tmp_path):
    """目录批量：2 正常 + 1 缺陷全处理；失败 0 → 退出码 0。"""
    import shutil

    for name in (
        "gen-operating-001-normal.txt",
        "gen-operating-004-time-order.txt",
        "gen-work_first-013-normal.txt",
    ):
        shutil.copy(ROOT / "data" / "samples" / "gen" / name, tmp_path / name)
    rc = cli.main(["run", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "共 3 份" in out
    assert "[通过] gen-operating-001-normal.txt" in out
    assert "[问题] gen-operating-004-time-order.txt" in out and "R-OP-002" in out
    assert "== 批量汇总 == 共 3 份 ｜ 全部合规 2 ｜ 存在问题 1 ｜ 处理失败 0" in out


def test_run_directory_batch_continues_on_error(capsys, tmp_path):
    """批量中个别票解析失败：继续处理其余票，退出码 1，失败行注明原因。"""
    import shutil

    shutil.copy(ROOT / "data" / "samples" / "gen" / "gen-operating-001-normal.txt", tmp_path / "good.txt")
    (tmp_path / "garbage.txt").write_text("无关文本", encoding="utf-8")
    rc = cli.main(["run", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "[失败] garbage.txt" in out and "无法识别票种" in out
    assert "[通过] good.txt" in out
    assert "处理失败 1" in out


def test_run_directory_json(capsys, tmp_path):
    import shutil

    shutil.copy(ROOT / "data" / "samples" / "gen" / "gen-operating-001-normal.txt", tmp_path / "a.txt")
    shutil.copy(ROOT / "data" / "samples" / "gen" / "gen-operating-004-time-order.txt", tmp_path / "b.txt")
    rc = cli.main(["run", str(tmp_path), "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(out)
    assert payload["mode"] == "directory" and payload["aggregate"]["total"] == 2
    assert payload["aggregate"]["clean"] == 1 and payload["aggregate"]["with_findings"] == 1
    by_file = {r["file"]: r for r in payload["results"]}
    assert by_file["a.txt"]["status"] == "ok" and by_file["a.txt"]["card"]["ticket_type"] == "operating"
    assert by_file["b.txt"]["summary"]["不合规"] == 1


def test_run_directory_with_report_dir(capsys, tmp_path):
    """目录模式 --report：每票一份 docx 落到报告目录。"""
    import shutil

    for name in ("gen-operating-001-normal.txt", "gen-operating-004-time-order.txt"):
        shutil.copy(ROOT / "data" / "samples" / "gen" / name, tmp_path / name)
    reports = tmp_path / "reports"
    rc = cli.main(["run", str(tmp_path), "--report", str(reports)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "逐票报告目录" in out
    docx_files = sorted(p.name for p in reports.glob("*.docx"))
    assert docx_files == [
        "gen-operating-001-normal.docx",
        "gen-operating-004-time-order.docx",
    ]


def test_report_cmd_default_out_path(capsys, tmp_path):
    src = tmp_path / "myticket.txt"
    src.write_text(SAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    rc = cli.main(["report", str(src)])
    out = capsys.readouterr().out
    assert rc == 0
    expected = src.parent / "myticket-审核报告.docx"
    assert str(expected) in out
    assert expected.exists()


def test_report_cmd_unparseable_friendly(capsys, tmp_path):
    bad = tmp_path / "bad.txt"
    bad.write_text("无关文本", encoding="utf-8")
    rc = cli.main(["report", str(bad)])
    captured = capsys.readouterr()
    assert rc == 2
    assert "校核失败" in captured.err


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
