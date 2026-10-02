# HANDOFF-M4（M3 收尾交接快照）

> **已过时仅作历史**（M4 已于 2026-10-02 完成，续接请读 [HANDOFF-M5.md](HANDOFF-M5.md)）。
>
> 写于 2026-10-02，M3（知识库三层 + 规则引擎全量）收尾。下一里程碑：M4 LLM 兜底 + 基准评测。新对话续接提示词：
> `/goal 读取 "D:\ProgramData\zcode\power-operation-ticket-checker\plan\HANDOFF-M4.md" 继续完成任务`

## 当前进度（M0–M3 已完成）

- plan/00–06 定稿；M0 骨架 + M1 数据先行 + M2 解析层（详见 HANDOFF-M3.md，其 M0–M2 段仍有效）。
- **M3 交付**：
  - **知识库三层落地**（`data/knowledge/`）：
    - `raw/`：6 项核心规范登记卡 JSON（standard/title/channel/source_urls/acquisition/overall_status/clauses[]）+ `nea-25fanCuo-2023.pdf`（国家能源局官网附件直连下载，245 页，魔数/大小校验通过，官方公开文件）。**出处纪律：quote 非空 ⇔ status=已核对**；25 反措 §1.2.7/§1.2.19/§3.1.1/§3.2.1/§3.2.2 逐字誊录=已核对，其余（Q/GDW×2、GB×2、DL/T）条文未获取=待核对+登记渠道，不编造不停摆。格式见 raw/README.md。
    - `chunks/chunks.json`：26 条条文块，`py -m powerticket.knowledge.ingest` 从 raw 确定性建块（`--check` 位级校验常驻测试 `test_chunks_bit_identical_with_committed`、`test_ingest_check_cli_bit_identical`）。
    - `rules/`：正式规则库三文件 `rules-form.json`(12)/`rules-time.json`(19)/`rules-content.json`(8)，**共 39 条**，demo-operating.json 退役。
  - **规则引擎全量 7 类 check_type**（`powerticket/rules/checks.py`）：required_field / time_order（**双模式** interval+in_window）/ process_signature / ticket_type_match / measure_coverage（直接消费 card.safety_measures）/ five_prevention（三形式化口径 no_load_disconnector·no_ground_close·grounding_after_test）/ consistency（设备双重名称×电压等级互证，正则 `(\d+)kV([一-鿿]{2,8}?线)([0-9\-号杆分段]{1,12}?)(断路器|隔离开关|接地开关)`）。
  - **time_order 扩展**：许可开始时间落计划区间（R-W?-004，violation——016/026 号 permit_time_out_of_range 样例主判）；终结不早于许可（R-W?-005）；终结超计划区间提示延期（R-W?-006，on_violation=manual 不硬判）。
  - **缺陷全集精确对账**：8 缺陷类型全部有可触发规则后，28 份缺陷样例非 pass 集合 == expect∪also_expect（精确相等，多出=双计/缺少=漏检），7 正常样例 0 误报；M2 的 `_covered_expected` 子集口径退役。测试 **145 项全绿**（M2 为 98）。
  - 检索：`KnowledgeBase.load().search(query, top_k)` 纯 Python 余弦（汉字二元组+ASCII 词元），零三方依赖；三层联动测试锁定每条规则 (basis.standard, basis.clause) 必须解析到条文块。
  - 已提交本地 git（**未推送**，发布在 M6 经用户确认）。

## M4 待办（LLM 兜底 + 基准评测）

1. **基准两脚本**（`powerticket/eval/`，CLI `py -m powerticket benchmark` 点亮，现为 stub）：
   - `parse_f1`：字段级 P/R/F1，生成器真值 vs 解析结果（35 份 gen 样例；fields + operation_sequence/safety_measures； remarks 是唯一不入真值的已抽取字段，评测字段集 = truth.fields）。
   - `endtoend`：检出率/误报率/判定准确率，植入缺陷 vs 规则命中；按 **"非 pass 集合 == expect∪also_expect"** 口径（M3 已定，test_data_generator.py `test_generated_sample_expected_conclusions_fire` 即参考实现）。
   - 门槛：F1≥0.95、误报 0；**基准零 API 依赖**可重复；指标写进 README。
2. **LLM 兜底抽取**（`powerticket/llm/` 现为空壳）：解析失败/低置信度时走 LLM 兜底，**与规则解析同一参数卡出口**（TicketCard），带 warnings 留痕；供应商按决策 D-2（DashScope qwen，openai 兼容，`enable_thinking=false`），密钥 `.env` 不入仓；**LLM 断供降级测试**（无 key/网络断 → 纯规则通路照常出结论，测试锁定）。
3. README 增补基准指标与运行方式；CLI `benchmark` 子命令接真实现（去掉 stub）。
4. （可选，不阻塞）ticket_templates 附录编号两源分歧核对——Q/GDW 全文仍未公开获取，维持"待核对"即可，勿强行定稿。

