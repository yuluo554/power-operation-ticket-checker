# data/ 数据台账

> 规则（ai-tool-project-sprint 阶段1）：每份数据登记来源与许可；规范条目挂出处+status；程序化自制带真值数据是核心资产（固定 seed 可复现，可注入已知缺陷做配对评测）。`_private/` 目录不入仓。

## 登记表

| 数据 | 类型 | 来源 | 许可 | 状态 |
|---|---|---|---|---|
| samples/sample-operating-01.txt | 变电站倒闸操作票 demo 样例 | 人工编写的虚构演示数据（设备/人名均非真实） | 项目自带（MIT） | ✅ M0 |
| ticket_templates/*.txt（7 票种） | 票样布局模板（{{占位符}}） | 重构自 Q/GDW 1799.1/1799.2 附录票样结构；字段名与内容全部自拟虚构；渠道与偏差见 ticket_templates/README.md、templates.json channels_checked | 项目自带（MIT） | ✅ M1，status=待核对（附录编号两源分歧，M3 官方原文核对） |
| ticket_templates/templates.json | 字段注册表（每字段挂 source/status） | 同上，逐项挂票样结构位置 | 项目自带（MIT） | ✅ M1 |
| generator/generate.py + generator/defect_catalog.json | 生成器 + 缺陷对齐清单/互斥矩阵/封顶参数 | 程序化自制（stdlib，Python 3.8 兼容） | 项目自带（MIT） | ✅ M1 |
| samples/gen/（35 份票据 + 35 份真值 + manifest.json，seed=20261002） | 带真值配对评测集（7 正常 + 28 缺陷/组合） | 程序化自制：generator/generate.py（内容全部虚构，逐份缺陷/期望见 gen/manifest.json） | 项目自带（MIT） | ✅ M1，--force 位级一致门常驻测试 |
| knowledge/raw/（6 张规范登记卡 + nea-25fanCuo-2023.pdf） | 规范原文+来源台账（知识库第一层） | 国能发安全〔2023〕22号：国家能源局官网附件 PDF 直连下载（zfxxgk.nea.gov.cn，魔数/大小已校验，官方文件公开发布）；其余 5 项：编号/名称核对+渠道登记，条文未获取处显式待核对（格式见 raw/README.md） | 登记卡/誊录：项目自带（MIT）；规范原文版权归原发布机构 | ✅ M3，25 反措 §1.2.7/1.2.19/3.1.1/3.2.1/3.2.2 逐字誊录=已核对，其余待核对 |
| knowledge/chunks/chunks.json | 条文块 26 条（知识库第二层，raw 确定性建块） | 程序化生成：powerticket.knowledge.ingest（--check 位级校验常驻测试） | 项目自带（MIT） | ✅ M3 |
| knowledge/rules/rules-form.json（12 条） | 必填项+签字链规则（知识库第三层） | 依据 raw/ 登记卡条款：required_field 挂 Q/GDW 票样重构（待核对）；process_signature 挂 25 反措 §3.2.1（已核对） | 项目自带（MIT） | ✅ M3 |
| knowledge/rules/rules-time.json（19 条） | 时间逻辑规则（interval + in_window 两模式） | 时间栏目口径挂 Q/GDW（待核对）；含许可落计划区间/终结闭环（M3 扩展） | 项目自带（MIT） | ✅ M3 |
| knowledge/rules/rules-content.json（8 条） | 内涵校核规则：票种匹配/四要素/五防/一致性 | 四要素挂 25 反措 §1.2.7、五防挂 §1.2.19（均已核对）；票种匹配/一致性挂 Q/GDW（待核对） | 项目自带（MIT） | ✅ M3 |

## M1 真值语义速记（详版见 generator/README.md）

- `expect`：注入项主期望结论（check_type 粒度）；`also_expect`：已声明规则语义强制推出的隐含结论（当前唯一来源：missing_field 注入时间字段 → time_order 待人工确认）。
- 评测按"文档全部非 pass 集合"对账；正常样例 expected=∅，任何非 pass 即误报。
- `fields`（时间 ISO）+ operation_sequence/safety_measures 为解析真值；缺失注入字段不出现于 fields。

## 规范依据查证记录

- 国能发安全〔2023〕22号（二十五项反措 2023版）：国家能源局 zfxxgk.nea.gov.cn 通知页+附件 PDF 均直连核验，2026-10-02 ✅；**官方原文 PDF 已下载入库**（knowledge/raw/nea-25fanCuo-2023.pdf，245 页），§1.2.7/§1.2.19/§3.1.1/§3.2.1/§3.2.2 逐字誊录入 chunks，status=已核对 ✅
- GB 26860-2011：国家标准全文公开系统 openstd.samr.gov.cn（hcno=3428089C6475E0B29FF38B8C6D8EC205），2026-10-02 查证 ✅；全文为在线图片版，机器可读条文未获取 ⬜
- GB 26859-2011：编号/名称经检索核对，原文全文待入库获取 ⬜
- Q/GDW 1799.1-2013 / Q/GDW 1799.2-2013：编号/附录票样结构经检索核对（附录票样字段清单为解析器设计输入）；条文全文待获取（检索摘要一律不采信）⬜
  - M1 补充：附录票样结构已用于模板重构（票样目录经京东读书在线阅读页确认；附录编号在两公开渠道存在分歧，已按"待核对"落库）；工作票栏目清单另经安全管理网《工作票的使用和管理》页抓取佐证（safehoo.com，2026-10-02）
  - 版本提示：检索发现 Q/GDW 1799.1-2024 新版存在，M3 入库时核对版本适用性 ⬜
- DL/T 408-2023：编号经检索核对，版本适用性说明需入库时核对 ⬜

## M3 知识库速记（详版见 knowledge/raw/README.md）

- 三层：raw（登记卡+官方 PDF）→ chunks（ingest 确定性建块 26 条，`--check` 位级门）→ rules（39 条规则 JSON）。
- 出处纪律：`quote` 非空 ⇔ status=已核对（测试锁定）；每条规则的 (standard, clause) 必须解析到条文块（三层联动测试锁定）。
- 检索：`KnowledgeBase.load().search(query, top_k)` 纯 Python 余弦（汉字二元组+ASCII 词元），零三方依赖。
