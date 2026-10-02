# HANDOFF-M5（M4 收尾交接快照）

> **已过时仅作历史**（M5 已于 2026-10-02 完成，续接请读 [HANDOFF-M6.md](HANDOFF-M6.md)）。
>
> 写于 2026-10-02，M4（基准评测 + LLM 兜底）收尾。下一里程碑：M5 编排与交付（CLI run + docx 报告 + Web 面板）。新对话续接提示词：
> `/goal 读取 "D:\ProgramData\zcode\power-operation-ticket-checker\plan\HANDOFF-M5.md" 继续完成任务`

## 当前进度（M0–M4 已完成）

- plan/00–06 定稿；M0 骨架 + M1 数据先行 + M2 解析层 + M3 知识与规则（详见 HANDOFF-M4.md，其 M0–M3 段仍有效）。
- **M4 交付**：
  - **基准两脚本**（`powerticket/eval/`，实测 2026-10-02，data/samples/gen 35 份样例）：
    - `parse_f1.py`：字段级 P/R/F1 = **1.0**（463 评测项：0 误报 0 漏报）。口径：评测字段集=truth.fields（remarks 是唯一不入真值的已抽取字段，不计分）；标量逐键对账（错值=FP+FN），列表块（operation_sequence/safety_measures）按位对账（真值缺键视为空表）；微平均聚合；per_ticket_type 分票种计数。
    - `endtoend.py`：检出率 **1.0**（28/28 缺陷样例非 pass 集合==expect∪also_expect 精确对账）、误报率 **0**、判定准确率 **1.0**（35/35）；`failures` 明细（漏检/误报 check_type）便于定位。
    - 接口（**既定口径**）：`parse_f1.run(samples_dir=None)`、`endtoend.run(samples_dir=None, rules_path=None)`；两者 `main(argv)` 支持 `py -m powerticket.eval.<script>` 直跑；门槛 F1≥0.95、误报 0，未过退出码 1。
    - CLI `benchmark [--json]` 接真实现（stub 退役）；`--json` 输出纯净 JSON。
  - **LLM 兜底**（`powerticket/llm/`）：
    - `client.py`：DashScope qwen openai 兼容（决策 D-2 落地）：base_url 默认 `https://dashscope.aliyuncs.com/compatible-mode/v1`、`extra_body={"enable_thinking": False}`；默认模型 qwen-plus；`POWERTICKET_LLM_MODEL/BASE_URL/TIMEOUT` env 可覆盖；`DASHSCOPE_API_KEY` 走环境变量或仓库根 `.env`（零依赖 `load_dotenv`，.gitignore 已排除）；openai 懒加载、依赖仅 extras[llm]；任何不可用抛 `LLMUnavailable(reason)`（reason 属性可编程读取）。
    - `fallback.py`：`parse_ticket_with_fallback(text, allow_llm=False, extract_fn=None)`——规则优先（默认关闭，core 零 API）；解析失败+allow_llm → LLM 兜底，LLM 不可用 → ParseError 附降级说明；低置信度（<0.6）字段补抽：只补缺/替低置信度字段与空列表块，高置信度不动；**缺失字段不兜底**（缺失是合规信号，防掩盖缺陷）。`extract_via_llm(text, chat_fn=None)`：归一化 → LLM → `card_from_llm_response`（票种白名单校验、字段白名单、ISO 时间校验、**摘录逐字回验**——quote 非原文子串则该项不入卡；LLM_CONFIDENCE=0.7）→ 同一 TicketCard 出口 + warnings 留痕。
    - 编排接入：`pipeline.run_pipeline(text, rules_path=None, allow_llm_fallback=False)`；CLI `parse`/`check` 增 `--llm-fallback` 旗标。
    - **断供降级测试锁定**：无依赖/无密钥/网络断/坏响应 → 纯规则通路照常出卡出结论（tests/test_llm.py）。
  - 测试 **174 项全绿**（M3 为 145，+29：eval 9 + llm 16 + CLI 4）。
  - 已本地提交（未推送，发布在 M6 经用户确认）。

## M5 待办（编排与交付）

1. **CLI run 子命令**（`powerticket/cli.py`，现为 stub）：多票端到端与目录模式（目录批量 check → 汇总输出；保持 core 零依赖）。
2. **docx 报告导出**（`powerticket/report/`，python-docx，extras[report]）：报告结构见 plan/04 §5——结论汇总 → 分级问题清单 → 逐条证据（含原文摘录）→ 整改建议 → 签署栏；"待人工确认"独立成节；**无外链断言**进测试。
3. **Web 面板**（`powerticket/web/`，FastAPI，extras[web]）：上传 → 参数卡 → 结论 → 报告预览；前端 vendor 本地化，**页面 0 外链断言**进测试；Web 冒烟（真实上传 + 中文 JSON 路径）。
4. （可选，不阻塞）ticket_templates 附录编号两源分歧核对——Q/GDW 全文仍未公开获取，维持"待核对"即可，勿强行定稿。

