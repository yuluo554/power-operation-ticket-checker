# HANDOFF-M6（M5 收尾交接快照）

> 写于 2026-10-02，M5（编排与交付）收尾。下一里程碑：M6 发布（干净环境验证 + 脱敏 + GitHub 公开 + 收尾固化）。新对话续接提示词：
> `/goal 读取 "D:\ProgramData\zcode\power-operation-ticket-checker\plan\HANDOFF-M6.md" 继续完成任务`

## 当前进度（M0–M5 已完成）

- plan/00–06 定稿；M0 骨架 + M1 数据先行 + M2 解析层 + M3 知识与规则 + M4 基准与 LLM 兜底（详见 HANDOFF-M5.md，其 M0–M4 段仍有效）。
- **M5 交付**（2026-10-02）：
  - **CLI run 子命令**（`powerticket/cli.py`，stub 退役）：
    - 单票模式：`run <票>.txt`（人读明细，同 demo 形态）；`--json` 纯净 JSON（提示文案走 stderr）；`--report <x.docx>` 同时导报告（目标为已存在目录时拒绝，防误写）。
    - 目录模式：`run <目录>` 批量处理 `*.txt`（排序遍历），逐票 `[通过]/[问题]` 行含票种、三级计数、非 pass 规则 id，失败票 `[失败]` 行注明原因**不中断整批**；结尾 `== 批量汇总 ==`；退出码：0 全部处理成功 / 1 存在处理失败 / 2 路径或参数错误。`--report <目录>` 每票一份 docx（先探测 extras[report]，避免处理到一半失败）。
    - core 通路零三方依赖不变。
  - **docx 报告导出**（`powerticket/report/`）：
    - `sections.py`：`build_report_sections(result, meta=None)` **零依赖纯函数**——章节序：元信息 → 一、结论汇总 → 二、分级问题清单（重大/较大/一般/低排序，RISK_ORDER）→ 三、逐条证据（含原文摘录：参数卡 fields/操作序列/安全措施的 evidence.quote 逐字）→ 四、整改建议 → 五、待人工确认（独立成节，解析告警一并列入）→ 六、签署栏（审核人/复核人/批准人空签表）。`overall_verdict` 三级总判定。
    - `docx_render.py`（extras[report] 懒加载）：`render_docx_report(result, out_path, meta)` / `render_docx_report_bytes(...)`（Web 下载用）/ `ensure_docx_available()`（批量前置探测）；中文字体宋体（失败不抛）。
    - `find_external_links(data) -> list`（`__init__.py`，零依赖）：**报告无外链判据**三条——`<w:hyperlink>` 元素 / rels `TargetMode="External"` / document.xml 正文 `<w:t>` 含 `http(s)://`；xmlns 命名空间 URI 不计（判据自证测试：合成含 URL 伪 docx 必须被检出）。
    - 纪律：报告依据只取 standard+clause+status+quote，**登记渠道 channel 不入报告**；章节结构纯函数被 Web 预览复用，**预览即所得**。
  - **Web 面板**（`powerticket/web/`，FastAPI extras[web]）：
    - `app.py`：`create_app()` 工厂；端点 GET `/`（内联单页）、GET `/healthz`、POST `/api/check`（multipart 上传 → run_pipeline → JSON；解析失败 422 + 中文 error）、POST `/api/report-preview`（sections JSON，与 docx 同源）、POST `/api/report`（docx 下载；缺 extras[report] 503 + 安装提示）。**/docs、/redoc 显式关闭**（Swagger UI 引 CDN，与 0 外链冲突）。
    - `static/index.html`：**零依赖内联单页**（vanilla JS + inline CSS，无任何外部资源引用；原拟 Vue3/PDF.js vendor 已由决策表替代）——上传→参数卡（字段/操作序列/安全措施/告警）→结论（三级 chips+结论表）→报告预览+docx 下载（a.download 命名中文文件名）。
    - **坑（实测）**：`from __future__ import annotations` 下 FastAPI 端点签名 `UploadFile` 前向引用必须在**模块级**可解析——放 `create_app()` 局部导入会 PydanticUserError（app.py 顶部有注释说明）。
    - CLI `web` 子命令：懒加载 uvicorn+create_app，缺依赖友好提示退出码 2；`--host/--port` 可配。
  - 测试 **203 项全绿**（M4 为 174，+29：report 10 + web 10 + CLI 9）。关键断言：报告无外链（真样例 + 合成判据自证）、页面 0 外链（`http(s)://`/`<link>`/外部 src 全禁）、Web 冒烟（真实 multipart 上传 + 中文文件名 + 中文 JSON 原样输出断言）、预览/docx 章节同源、extras 缺失降级友好提示。
  - 实跑演示均已过：批量 35 份（7 合规/28 有问题/0 失败）、单票+批量 docx 生成、真 uvicorn curl 冒烟（healthz/首页/上传/docx 下载）。
  - 已本地提交（未推送，发布在 M6 经用户确认）。

## M6 待办（发布）

