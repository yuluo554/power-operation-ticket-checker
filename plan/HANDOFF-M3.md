# HANDOFF-M3（M2 收尾交接快照）

> 写于 2026-10-02，M2（解析层）收尾。下一里程碑：M3 知识库三层 + 规则引擎全 check_type。新对话续接提示词：
> `/goal 读取 "D:\ProgramData\zcode\power-operation-ticket-checker\plan\HANDOFF-M3.md" 继续完成任务`

## 当前进度（M0+M1+M2 已完成）

- plan/00–06 定稿；M0 骨架 + M1 数据先行（详见 HANDOFF-M2.md 的 M1 段，仍有效）。
- **M2 交付**：
  - `powerticket/parse/`：7 票种解析器全覆盖（每票种一个模块：`operating.py` 含 `parse_operating_like` 共用骨架、`line_operating.py`、`work.py` 四票种共用骨架 + `work_first/work_second/line_work_first/line_work_second.py` 薄壳、`emergency_repair.py`；公共件 `common.py`：时间归一/字段入卡合法性门/标签行与编号块抽取）。
  - 路由修复：`_TYPE_KEYWORDS` 补齐 line_work_first/line_work_second；**顺序门控**——线路专用关键词排在同款通用关键词之前（子串包含），路由负例测试锁定。
  - 双时间行：工作票 `计划工作时间：自…至…` 拆 plan_start/plan_end；许可/终结/抢修时间全部 ISO 入卡；合法性校验含日历越界（13 月丢弃+warnings）。
  - **measures 表示定稿**：参数卡增补 `safety_measures: list[SafetyMeasure{no,text,evidence}]` 独立容器（schema v0.1 增补，与 operation_sequence 对称、与真值结构镜像）；备注（remarks）照常抽取但不入真值（虚构声明）。
  - dispatcher（发令人）抽取完成；demo 样例补发令人行，R-OP-001 必填字段含 dispatcher。
  - demo 规则库扩至 14 条（7 票种 × required_field + time_order；工作票查 plan_start/plan_end）；**签字链字段（签发人/许可人）不进 required_field 参数**（归 process_signature，防归因双计）。
  - 回归：35 份样例 truth↔card 逐项对账（字段集精确相等−remarks、值+证据逐项、steps/measures 列表块）+ 注入缺失字段不入卡留痕 + 已覆盖期望（required_field/time_order，许可越界除外）全触发 + 7 正常样例零误报零告警。测试 98 项全绿。
- 已提交本地 git（**未推送**，发布在 M6 经用户确认）。

## M3 待办（知识库三层 + 规则引擎全量）

1. 知识库三层落地：`data/knowledge/raw/`（6 项核心规范原文+来源台账，入库渠道 fallback 见 plan/05 §3）→ `chunks/`（条文块，纯 Python 余弦检索）→ `rules/`（机器可读规则 JSON）。每条挂 `standard+clause+quote+channel+status`；查不到 → "待核对"+登记渠道，不编造不停停。
2. 规则引擎补全 check_type：`process_signature`（签字链缺环——M2 已把签发人/许可人从 required_field 参数排除，语义归此）/ `ticket_type_match`（票种与停电需求错配）/ `measure_coverage`（第一种票四要素——直接消费 `card.safety_measures`）/ `five_prevention`（防带负荷拉合隔离开关等形式化检查）/ `consistency`（双重名称/电压等级互证）。
3. `time_order` 扩展：许可开始时间落计划区间（permit_time_out_of_range 缺陷样例 016/026 在等这条规则；M2 的 `_covered_expected` 测试口径届时移除例外）。
4. 规则与缺陷目录对账：8 缺陷类型全部有可触发规则后，M2 回归测试的 covered 子集对账升级为全集对账（或移交 M4 基准）。
5. 正式规则库拆分文件/命名（demo-operating.json 是骨架演示件，M3 重构为正式库；`test_package.test_demo_rules_file_registered` 引用此文件名需同步）。

## 既定口径清单（动了会打挂基准/测试，先对照再改）

