"""Web 面板测试（M5）：页面 0 外链断言、真实上传冒烟、中文 JSON 路径、报告预览/导出同源、CLI 接线。"""
import sys

import pytest

from powerticket import cli
from powerticket.report import find_external_links
from powerticket.report.sections import build_report_sections
from powerticket.pipeline import run_pipeline

from test_cli import ROOT, SAMPLE

pytest.importorskip("fastapi", reason="extras[web] 未安装")
pytest.importorskip("httpx", reason="TestClient 需要 httpx")

from fastapi.testclient import TestClient  # noqa: E402

from powerticket.web.app import STATIC_DIR, create_app  # noqa: E402

DEFECT = ROOT / "data" / "samples" / "gen" / "gen-operating-005-five-prevention.txt"


@pytest.fixture()
def client():
    return TestClient(create_app())


def _upload(path, name=None):
    data = path.read_bytes()
    return {"file": (name or path.name, data, "text/plain")}, data


def test_index_page_zero_external_links(client):
    """页面 0 外链断言：无绝对 URL、无外部 <link>/<script src>。"""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    assert "电力两票智能审核面板" in html
    for marker in ("http://", "https://", "<link", "src=\"http", "url(http", "@import"):
        assert marker not in html, marker


def test_static_file_zero_external_links():
    html = STATIC_DIR.joinpath("index.html").read_text(encoding="utf-8")
    assert "http://" not in html and "https://" not in html
    assert "<link" not in html


def test_docs_disabled(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404


def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_check_real_upload_chinese_json(client):
    """Web 冒烟：真实 multipart 上传 + 中文 JSON 原样输出（无 \\u 转义）。"""
    files, _ = _upload(DEFECT, name="操作票-005.txt")
    resp = client.post("/api/check", files=files)
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["filename"] == "操作票-005.txt"
    assert payload["card"]["ticket_type_name"] == "变电站倒闸操作票"
    assert payload["summary"]["不合规"] == 1
    # 中文 JSON 路径：响应体含原样中文（starlette ensure_ascii=False），票种名与文件名均中文
    assert "变电站倒闸操作票" in resp.text
    assert "操作票-005.txt" in resp.text


def test_check_unparseable_returns_422(client):
    files, _ = _upload(SAMPLE, name="bad.txt")
    files["file"] = ("bad.txt", "无关文本".encode("utf-8"), "text/plain")
    resp = client.post("/api/check", files=files)
    assert resp.status_code == 422
    assert "解析失败" in resp.json()["error"]


def test_report_preview_same_sections_as_docx(client):
    """报告预览与 docx 导出共用同一章节结构（预览即所得）。"""
    files, _ = _upload(DEFECT)
    resp = client.post("/api/report-preview", files=files)
    assert resp.status_code == 200
    result = run_pipeline(DEFECT.read_text(encoding="utf-8"))
    expected = build_report_sections(result)  # 章节数与 meta 无关，结构必须同源
    kinds = [s["kind"] for s in resp.json()["sections"]]
    assert kinds[0] == "title" and kinds.count("heading") >= 6
    # 与本地构建的章节数一致（meta 内容可因时间戳不同，结构必须同源）
    assert len(kinds) == len(expected)
    texts = [s.get("text") for s in resp.json()["sections"] if s["kind"] == "heading"]
    assert "六、签署栏" in texts


def test_report_download_docx_no_external_links(client):
    files, _ = _upload(DEFECT)
    resp = client.post("/api/report", files=files)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert resp.content[:2] == b"PK"
    assert find_external_links(resp.content) == []


def test_cli_web_wiring(monkeypatch, capsys):
    """CLI web 接线：以指定 host/port 启动 uvicorn（打桩，不真起服务）。"""
    import uvicorn

    calls = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: calls.update(kw, app=app))
    rc = cli.main(["web", "--host", "127.0.0.1", "--port", "8123"])
    out = capsys.readouterr().out
    assert rc == 0
    assert calls["port"] == 8123 and calls["host"] == "127.0.0.1"
    assert calls["app"] is not None
    assert "Web 面板启动" in out


def test_cli_web_missing_deps(monkeypatch, capsys):
    """extras[web] 缺失 → 友好提示退出码 2，不抛裸 traceback。"""
    monkeypatch.delitem(sys.modules, "powerticket.web.app", raising=False)
    monkeypatch.setitem(sys.modules, "fastapi", None)
    rc = cli.main(["web"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "Web 面板不可用" in captured.err
    assert "pip install -e .[web]" in captured.err
