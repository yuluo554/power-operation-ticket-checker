"""Web 审核面板（M5）：FastAPI 上传 → 参数卡 → 校核结论 → 报告预览。

前端 vendor 本地化（Vue3/PDF.js），页面 0 外链断网可演示。
依赖仅入 extras[web]；注意 File(...) 隐式依赖 python-multipart，缺声明启动即崩（已在 pyproject 锁死）。
"""


class WebUnavailable(RuntimeError):
    """Web 依赖不可用。"""

    def __init__(self, reason: str = "依赖未安装"):
        super().__init__(
            f"Web 面板不可用（{reason}）。计划 M5 提供；依赖安装：py -m pip install -e .[web]"
        )
