"""票据文本清洗：CRLF 归一、零宽字符与全角空格（M2 扩展字符定位伪空格）。"""
from __future__ import annotations


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u200b", "").replace("\ufeff", "")
    text = text.replace("\u3000", " ")
    return text
