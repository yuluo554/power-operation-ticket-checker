"""FastAPI 应用（M5，plan/04 §5）：上传 → 参数卡 → 结论 → 报告预览/导出。

- 依赖仅 extras[web]（fastapi/uvicorn/python-multipart），由 CLI web 懒加载；
- core 通路零 API：/api/check 只走 run_pipeline（默认无 LLM 兜底）；
- 报告预览/导出复用 report 包：预览与 docx 同一章节结构（sections.py）；
- 前端为内联单页 static/index.html，零外部资源引用（页面 0 外链断言进测试），
  /docs、/redoc（Swagger UI 会引 CDN）显式关闭，保证断网可演示。
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response

# 说明：fastapi 在模块级导入——本模块本身即 extras[web] 边界（CLI web 懒加载它）；
# 且 future annotations 下端点签名的 "UploadFile" 前向引用必须在模块全局可解析，
# 放在 create_app() 局部会导致 pydantic ForwardRef 悬空（实测 PydanticUserError）。
from .. import __version__
from ..parse import ParseError
from ..pipeline import run_pipeline
from ..rules import RuleError

STATIC_DIR = Path(__file__).resolve().parent / "static"

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _report_meta(filename: str) -> dict:
    return {
        "source_file": filename,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "version": __version__,
    }


def create_app() -> FastAPI:
    app = FastAPI(
        title="电力两票智能审核面板",
        version=__version__,
        docs_url=None,  # Swagger UI 引 CDN，与 0 外链纪律冲突，显式关闭
        redoc_url=None,
    )

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok", "version": __version__}

    def _run_or_error(text: str):
        try:
            return run_pipeline(text), None
        except ParseError as e:
            return None, f"解析失败: {e}"
        except RuleError as e:
            return None, f"规则加载失败: {e}"

    @app.post("/api/check")
    async def api_check(file: UploadFile = File(...)):
        """真实上传 → run_pipeline → 参数卡+结论 JSON（中文原样输出，无 \\u 转义）。"""
        text = (await file.read()).decode("utf-8", errors="replace")
        result, error = _run_or_error(text)
        if error:
            return JSONResponse(status_code=422, content={"error": error})
        return {"filename": file.filename, **result}

    @app.post("/api/report-preview")
    async def api_report_preview(file: UploadFile = File(...)):
        """报告预览：与 docx 导出共用同一章节结构（预览即所得）。"""
        from ..report.sections import build_report_sections

        text = (await file.read()).decode("utf-8", errors="replace")
        result, error = _run_or_error(text)
        if error:
            return JSONResponse(status_code=422, content={"error": error})
        sections = build_report_sections(result, _report_meta(file.filename or ""))
        return {"filename": file.filename, "sections": sections}

    @app.post("/api/report")
    async def api_report(file: UploadFile = File(...)):
        """docx 报告下载（extras[report] 缺失 → 503 + 安装提示）。"""
        from ..report import ReportUnavailable
        from ..report.docx_render import render_docx_report_bytes

        text = (await file.read()).decode("utf-8", errors="replace")
        result, error = _run_or_error(text)
        if error:
            return JSONResponse(status_code=422, content={"error": error})
        try:
            data = render_docx_report_bytes(result, _report_meta(file.filename or ""))
        except ReportUnavailable as e:
            return JSONResponse(status_code=503, content={"error": str(e)})
        # HTTP 头只放 ASCII（中文文件名由前端 a.download 决定）
        ascii_name = "".join(ch for ch in (file.filename or "report") if ch.isascii() and ch.isalnum()) or "report"
        return Response(
            data,
            media_type=DOCX_MIME,
            headers={"Content-Disposition": f"attachment; filename={ascii_name}-report.docx"},
        )

    return app
