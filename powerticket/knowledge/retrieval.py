"""纯 Python 余弦检索：汉字二元组 + ASCII 词元，core 零三方依赖（plan/04 §4）。

检索接口（M3 定稿，列入既定口径）：
    KnowledgeBase.load(path=None) -> KnowledgeBase          # 默认 data/knowledge/chunks/chunks.json
    kb.search(query: str, top_k: int = 5) -> list[tuple[dict, float]]
返回 [(条文块, 余弦相似度)]，按分数降序、同分按 chunk_id 升序；零分块不返回。
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHUNKS_PATH = _REPO_ROOT / "data" / "knowledge" / "chunks" / "chunks.json"

_ASCII_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")
_HAN_RE = re.compile(r"[一-鿿]+")


def tokenize(text: str) -> List[str]:
    """汉字按相邻二元组切词（单字成段保留单字），ASCII 连续串按词保留，全部小写。"""
    lowered = text.lower()
    tokens: List[str] = _ASCII_TOKEN_RE.findall(lowered)
    for seg in _HAN_RE.findall(lowered):
        if len(seg) == 1:
            tokens.append(seg)
        else:
            tokens.extend(seg[i : i + 2] for i in range(len(seg) - 1))
    return tokens


def _term_freqs(tokens: List[str]) -> Dict[str, float]:
    freqs: Dict[str, float] = {}
    for t in tokens:
        freqs[t] = freqs.get(t, 0.0) + 1.0
    return freqs


def cosine(query: Dict[str, float], doc: Dict[str, float]) -> float:
    if not query or not doc:
        return 0.0
    dot = sum(v * doc.get(t, 0.0) for t, v in query.items())
    nq = math.sqrt(sum(v * v for v in query.values()))
    nd = math.sqrt(sum(v * v for v in doc.values()))
    if nq == 0.0 or nd == 0.0:
        return 0.0
    return dot / (nq * nd)


class KnowledgeBase:
    """条文块知识库：加载 chunks.json 后做余弦检索（无索引预热、无三方依赖）。"""

    def __init__(self, chunks: List[dict]):
        if not chunks:
            raise ValueError("知识库为空：chunks.json 中没有条文块。")
        self.chunks = chunks
        self._vectors: List[Tuple[dict, Dict[str, float]]] = [
            (
                chunk,
                _term_freqs(
                    tokenize(
                        " ".join(
                            str(chunk.get(k, ""))
                            for k in ("standard", "clause", "topic", "text", "quote")
                        )
                    )
                ),
            )
            for chunk in chunks
        ]

    @classmethod
    def load(cls, path: Optional[str] = None) -> "KnowledgeBase":
        chunks_path = Path(path) if path else DEFAULT_CHUNKS_PATH
        if not chunks_path.is_file():
            raise FileNotFoundError(f"条文块文件不存在: {chunks_path}")
        data = json.loads(chunks_path.read_text(encoding="utf-8"))
        return cls(data.get("chunks", []))

    def search(self, query: str, top_k: int = 5) -> List[Tuple[dict, float]]:
        if top_k <= 0:
            return []
        qv = _term_freqs(tokenize(query))
        scored = [(chunk, cosine(qv, vec)) for chunk, vec in self._vectors]
        scored = [(c, s) for c, s in scored if s > 0.0]
        scored.sort(key=lambda item: (-item[1], item[0]["chunk_id"]))
        return scored[:top_k]