## 既定口径清单（M4 新增/锁定部分；M0–M3 口径见 HANDOFF-M4.md，均仍有效）

- **基准口径**：parse_f1 评测字段集=truth.fields（remarks 不计分）+列表块按位对账+微平均；endtoend 沿用 M3 全集精确对账（命中=非 pass 集合==expect∪also_expect），检出率=精确命中缺陷样例/28、误报率=有误报样例/35（门槛 0）、判定准确率=完全正确样例/35。
- **基准纪律**：零 API 依赖可重复（纯规则通路，与 LLM 无关）；门槛 F1≥0.95、误报 0，CLI benchmark 未过退出码 1。
- **LLM 兜底纪律**：默认关闭（`allow_llm=False`）；触发=解析失败或字段低置信度（<0.6）；缺失字段不兜底；摘录逐字回验（quote 非原文子串不入卡）；ISO 时间校验；全链路 warnings 留痕；LLMUnavailable 一律降级纯规则通路（测试锁定）；LLM_CONFIDENCE=0.7、LOW_CONFIDENCE_THRESHOLD=0.6。
- **LLM 供应商（D-2 落地）**：DashScope qwen openai 兼容、enable_thinking=false、默认 qwen-plus；`DASHSCOPE_API_KEY` env 或 .env 不入仓；openai 懒加载仅 extras[llm]。
- M0–M3 口径（知识库出处纪律、检索接口、规则库三文件、time_order 双模式、ticket_type_match 缺失跳过、五防三口径、measure_coverage 四要素、全集精确对账、票种代码/schema v0.1/路由门控/measures 容器/结论三级/时间 ISO/真值语义/互斥矩阵/包布局/eol=lf）照 HANDOFF-M4.md 不变。

## 本机环境坑（实测，照 HANDOFF-M4.md 全部有效）

- 仅 Python 3.8.8：`py` 启动；`from __future__ import annotations`；`Path.write_text` 无 `newline` 参数（用 `open(..., newline="\n")`）。
- 一律 `py -X utf8`；长任务 `PYTHONDONTWRITEBYTECODE=1`；怪错先清 `__pycache__`。
- pip 被系统代理污染：`NO_PROXY="*" no_proxy="*" py -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <pkg>`。
- Git Bash `/tmp` 与 Windows Python 不通：临时文件用仓库内路径。
- 本机已装 pypdf 5.9.0 / pdfminer（25 反措 PDF 誊录用过，core 代码未依赖）；openai 未装（LLM 测试全离线注入假客户端，不依赖真网络）。

## M4 DoD 核对

- [x] 基准两脚本落地：parse_f1（F1=1.0）+ endtoend（检出 28/28、误报 0、准确率 35/35）✅
- [x] 门槛 F1≥0.95、误报 0，CLI benchmark 判门槛（未过退出码 1）✅
- [x] 基准零 API 依赖可重复（纯规则通路，无网络调用）✅
- [x] LLM 兜底：同一 TicketCard 出口 + warnings 留痕 + 摘录逐字回验 + 缺失字段不兜底 ✅
- [x] LLM 断供降级测试锁定（无依赖/无密钥/坏响应 → 纯规则通路照常出结论）✅
- [x] 密钥 .env 机制（零依赖 load_dotenv）+ openai 懒加载 extras[llm] ✅
- [x] README 指标回填 + 运行方式 + LLM 启用说明 ✅
- [x] plan/00/04/05/06 回写（D-2 落地）；HANDOFF-M5 本档 ✅
- [x] 全量测试 174 项全绿 ✅
- [x] 本地提交（未推送）✅

## 关键命令速查

```bash
cd /d/ProgramData/zcode/power-operation-ticket-checker
py -X utf8 -m pytest                                  # 全量测试（174 项）
py -X utf8 -m powerticket demo                        # 端到端演示（operating，4 规则全合规）
py -X utf8 -m powerticket benchmark                   # 内置基准（F1/检出率/误报率，门槛判定）
py -X utf8 -m powerticket benchmark --json            # 基准机器可读输出
py -X utf8 -m powerticket check data/samples/gen/gen-operating-004-time-order.txt
py -X utf8 -m powerticket check <票>.txt --llm-fallback   # LLM 兜底（需 .[llm] + DASHSCOPE_API_KEY）
py -X utf8 -m powerticket.knowledge.ingest --check    # chunks 位级校验
PYTHONDONTWRITEBYTECODE=1 py -X utf8 data/generator/generate.py --force   # 重生成样例
git status && git log --oneline -3                    # 提交前三核对（本仓库）
```
