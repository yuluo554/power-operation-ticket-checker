"""M3 知识库守门：raw 台账完整性 / chunks 位级一致 / 余弦检索命中 / 规则↔条文块三层联动。"""
from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from powerticket.knowledge import KnowledgeBase
from powerticket.knowledge.ingest import CHUNKS_SCHEMA, build_chunks, chunks_to_text
from powerticket.rules import load_rules

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "knowledge" / "raw"
CHUNKS_FILE = ROOT / "data" / "knowledge" / "chunks" / "chunks.json"
RULES_DIR = ROOT / "data" / "knowledge" / "rules"

CORE_STANDARDS = {
    "GB 26859-2011",
    "GB 26860-2011",
    "Q/GDW 1799.1-2013",
    "Q/GDW 1799.2-2013",
    "国能发安全〔2023〕22号",
    "DL/T 408-2023",
}


@pytest.fixture(scope="module")
def chunks():
    data = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
    return data


@pytest.fixture(scope="module")
def kb(chunks):
    return KnowledgeBase(chunks["chunks"])


# ---------------------------------------------------------------------------
# raw 层：6 项核心规范登记卡齐全，条文块出处纪律（quote 非空 ⇔ 已核对）
# ---------------------------------------------------------------------------

def test_raw_covers_six_core_standards():
    standards = set()
    for f in RAW_DIR.glob("*.json"):
        data = json.loads(f.read_text(encoding="utf-8"))
        standards.add(data["standard"])
        assert data["channel"].strip() and data["acquisition"].strip()
        assert data["overall_status"] in ("已核对", "待核对")
    assert CORE_STANDARDS <= standards


def test_nea_official_pdf_registered_and_valid():
    card = json.loads((RAW_DIR / "nea-25fanCuo-2023.json").read_text(encoding="utf-8"))
    pdf = RAW_DIR / card["local_file"]
    assert pdf.is_file()
    head = pdf.read_bytes()[:5]
    assert head == b"%PDF-", "官方原文 PDF 魔数校验失败"
    assert card["overall_status"] == "已核对"
    assert any("zfxxgk.nea.gov.cn" in u for u in card["source_urls"])


# ---------------------------------------------------------------------------
# chunks 层：确定性建块（位级一致门）+ 出处纪律
# ---------------------------------------------------------------------------

def test_chunks_bit_identical_with_committed():
    payload = build_chunks(RAW_DIR)
    assert CHUNKS_FILE.read_text(encoding="utf-8") == chunks_to_text(payload)


def test_chunks_schema_and_provenance(chunks):
    assert chunks["schema"] == CHUNKS_SCHEMA
    assert chunks["built_from"] == "data/knowledge/raw"
    assert chunks["chunk_count"] == len(chunks["chunks"]) >= 20
    for c in chunks["chunks"]:
        assert c["chunk_id"] == f"{c['standard']}::{c['clause']}"
        assert c["status"] in ("已核对", "待核对")
        assert c["channel"].strip(), c["chunk_id"]
        assert (c["text"] or c["quote"]).strip(), c["chunk_id"]
        if c["status"] == "已核对":
            assert c["quote"].strip(), f"{c['chunk_id']} 已核对但无原文摘录"
        else:
            assert not c["quote"].strip(), f"{c['chunk_id']} 待核对却带 quote（疑似编造）"


def test_nea_chunks_carry_verified_quotes(chunks):
    nea = {c["clause"]: c for c in chunks["chunks"] if c["standard"] == "国能发安全〔2023〕22号"}
    assert {"1.2.7", "1.2.19", "3.1.1", "3.2.1", "3.2.2"} <= set(nea)
    for c in nea.values():
        assert c["status"] == "已核对" and c["quote"].strip()
    assert "带负荷拉（合）隔离开关" in nea["1.2.19"]["quote"]
    assert "停电、验电、接地、悬挂标示牌" in nea["1.2.7"]["quote"]


# ---------------------------------------------------------------------------
# 检索：纯 Python 余弦（接口签名 M3 定稿：load/search）
# ---------------------------------------------------------------------------

def test_retrieval_finds_five_prevention_clause(kb):
    hits = kb.search("带负荷拉合隔离开关 五防 严禁", top_k=3)
    assert hits, "检索无结果"
    assert "1.2.19" in hits[0][0]["clause"]
    score = hits[0][1]
    assert 0.0 < score <= 1.0
    assert score >= hits[-1][1]


def test_retrieval_finds_four_elements_clause(kb):
    hits = kb.search("停电检修 安全措施 验电 接地 标示牌 遮栏", top_k=3)
    assert hits, "检索无结果"
    assert "1.2.7" in hits[0][0]["clause"]


def test_retrieval_finds_two_ticket_discipline(kb):
    hits = kb.search("两票制度 操作票 工作票 执行", top_k=3)
    assert hits, "检索无结果"
    assert "3.2.1" in hits[0][0]["clause"]


def test_retrieval_top_k_and_no_match(kb):
    assert kb.search("停电 验电 接地", top_k=2).__len__() == 2
    assert kb.search("", top_k=3) == []
    assert kb.search("完全无关的查询词组量子混沌", top_k=3) == []


# ---------------------------------------------------------------------------
# rules 层与三层联动：每条规则的 (standard, clause) 必须解析到条文块
# ---------------------------------------------------------------------------

def test_rules_link_to_chunks(chunks):
    chunk_keys = {(c["standard"], c["clause"]) for c in chunks["chunks"]}
    rules = load_rules()
    assert rules, "规则库为空"
    for r in rules:
        basis = r["basis"]
        assert basis.get("status") in ("已核对", "待核对"), r["id"]
        assert basis.get("channel", "").strip(), r["id"]
        assert "quote" in basis, f"{r['id']} basis 缺 quote 键"
        key = (basis["standard"], basis["clause"])
        assert key in chunk_keys, f"{r['id']} 依据 {key} 未解析到条文块（三层联动断裂）"


def test_rules_basis_status_discipline():
    for r in load_rules():
        b = r["basis"]
        if b.get("status") == "已核对":
            assert b.get("quote", "").strip(), f"{r['id']} 已核对但无原文摘录"
        else:
            assert not b.get("quote", "").strip(), f"{r['id']} 待核对却带 quote（疑似编造）"


def test_ingest_check_cli_bit_identical():
    ingest = importlib.import_module("powerticket.knowledge.ingest")
    assert ingest.main(["--check"]) == 0