## 既定口径清单（M3 新增/锁定部分；M0–M2 口径见 HANDOFF-M3.md，均仍有效）

- **知识库出处纪律**：`quote` 非空 ⇔ `status=已核对`；仅官方可直连原文可标已核对（当前唯一来源：国能发安全〔2023〕22号官方 PDF，已入仓 data/knowledge/raw/nea-25fanCuo-2023.pdf）；待核对条目 quote="" + 登记渠道。
- **知识库检索接口**：`KnowledgeBase.load(path=None)`；`kb.search(query, top_k=5) -> list[(chunk, score)]`（余弦降序、同分按 chunk_id 升序、零分不返回）；分词=汉字二元组+ASCII 词元。
- **规则库三文件**：rules-form/rules-time/rules-content.json，39 条；规则 id 前缀 R-OP/R-LOP/R-W1/R-W2/R-LW1/R-LW2/R-ER；风险分级基线：required=低、time/signature=一般、type_match/measure=较大、five_prevention=重大、consistency=一般。
- **time_order 双模式**：params.mode=interval（默认，start<end）/ in_window（target∈[start,end]，on_violation=violation|manual）。
- **ticket_type_match 任务缺失跳过**：不产出结论（缺失归 required_field，防归因双计）——030 号样例全集对账锁定此行为。
- **五防三口径**：no_load_disconnector / no_ground_close / grounding_after_test（params.variants 选择）；依据 25 反措 §1.2.19（已核对）。
- **measure_coverage 四要素关键词**（params.elements）：停电=[断开,停电]、验电=[验电]、装设接地线=[接地线,装设接地,合上接地]、悬挂标示牌和装设遮栏=[标示牌]；applies_to 仅 work_first/line_work_first。
- **全集精确对账**：缺陷样例非 pass 集合 == expect∪also_expect；正常样例非 pass=∅。chunks.json 与生成器产物同为位级一致门（ingest --check）。
- 票种代码 7 个、参数卡 schema v0.1+增补、路由顺序门控、measures 独立容器、签字链不进 required_field、结论三级+中文汇总键、时间 ISO、真值语义、模板契约、互斥矩阵、包布局、eol=lf 等口径照 HANDOFF-M3.md 不变。

## 本机环境坑（实测，照 HANDOFF-M3.md 全部有效）

- 仅 Python 3.8.8：`py` 启动；`from __future__ import annotations`；`Path.write_text` 无 `newline` 参数（用 `open(..., newline="\n")`）。
- 一律 `py -X utf8`；长任务 `PYTHONDONTWRITEBYTECODE=1`；怪错先清 `__pycache__`。
- pip 被系统代理污染：`NO_PROXY="*" no_proxy="*" py -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <pkg>`。
- Git Bash `/tmp` 与 Windows Python 不通：临时文件用仓库内路径。
- 本机已装 pypdf 5.9.0 / pdfminer（25 反措 PDF 誊录用过，core 代码未依赖）。

## M3 DoD 核对

- [x] 知识库三层落地：raw 6 登记卡+官方 PDF → chunks 26 条确定性建块 → rules 39 条 ✅
- [x] 规则引擎补全 5 类 check_type（signature/type_match/measure/five_prevention/consistency）✅
- [x] time_order 扩展：许可落计划区间（016/026 触发）+ 终结闭环 ✅
- [x] 出处纪律：quote 非空 ⇔ 已核对；三层联动（规则依据↔条文块）测试锁定 ✅
- [x] 检索：纯 Python 余弦，接口签名定稿并测试 ✅
- [x] 缺陷全集精确对账（28 缺陷 + 7 正常零误报），_covered_expected 例外退役 ✅
- [x] 正式规则库拆分三文件，demo-operating.json 退役，test_package 同步 ✅
- [x] plan/00/04/05/06、data/README 回写；HANDOFF-M4 本档 ✅
- [x] 全量测试 145 项全绿 + demo/check 实跑通过（含 4 份缺陷样例抽检命中）✅
- [x] 本地提交（未推送）✅

## 关键命令速查

```bash
cd /d/ProgramData/zcode/power-operation-ticket-checker
py -X utf8 -m pytest                                  # 全量测试（145 项）
py -X utf8 -m powerticket demo                        # 端到端演示（operating，4 规则全合规）
py -X utf8 -m powerticket check data/samples/gen/gen-operating-005-five-prevention.txt
py -X utf8 -m powerticket.knowledge.ingest            # raw → chunks 重建（26 块）
py -X utf8 -m powerticket.knowledge.ingest --check    # chunks 位级校验
PYTHONDONTWRITEBYTECODE=1 py -X utf8 data/generator/generate.py --force   # 重生成样例
git status && git log --oneline -3                    # 提交前三核对（本仓库）
```
