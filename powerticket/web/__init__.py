"""Web 审核面板（M5，plan/04 §5）：FastAPI 上传 → 参数卡 → 校核结论 → 报告预览/导出。

- 应用工厂：powerticket.web.app.create_app（fastapi 懒加载，CLI web 懒加载本模块）；
- 前端为内联单页 static/index.html（零依赖 vanilla JS，无任何外部资源引用），
  等效达成"前端 vendor 本地化 + 页面 0 外链断网可演示"（M5 定稿，plan/06）；
- 依赖仅入 extras[web]；注意 File(...) 隐式依赖 python-multipart，缺声明启动即崩（已在 pyproject 锁死）。
"""


class WebUnavailable(RuntimeError):
    """Web 依赖不可用。"""

    def __init__(self, reason: str = "依赖未安装"):
        super().__init__(
            f"Web 面板不可用（{reason}）。依赖安装：py -m pip install -e .[web]"
        )
