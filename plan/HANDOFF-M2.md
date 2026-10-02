# HANDOFF-M2（M1 收尾交接快照）

> 写于 2026-10-02，M1（数据先行）收尾。下一里程碑：M2 解析层（7 票种全覆盖→参数卡）。新对话续接提示词：
> `/goal 读取 "D:\ProgramData\zcode\power-operation-ticket-checker\plan\HANDOFF-M2.md" 继续完成任务`

## 当前进度（M0+M1 已完成）

- plan/00–06 定稿；M0 骨架：CLI demo/parse/check 可用，run/report/web/benchmark 为诚实 stub（提示里程碑、exit 2）。
- **M1 交付**：
  - `data/ticket_templates/`：7 票种模板 txt（`{{key}}` 占位符布局）+ `templates.json` 字段注册表（每字段挂 source/status=待核对；附录编号两源分歧已记录；字段名重构偏差『工作班人员(不包括工作负责人)』→『工作班成员』已登记）。
  - `data/generator/`：`generate.py`（固定 seed=20261002，stdlib/3.8 兼容，`--force` 先清旧行+显式 LF）+ `defect_catalog.json`（8 缺陷类型↔7 check_type 对齐、4 条互斥注入矩阵、4 项多值封顶）。
  - `data/samples/gen/`：35 份样例（7 票种 × 1 正常 + 28 缺陷/组合）+ 35 份 truth.json + manifest.json，全部入仓。
  - 真值语义：expect=check_type 粒度主期望；also_expect 只登记已声明语义的隐含结论（当前唯一来源：missing_field 注入时间字段→time_order 待人工确认）。
  - 测试 39 项全绿（新增 tests/test_data_generator.py 15 项守门：模板完整性/确定性/真值语义/互斥矩阵/operating 回归）。
- **M1 附带修复（M0 潜伏 bug）**：`parse/operating.py` 字段正则 `\s*`→`[ \t]*`——`\s` 吃换行导致空值字段误抽下一行内容（生成器 missing-field 样例回归抓出）。
- 已提交本地 git（**未推送**，发布在 M6 经用户确认）。

## M2 待办（解析层：7 票种 → 参数卡）

1. 每票种一个 parser（`powerticket/parse/<type>.py`），注册进 `_PARSERS`；布局依据 `data/ticket_templates/*.txt` + 字段注册表 `templates.json`（label/role 就是解析槽位契约）。
2. **路由补全（有已知坑）**：`_TYPE_KEYWORDS` 现缺 line_work_first/line_work_second；且 `电力线路第一种工作票` 文本包含 `第一种工作票` 子串——**线路专用关键词必须排在通用关键词之前**（顺序门控），并加路由负例测试（7 票种标题各路由正确 + 交叉文本不误配）。
3. 双时间行解析：工作票 `计划工作时间：自…至…` 一行拆 plan_start/plan_end（ISO 入卡）；许可/终结时间同样 ISO 化。
4. measures 列表抽取：`safety_measures` 条目进参数卡的表示方式（fields 内 vs 独立容器）M2 定稿，定稿后列入既定口径。
5. dispatcher（发令人）抽取——真值已登记（operating/line_operating），M0 骨架解析器暂未抽。
6. 合法性校验：非法时间/空值一律丢弃+warnings（沿用 operating 现行为）。
7. 回归扩展：`tests/test_data_generator.py` 的 operating 对账测试推广到全部 7 票种（truth.fields vs card.fields 逐项对账 + 缺陷样例字段缺失断言 + time_order 规则触发 + 正常样例零误报）。

## 既定口径清单（动了会打挂基准/测试，先对照再改）

- 票种代码 7 个：`operating / line_operating / work_first / work_second / line_work_first / line_work_second / emergency_repair`（plan/04 §1）。
- 参数卡 schema v0.1：`TicketCard{ticket_type, fields{FieldValue{value,confidence,evidence{region,quote}}}, operation_sequence, warnings}`。
- 规则 JSON schema：必填 `id/name/check_type/applies_to/basis{standard,...}`；**basis.standard 为空即拒载**（测试锁定）；`applies_to` 门控对全部 check_type 生效（测试锁定）。
- 结论三级：`合规 / 不合规（低·一般·较大·重大）/ 待人工确认`；汇总键为中文 `"合规"/"不合规"/"待人工确认"`。
- 时间值统一转 ISO（`YYYY-MM-DDTHH:MM`）入卡；解析非法值丢弃+warnings。
- **真值语义（M1 定稿）**：expect=check_type 粒度主期望；also_expect 只登记本仓已声明规则语义强制推出的隐含结论；评测按"全部非 pass 集合"对账（expected=expect∪also_expect；正常样例 expected=∅，任何非 pass 即误报）。
- **模板契约（M1 定稿）**：`{{key}}` 占位符 ↔ templates.json 注册表键一一对应（测试锁定）；缺失注入=保留『标签：』空值行；steps/measures 为生成器展开的多行块；truth.fields 不含被缺失注入的字段。
- **缺陷目录（M1 定稿）**：8 缺陷类型↔check_type 对齐 + 互斥矩阵（time_order×permit_time_out_of_range；missing_field×time_order（时间目标）；missing_field×permit_time_out_of_range（计划时间目标）；five_prevention×double_name_mismatch）+ 封顶（steps 2–10、measures 1–8、crew 1–5、组合≤2 缺陷）。
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

## M1 DoD 核对

- [x] 7 票种模板+字段注册表，逐项挂出处（status=待核对，渠道留痕）✅
- [x] 生成器：固定 seed、正常/缺陷注入、expect/also_expect 真值、txt+truth.json+manifest ✅
- [x] `--force` 位级一致（跨次运行逐字节比对测试常驻）✅
- [x] 缺陷↔check_type 对齐清单、互斥注入矩阵、多值封顶参数（defect_catalog.json，生成器启动校验）✅
- [x] 样例集 35 份+真值；台账 100% 登记（data/README.md，来源/许可齐全）✅
- [x] operating 生成样例与现有解析器/规则引擎回归对账（含缺陷检出与零误报）✅
- [x] M0 解析器跨行抽取 bug 修复+回归锁定 ✅
- [x] plan/00、05、06 回写 ✅
- [x] 全量测试 39 项全绿 + demo 实跑通过 ✅
- [x] 本地提交（未推送）✅

## 关键命令速查

```bash
cd /d/ProgramData/zcode/power-operation-ticket-checker
py -X utf8 -m pytest                                  # 全量测试（39 项）
py -X utf8 -m powerticket demo                        # 端到端演示
py -X utf8 -m powerticket check data/samples/sample-operating-01.txt
PYTHONDONTWRITEBYTECODE=1 py -X utf8 data/generator/generate.py --force   # 重生成样例（先清旧行）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 data/generator/generate.py --dry-run # 只打印清单
git status && git log --oneline -3                    # 提交前三核对（本仓库）
```
