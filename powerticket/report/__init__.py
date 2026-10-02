"""docx 报告导出（M5）：结论+分级问题清单+逐条证据+整改建议+签署栏。

依赖仅入 extras[report]（python-docx），缺失时抛 ReportUnavailable 由 CLI 打印安装提示。
"""


class ReportUnavailable(RuntimeError):
    """报告导出依赖不可用。"""

    def __init__(self, reason: str = "依赖未安装"):
        super().__init__(
            f"报告导出不可用（{reason}）。计划 M5 提供；依赖安装：py -m pip install -e .[report]"
        )
