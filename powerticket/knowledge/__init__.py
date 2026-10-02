"""规范知识库三层：raw（规范原文+来源台账）→ chunks（条文块+余弦检索）→ rules（机器可读规则）。

- raw/：每项规范一张登记卡（JSON）+ 官方原文文件（已获取者）；查不到原文的条目
  显式 status=待核对 并登记渠道，不编造、不停摆。
- chunks/：`py -m powerticket.knowledge.ingest` 从 raw 确定性建块；检索用
  KnowledgeBase（纯 Python 余弦，零三方依赖）。
- rules/：规则 JSON 由 powerticket.rules.load_rules 加载（全 7 类 check_type，M3 起）。

三层联动守门：每条规则的 (basis.standard, basis.clause) 必须能解析到条文块
（tests/test_knowledge.py::test_rules_link_to_chunks）。

注意：本包 __init__ 不预导入 .ingest（`py -m powerticket.knowledge.ingest` 直跑时
避免同模块双导入的 RuntimeWarning）；建块函数从 powerticket.knowledge.ingest 导入。
"""
from .retrieval import KnowledgeBase, cosine, tokenize

__all__ = [
    "KnowledgeBase",
    "cosine",
    "tokenize",
]
