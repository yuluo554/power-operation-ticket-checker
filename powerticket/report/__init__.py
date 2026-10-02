"""docx 报告导出（M5，plan/04 §5）：结论汇总→分级问题清单→逐条证据（含原文摘录）→整改建议→待人工确认→签署栏。

- 章节结构（零依赖纯函数）：powerticket.report.sections.build_report_sections；
- docx 渲染（extras[report]，懒加载）：powerticket.report.docx_render；
- 无外链纪律：报告正文不写 URL/超链接，判据 find_external_links 进测试锁定。
"""

from __future__ import annotations

import io
import re
import zipfile
from typing import List


class ReportUnavailable(RuntimeError):
    """报告导出依赖不可用。"""

    def __init__(self, reason: str = "依赖未安装"):
        super().__init__(
            f"报告导出不可用（{reason}）。依赖安装：py -m pip install -e .[report]"
        )


def find_external_links(data: bytes) -> List[str]:
    """扫描 docx 字节流中的外链线索，返回命中描述列表（空列表 = 无外链）。

    判据三条（对应"报告无外链"断言）：
    - 任意 XML 部件出现 <w:hyperlink> 超链接元素；
    - 任意 .rels 出现 TargetMode="External" 外部关系；
    - document.xml 正文文本（<w:t>）出现 http(s):// 字样。
    注：xmlns/关系 Type 属性中的命名空间 URI 不是外链，不计入。
    """
    hits: List[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for name in zf.namelist():
            if not name.endswith((".xml", ".rels")):
                continue
            xml = zf.read(name).decode("utf-8", errors="replace")
            if "<w:hyperlink" in xml:
                hits.append(f"{name}: <w:hyperlink> 元素")
            if 'TargetMode="External"' in xml:
                hits.append(f"{name}: External 关系")
            if name == "word/document.xml":
                for text in re.findall(r"<w:t(?:\s[^>]*)?>([^<]*)</w:t>", xml):
                    if re.search(r"https?://", text):
                        hits.append(f"{name}: 正文文本含 URL: {text[:60]!r}")
    return hits