- 票种代码 7 个：`operating / line_operating / work_first / work_second / line_work_first / line_work_second / emergency_repair`（plan/04 §1）。
- 参数卡 schema v0.1+M2 增补：`TicketCard{ticket_type, fields{FieldValue{value,confidence,evidence{region,quote}}}, operation_sequence, safety_measures, warnings}`。
- **路由顺序门控（M2 定稿）**：线路专用关键词在前；`_PARSERS` 注册 7 票种；未注册防御分支报"解析器未注册"。
- **measures 表示（M2 定稿）**：`safety_measures` 独立容器，条目 `{no,text,evidence}`；remarks 照抽但不入真值（评测字段集 = truth.fields，card 侧恒多 remarks）。
- 规则 JSON schema：必填 `id/name/check_type/applies_to/basis{standard,...}`；**basis.standard 为空即拒载**（测试锁定）；`applies_to` 门控对全部 check_type 生效（测试锁定）。
- **签字链字段不进 required_field 参数（M2 定稿）**：工作票 issuer/permitor、抢修单 permitor 留空归 process_signature。
- 结论三级：`合规 / 不合规（低·一般·较大·重大）/ 待人工确认`；汇总键为中文 `"合规"/"不合规"/"待人工确认"`。
- 时间值统一转 ISO（`YYYY-MM-DDTHH:MM`）入卡；解析非法值（格式/日历越界）丢弃+warnings。
- **真值语义（M1 定稿）**：expect=check_type 粒度主期望；also_expect 只登记本仓已声明规则语义强制推出的隐含结论；评测按"全部非 pass 集合"对账（expected=expect∪also_expect；正常样例 expected=∅，任何非 pass 即误报）。
- **模板契约（M1 定稿）**：`{{key}}` 占位符 ↔ templates.json 注册表键一一对应（测试锁定）；缺失注入=保留『标签：』空值行；steps/measures 为生成器展开的多行块；truth.fields 不含被缺失注入的字段。
- **缺陷目录（M1 定稿）**：8 缺陷类型↔check_type 对齐 + 互斥矩阵（time_order×permit_time_out_of_range；missing_field×time_order（时间目标）；missing_field×permit_time_out_of_range（计划时间目标）；five_prevention×double_name_mismatch）+ 封顶（steps 2–10、measures 1–8、crew 1–5、组合≤2 缺陷）。
- M2 回归对账口径：35 份样例 truth↔card 全对账常驻（`test_generated_sample_parse_matches_truth` 等 3 组参数化测试）；`_covered_expected` 当前排除 permit_time_out_of_range（等 M3 许可区间规则）。
- 基准门槛：解析 F1≥0.95、误报 0、零 API（M4 承接全集对账）。
- 包布局 flat（repo 根直接 `py -m powerticket`）；core 零三方依赖，依赖只进 extras（web 含 python-multipart）。
- `.gitattributes` 全仓 `eol=lf`（fixtures 位级一致前提，勿动）；生成器写文件显式 LF。
- 真值/生成器漂移防线：`test_generator_matches_committed_files` 常驻比对内存产物与已提交文件，改模板/池子必须 `--force` 重生成再提交。
- 品牌隔离：不提姊妹项目业务；测试/数据全部虚构。

## 本机环境坑（实测）

- 仅 Python 3.8.8：`py` 启动（非 `python`）；代码保持 3.8 兼容（`from __future__ import annotations`，无 `X | Y` 运行时语法；`Path.write_text` 无 `newline` 参数，用 `open(..., newline="\n")`）。
- 一律 `py -X utf8`（控制台 GBK）；长任务 `PYTHONDONTWRITEBYTECODE=1`（pyc 偶发损坏）；怪错先清 `__pycache__`。
- pip 被系统代理污染：装包用 `NO_PROXY="*" no_proxy="*" py -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <pkg>`。
- Git Bash `/tmp` 与 Windows Python 不通：临时文件用仓库内路径（pytest tmp_path 用的是 Windows %TEMP%，无此问题）。
- 测试用 `py -m pytest`（保证 cwd 在 sys.path，flat 布局零安装可跑）。

## M2 DoD 核对

- [x] 7 票种解析器全覆盖，注册进 `_PARSERS`，布局依据 templates.txt + templates.json ✅
- [x] 路由补全（line_work_first/second）+ 顺序门控 + 路由负例测试（7 标题正例 + 交叉文本不误配）✅
- [x] 双时间行拆分（自…至… → plan_start/plan_end ISO）+ 许可/终结/抢修时间 ISO 化 ✅
- [x] measures 列表表示定稿（safety_measures 独立容器）并列入既定口径 ✅
- [x] dispatcher（发令人）抽取（operating/line_operating）✅
- [x] 合法性校验：非法时间/日历越界/空值一律丢弃+warnings ✅
- [x] 回归推广：truth.fields vs card.fields 全 35 份逐项对账 + 缺失断言 + 已覆盖期望触发 + 正常样例零误报 ✅
- [x] plan/00、04、05、06 回写 ✅
- [x] 全量测试 98 项全绿 + demo/check 实跑通过（7 票种抽样）✅
- [x] 本地提交（未推送）✅

## 关键命令速查

```bash
cd /d/ProgramData/zcode/power-operation-ticket-checker
py -X utf8 -m pytest                                  # 全量测试（98 项）
py -X utf8 -m powerticket demo                        # 端到端演示（operating）
py -X utf8 -m powerticket check data/samples/gen/gen-work_first-013-normal.txt
PYTHONDONTWRITEBYTECODE=1 py -X utf8 data/generator/generate.py --force   # 重生成样例（先清旧行）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 data/generator/generate.py --dry-run # 只打印清单
git status && git log --oneline -3                    # 提交前三核对（本仓库）
```