1. **干净环境验证**：新 clone + 新 venv 按 README 一次跑通（pytest / demo / benchmark / run / report / web 冒烟；extras[report]/[web] 安装路径验证）。
2. **脱敏四步 + 终验三扫全 0**（姊妹项目方法论：密钥/内网地址/个人路径/真实人员设备信息；scripts/ 审计脚本）。
3. **GitHub 公开**：发布前与用户确认（决策 D-3：用户现有账号，M6 统一发布；发布前不对外宣称）；tag + release。
4. **收尾固化**：README 终稿、plan/00/05/06 回写、发布后 GitHub 全新 clone 复核。
5. （可选，不阻塞）ticket_templates 附录编号两源分歧核对——Q/GDW 全文仍未公开获取，维持"待核对"即可，勿强行定稿。

## 既定口径清单（M5 新增/锁定部分；M0–M4 口径见 HANDOFF-M5.md，均仍有效）

- **报告章节序**：元信息 → 一、结论汇总 → 二、分级问题清单（按风险等级）→ 三、逐条证据（含原文摘录）→ 四、整改建议 → 五、待人工确认（独立成节）→ 六、签署栏；报告无外链（find_external_links 三判据）；channel 不入报告；预览即所得（sections 纯函数共用）。
- **Web 0 外链**：内联单页无任何外部引用 + /docs /redoc 关闭；断言进测试。
- **CLI run 退出码**：0 全部成功 / 1 存在处理失败（整批不中断）/ 2 路径或参数错误；--json 纯净 JSON（提示走 stderr）。
- **前端形态决策**：零依赖内联单页替代 Vue3/PDF.js vendor（plan/06 M5 行）；FastAPI future-annotations + UploadFile 模块级导入坑记录在案。
- M0–M4 口径（基准口径/基准纪律/LLM 兜底纪律/LLM 供应商 D-2/知识库出处纪律/检索接口/规则库三文件/time_order 双模式/ticket_type_match 缺失跳过/五防三口径/measure_coverage 四要素/全集精确对账/票种代码/schema v0.1/路由门控/measures 容器/结论三级/时间 ISO/真值语义/互斥矩阵/包布局/eol=lf）照 HANDOFF-M5.md 不变。

## 本机环境坑（实测，照 HANDOFF-M5.md 全部有效）

- 仅 Python 3.8.8：`py` 启动；`from __future__ import annotations`；`Path.write_text` 无 `newline` 参数（用 `open(..., newline="\n")`）。
- 一律 `py -X utf8`；长任务 `PYTHONDONTWRITEBYTECODE=1`；怪错先清 `__pycache__`。
- pip 被系统代理污染：`NO_PROXY="*" no_proxy="*" py -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <pkg>`。
- Git Bash `/tmp` 与 Windows Python 不通：临时文件用仓库内路径。
- **M5 新增**：fastapi 0.124.4 + pydantic 2.10 + starlette TestClient(httpx 0.27) 在 3.8 可用（pip 自动解析兼容版本）；future-annotations × FastAPI UploadFile 必须模块级导入（见上）。

## M5 DoD 核对

- [x] CLI run 子命令落地：单票+目录批量（35 份一次跑通），--json/--report，core 零依赖 ✅
- [x] docx 报告导出落地：章节结构定稿（plan/04 §5 + plan/06 决策），待人工确认独立成节，原文摘录逐字 ✅
- [x] 报告无外链断言进测试（find_external_links 三判据 + 判据自证）✅
- [x] Web 面板落地：上传→参数卡→结论→报告预览/docx 导出 ✅
- [x] 页面 0 外链断言进测试；/docs /redoc 关闭，断网可演示 ✅
- [x] Web 冒烟：真实 multipart 上传 + 中文 JSON 原样输出（TestClient + 真 uvicorn curl 双验）✅
- [x] README 回写（M5 章节+命令+状态）；plan/00/04/05/06 回写（含两新决策）；HANDOFF-M6 本档 ✅
- [x] 全量测试 203 项全绿 + benchmark 回归全过 ✅
- [x] 本地提交（未推送）✅

## 关键命令速查

```bash
cd /d/ProgramData/zcode/power-operation-ticket-checker
py -X utf8 -m pytest                                  # 全量测试（203 项）
py -X utf8 -m powerticket demo                        # 端到端演示（operating，4 规则全合规）
py -X utf8 -m powerticket benchmark                   # 内置基准（F1/检出率/误报率，门槛判定）
py -X utf8 -m powerticket run data/samples/gen        # 目录批量审核（35 份）
py -X utf8 -m powerticket run data/samples/gen --report reports/   # 批量+逐票 docx
py -X utf8 -m powerticket report data/samples/gen/gen-operating-005-five-prevention.txt  # 单票报告
py -X utf8 -m powerticket web                         # Web 面板 http://127.0.0.1:8000
py -X utf8 -m powerticket.knowledge.ingest --check    # chunks 位级校验
PYTHONDONTWRITEBYTECODE=1 py -X utf8 data/generator/generate.py --force   # 重生成样例
git status && git log --oneline -3                    # 提交前三核对（本仓库）
```
