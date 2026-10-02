# data/ 数据台账

> 规则（ai-tool-project-sprint 阶段1）：每份数据登记来源与许可；规范条目挂出处+status；程序化自制带真值数据是核心资产（固定 seed 可复现，可注入已知缺陷做配对评测）。`_private/` 目录不入仓。

## 登记表

| 数据 | 类型 | 来源 | 许可 | 状态 |
|---|---|---|---|---|
| samples/sample-operating-01.txt | 变电站倒闸操作票 demo 样例 | 人工编写的虚构演示数据（设备/人名均非真实） | 项目自带（MIT） | ✅ M0 |
| knowledge/rules/demo-operating.json | 演示规则 2 条（R-OP-001/002） | 依据 Q/GDW 1799.1-2013 附录票样字段重构，条款号待核对 | 项目自带（MIT） | ✅ M0，status=待核对 |
| ticket_templates/*.txt（7 票种） | 票样布局模板（{{占位符}}） | 重构自 Q/GDW 1799.1/1799.2 附录票样结构；字段名与内容全部自拟虚构；渠道与偏差见 ticket_templates/README.md、templates.json channels_checked | 项目自带（MIT） | ✅ M1，status=待核对（附录编号两源分歧，M3 官方原文核对） |
| ticket_templates/templates.json | 字段注册表（每字段挂 source/status） | 同上，逐项挂票样结构位置 | 项目自带（MIT） | ✅ M1 |
| generator/generate.py + generator/defect_catalog.json | 生成器 + 缺陷对齐清单/互斥矩阵/封顶参数 | 程序化自制（stdlib，Python 3.8 兼容） | 项目自带（MIT） | ✅ M1 |
| samples/gen/（35 份票据 + 35 份真值 + manifest.json，seed=20261002） | 带真值配对评测集（7 正常 + 28 缺陷/组合） | 程序化自制：generator/generate.py（内容全部虚构，逐份缺陷/期望见 gen/manifest.json） | 项目自带（MIT） | ✅ M1，--force 位级一致门常驻测试 |

## M1 真值语义速记（详版见 generator/README.md）

- `expect`：注入项主期望结论（check_type 粒度）；`also_expect`：已声明规则语义强制推出的隐含结论（当前唯一来源：missing_field 注入时间字段 → time_order 待人工确认）。
- 评测按"文档全部非 pass 集合"对账；正常样例 expected=∅，任何非 pass 即误报。
- `fields`（时间 ISO）+ operation_sequence/safety_measures 为解析真值；缺失注入字段不出现于 fields。

## 规范依据查证记录

- GB 26860-2011：国家标准全文公开系统 openstd.samr.gov.cn（hcno=3428089C6475E0B29FF38B8C6D8EC205），2026-10-02 查证 ✅
- GB 26859-2011：编号/名称经检索核对，原文全文待入库获取 ⬜
- Q/GDW 1799.1-2013 / Q/GDW 1799.2-2013：编号/附录票样结构经检索核对，条文全文待入库获取（附录票样字段清单为解析器设计输入）⬜
  - M1 补充：附录票样结构已用于模板重构（票样目录经京东读书在线阅读页确认；附录编号在两公开渠道存在分歧，已按"待核对"落库）；工作票栏目清单另经安全管理网《工作票的使用和管理》页抓取佐证（safehoo.com，2026-10-02）
  - 版本提示：检索发现 Q/GDW 1799.1-2024 新版存在，M3 入库时核对版本适用性 ⬜
- 二十五项反措 2023版（国能发安全〔2023〕22号）：国家能源局 zfxxgk.nea.gov.cn 原文 PDF，2026-10-02 查证 ✅，待下载入库 ⬜
- DL/T 408-2023：编号经检索核对，版本适用性说明需入库时核对 ⬜
