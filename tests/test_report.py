"""报告导出测试（M5）：章节结构、docx 渲染、无外链断言（plan/04 §5 / HANDOFF-M5 待办 2）。"""
import sys
import zipfile

import pytest

from powerticket.pipeline import run_pipeline
from powerticket.report import ReportUnavailable, find_external_links
from powerticket.report.docx_render import (
    ensure_docx_available,
    render_document,
    render_docx_report,
    render_docx_report_bytes,
)
from powerticket.report.sections import build_report_sections, overall_verdict

from test_cli import ROOT, SAMPLE

DEFECT = ROOT / "data" / "samples" / "gen" / "gen-operating-005-five-prevention.txt"
MANUAL = ROOT / "data" / "samples" / "gen" / "gen-operating-002-missing-start-time.txt"


def _sections_of(path, meta=None):
    return build_report_sections(run_pipeline(path.read_text(encoding="utf-8")), meta)


def test_overall_verdict_three_levels():
    assert overall_verdict({"合规": 4, "不合规": 0, "待人工确认": 0}) == "合规"
    assert overall_verdict({"合规": 2, "不合规": 1, "待人工确认": 0}) == "不合规（需整改）"
    assert overall_verdict({"合规": 2, "不合规": 0, "待人工确认": 1}) == "待人工确认"


def test_sections_structure_compliant():
    sections = _sections_of(SAMPLE)
    kinds = [s["kind"] for s in sections]
    assert kinds[0] == "title"
    headings = [s["text"] for s in sections if s["kind"] == "heading" and s["level"] == 1]
    assert headings == [
        "一、结论汇总",
        "二、分级问题清单（按风险等级）",
        "三、逐条证据（含原文摘录）",
        "四、整改建议",
        "五、待人工确认",
        "六、签署栏",
    ]
    assert "本票未发现不合规项。" in [s["text"] for s in sections if s["kind"] == "paragraph"]
    assert sections[-1]["kind"] == "paragraph"  # 签署栏说明收尾


def test_sections_violation_graded_list_and_evidence():
    sections = _sections_of(DEFECT)
    problem_tables = [s for s in sections if s["kind"] == "table" and s["header"][0] == "风险等级"]
    assert problem_tables, "缺分级问题清单表"
    row = problem_tables[0]["rows"][0]
    assert row[0] == "重大" and row[1] == "R-OP-003"
    # 逐条证据：违规项 heading2 + 证据原文逐字
    h2 = [s["text"] for s in sections if s["kind"] == "heading" and s["level"] == 2]
    assert any("R-OP-003" in t for t in h2)
    bullets = [i for s in sections if s["kind"] == "bullets" for i in s["items"]]
    assert any("拉开隔离开关前未见断开断路器操作" in b for b in bullets)
    # 原文摘录来自参数卡证据链（逐字）
    excerpt_tables = [s for s in sections if s["kind"] == "table" and s["header"] == ["字段", "提取值", "原文摘录"]]
    assert excerpt_tables and any("编号：CZ-2026-0005" in r[2] for r in excerpt_tables[0]["rows"])
    # 整改建议含违规规则
    suggestion_bullets = [i for i in bullets if i.startswith("[R-OP-003]")]
    assert suggestion_bullets


def test_sections_manual_independent_section():
    """含待人工确认的样例：第五节独立成节，且解析告警一并列入。"""
    sections = _sections_of(MANUAL)
    idx_manual = next(i for i, s in enumerate(sections) if s.get("text") == "五、待人工确认")
    idx_sign = next(i for i, s in enumerate(sections) if s.get("text") == "六、签署栏")
    assert idx_manual < idx_sign
    h2 = [s["text"] for s in sections[idx_manual:idx_sign] if s["kind"] == "heading" and s["level"] == 2]
    assert any("R-OP-002" in t for t in h2)


def test_sections_meta_rows():
    sections = _sections_of(SAMPLE, meta={"source_file": "sample.txt", "generated_at": "2026-10-02T12:00:00", "version": "0.1.0"})
    meta = next(s for s in sections if s["kind"] == "meta_table")
    rows = {r[0]: r[1] for r in meta["rows"]}
    assert rows["票据类型"] == "变电站倒闸操作票"
    assert rows["来源文件"] == "sample.txt"
    assert rows["审核时间"] == "2026-10-02T12:00:00"


def test_render_docx_no_external_links():
    """报告无外链断言：违规样例报告（含规范原文/摘录）三种判据全零命中。"""
    data = render_docx_report_bytes(run_pipeline(DEFECT.read_text(encoding="utf-8")))
    assert data[:2] == b"PK"
    assert find_external_links(data) == []


def test_render_docx_content_complete():
    doc = render_document(run_pipeline(DEFECT.read_text(encoding="utf-8")))
    texts = [p.text for p in doc.paragraphs]
    assert "电力两票智能审核报告" in texts
    assert "六、签署栏" in texts
    joined = "\n".join(texts)
    assert "R-OP-003" in joined
    assert "严禁带电挂（合）接地线" in joined  # 规范原文（basis.quote）入报告
    assert len(doc.tables) >= 5


def test_render_docx_report_file(tmp_path):
    out = tmp_path / "nested" / "report.docx"
    result = run_pipeline(SAMPLE.read_text(encoding="utf-8"))
    path = render_docx_report(result, out)
    assert path.exists() and path.stat().st_size > 0
    assert find_external_links(path.read_bytes()) == []


def test_report_unavailable_when_docx_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "docx", None)
    with pytest.raises(ReportUnavailable):
        ensure_docx_available()
    with pytest.raises(ReportUnavailable):
        render_document(run_pipeline(SAMPLE.read_text(encoding="utf-8")))


def test_find_external_links_detects_synthetic():
    """判据自证：合成含 URL 的伪 docx 必须被检出（防止判据恒真）。"""
    import io

    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as zf:
        zf.writestr(
            "word/document.xml",
            "<w:document><w:body><w:p><w:r><w:t>see http://evil.example.com now</w:t></w:r></w:p></w:body></w:document>",
        )
        zf.writestr(
            "word/_rels/document.xml.rels",
            '<Relationships><Relationship Id="r1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="http://evil.example.com" TargetMode="External"/></Relationships>',
        )
    hits = find_external_links(bio.getvalue())
    assert len(hits) == 2  # 正文 URL + External 关系（rels 的 Type 命名空间 URI 不计）
