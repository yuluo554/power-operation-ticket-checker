# HANDOFF-M1（M0 收尾交接快照）

> **已过时仅作历史**（M1 已于 2026-10-02 完成，续接请读 [HANDOFF-M2.md](HANDOFF-M2.md)）。
>
> 写于 2026-10-02，M0（计划+骨架）收尾。下一里程碑：M1 数据先行。新对话续接提示词：
> `/goal 读取 "D:\ProgramData\zcode\power-operation-ticket-checker\plan\HANDOFF-M1.md" 继续完成任务`

## 当前进度（M0 已完成）

- plan/00–06 全部定稿（02 需求解读 / 03 架构选型 / 04 模块详设 / 05 数据与里程碑 / 06 决策记录）。
- 可运行骨架：包 `powerticket`（flat 布局，core 零三方依赖），CLI 子命令 demo/parse/check 可用，run/report/web/benchmark 为诚实 stub（提示里程碑、exit 2）。
- 端到端通路：清洗→票种路由→operating 解析器（demo 样例 6 字段+5 步序列，全带证据）→规则引擎（required_field/time_order 两 check_type+applies_to 门控+无出处拒载）→三级结论汇总。
- 测试 24 项全绿（`py -X utf8 -m pytest`），demo 实跑通过；CI 就绪（.github/workflows/ci.yml，本地未推送）。
- 已提交本地 git（**未推送**，发布在 M6 经用户确认）。

## M1 待办（数据先行）

1. `data/ticket_templates/`：7 票种模板（字段清单重构自 Q/GDW 1799.1/1799.2 附录票样结构，逐项挂出处）。
2. `data/generator/`：生成器（固定 seed；正常/植入缺陷；真值 expect/also_expect；输出 txt+truth.json；--force 位级一致）。
3. `data/samples/`：扩充样例集+真值；台账登记每份数据（来源/许可）。
4. 缺陷类型与 check_type 对齐清单；互斥注入矩阵；多值封顶参数。
5. 更新 plan/05 里程碑回写、data/README.md 登记表。

## 既定口径清单（动了会打挂基准/测试，先对照再改）

- 票种代码 7 个：`operating / line_operating / work_first / work_second / line_work_first / line_work_second / emergency_repair`（plan/04 §1）。
- 参数卡 schema v0.1：`TicketCard{ticket_type, fields{FieldValue{value,confidence,evidence{region,quote}}}, operation_sequence, warnings}`。
- 规则 JSON schema：必填 `id/name/check_type/applies_to/basis{standard,...}`；**basis.standard 为空即拒载**（测试锁定）；`applies_to` 门控对全部 check_type 生效（测试锁定）。
- 结论三级：`合规 / 不合规（低·一般·较大·重大）/ 待人工确认`；汇总键为中文 `"合规"/"不合规"/"待人工确认"`。
- 时间值统一转 ISO（`YYYY-MM-DDTHH:MM`）入卡；解析非法值丢弃+warnings。
- 真值语义：`expect` 主期望 + `also_expect` 隐含结论，按"全部非 pass 集合"对账。
- 基准门槛：解析 F1≥0.95、误报 0、零 API。
- 包布局 flat（repo 根直接 `py -m powerticket`）；core 零三方依赖，依赖只进 extras（web 含 python-multipart）。
- `.gitattributes` 全仓 `eol=lf`（M1 冻结 fixtures 位级一致的前提，勿动）。
- 品牌隔离：不提姊妹项目业务；测试/数据全部虚构。

## 本机环境坑（实测）

- 仅 Python 3.8.8：`py` 启动（非 `python`）；代码保持 3.8 兼容（`from __future__ import annotations`，无 `X | Y` 运行时语法）。
- 一律 `py -X utf8`（控制台 GBK）；长任务 `PYTHONDONTWRITEBYTECODE=1`（pyc 偶发损坏）；怪错先清 `__pycache__`。
- pip 被系统代理污染：装包用 `NO_PROXY="*" no_proxy="*" py -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <pkg>`。
- Git Bash `/tmp` 与 Windows Python 不通：临时文件用仓库内路径。
- 测试用 `py -m pytest`（保证 cwd 在 sys.path，flat 布局零安装可跑）。

## M0 DoD 核对

- [x] plan/00–06 定稿，文档索引/里程碑/决策回写 ✅
- [x] 骨架端到端可演示（demo 输出参数卡+结论+依据+汇总）
- [x] 测试全绿（24 项，含失败路径：空输入/无法识别/未实现票种/缺文件/坏规则/未知 check_type/门控负例）
- [x] CI 就绪（矩阵：ubuntu 3.9/3.11/3.13 + ubuntu-22.04 3.8 + windows 3.11）
- [x] data 台账登记 demo 样例与演示规则（含"待核对"status）
- [x] .gitattributes/.gitignore/LICENSE/pyproject 就绪
- [x] 本地提交（未推送）

## 关键命令速查

```bash
cd /d/ProgramData/zcode/power-operation-ticket-checker
py -X utf8 -m pytest                                  # 全量测试（24 项）
py -X utf8 -m powerticket demo                        # 端到端演示
py -X utf8 -m powerticket check data/samples/sample-operating-01.txt
py -X utf8 -m powerticket parse data/samples/sample-operating-01.txt
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m pytest        # 长任务防 pyc 损坏
git status && git log --oneline -3                    # 提交前三核对（本仓库）
```
