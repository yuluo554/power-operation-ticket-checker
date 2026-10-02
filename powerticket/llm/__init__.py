"""LLM 兜底（M4）：非结构化抽取兜底 / 别名归一 / 复核 / 报告行文。

纪律：数值结论永远来自确定性规则；客户端 enable_thinking=false、
摘录逐字回验、失败降级规则通路。依赖仅入 extras[llm]。
"""


class LLMUnavailable(RuntimeError):
    """LLM 依赖或服务不可用（调用方须降级到规则通路）。"""

    def __init__(self, reason: str = "依赖未安装"):
        super().__init__(
            f"LLM 兜底不可用（{reason}）。计划 M4 提供；依赖安装：py -m pip install -e .[llm]"
        )
