"""raw → chunks 建块（确定性）：读 data/knowledge/raw/*.json 的条文条目 → chunks/chunks.json。

每个条文块挂 standard+clause+topic+text+quote+channel+status（M3 既定口径）；
status ∈ {已核对, 待核对}：quote 为空的块必须是待核对（原文未获取，不编造）。
build_chunks() 为纯函数、无随机性；CLI 写文件显式 LF（与生成器同纪律）。

用法：
    py -X utf8 -m powerticket.knowledge.ingest            # 默认重建 data/knowledge/chunks/chunks.json
    py -X utf8 -m powerticket.knowledge.ingest --check    # 只校验内存产物与已提交文件位级一致
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_DIR = _REPO_ROOT / "data" / "knowledge" / "raw"
DEFAULT_OUT = _REPO_ROOT / "data" / "knowledge" / "chunks" / "chunks.json"

CHUNKS_SCHEMA = "powerticket-knowledge-chunks/0.1"
_STATUSES = ("已核对", "待核对")


class IngestError(Exception):
    """raw 层条文条目不合法或 chunks 产物校验失败。"""


def build_chunks(raw_dir: Path = DEFAULT_RAW_DIR) -> Dict[str, Any]:
    if not raw_dir.is_dir():
        raise IngestError(f"raw 目录不存在: {raw_dir}")
    chunks: List[Dict[str, Any]] = []
    seen_ids: set = set()
    for f in sorted(raw_dir.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        standard = str(data.get("standard", "")).strip()
        title = str(data.get("title", "")).strip()
        if not standard or not title:
            raise IngestError(f"{f.name} 缺 standard/title")
        channel_default = str(data.get("channel", "")).strip()
        for entry in data.get("clauses", []):
            clause = str(entry.get("clause", "")).strip()
            status = str(entry.get("status", "待核对")).strip()
            text = str(entry.get("text", "")).strip()
            quote = str(entry.get("quote", "")).strip()
            channel = str(entry.get("channel", channel_default)).strip()
            if not clause:
                raise IngestError(f"{f.name} 存在缺 clause 的条文条目")
            if status not in _STATUSES:
                raise IngestError(f"{f.name}/{clause} status 非法: {status}")
            if not text and not quote:
                raise IngestError(f"{f.name}/{clause} text 与 quote 均为空，无法建块")
            if not channel:
                raise IngestError(f"{f.name}/{clause} 缺登记渠道（来源台账纪律）")
            if status == "已核对" and not quote:
                raise IngestError(f"{f.name}/{clause} 已核对但无原文摘录（quote 不得为空）")
            chunk_id = f"{standard}::{clause}"
            if chunk_id in seen_ids:
                raise IngestError(f"chunk_id 重复: {chunk_id}")
            seen_ids.add(chunk_id)
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "standard": standard,
                    "title": title,
                    "clause": clause,
                    "topic": str(entry.get("topic", "")).strip(),
                    "text": text,
                    "quote": quote,
                    "channel": channel,
                    "status": status,
                }
            )
    if not chunks:
        raise IngestError(f"{raw_dir} 未产出任何条文块")
    return {
        "schema": CHUNKS_SCHEMA,
        "built_from": "data/knowledge/raw",
        "chunk_count": len(chunks),
        "chunks": chunks,
    }


def chunks_to_text(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="powerticket.knowledge.ingest",
        description="规范知识库建块：data/knowledge/raw/*.json → chunks/chunks.json（确定性）",
    )
    parser.add_argument("--raw", default=str(DEFAULT_RAW_DIR), help="raw 目录")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="输出 chunks.json 路径")
    parser.add_argument(
        "--check", action="store_true", help="只校验内存产物与已提交文件位级一致，不写文件"
    )
    args = parser.parse_args(argv)

    try:
        payload = build_chunks(Path(args.raw))
    except IngestError as e:
        print(f"建块失败: {e}", file=sys.stderr)
        return 2
    text = chunks_to_text(payload)
    out = Path(args.out)
    if args.check:
        if not out.is_file():
            print(f"校验失败: {out} 不存在", file=sys.stderr)
            return 2
        if out.read_text(encoding="utf-8") != text:
            print(f"校验失败: {out} 与内存产物位级不一致（raw 变更后需重建）", file=sys.stderr)
            return 2
        print(f"校验通过: {out} 与内存产物一致（{payload['chunk_count']} 个条文块）")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"已写入 {out}（{payload['chunk_count']} 个条文块）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
