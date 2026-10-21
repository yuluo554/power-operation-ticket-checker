# Changelog

本文件记录本仓的对外变更。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [0.2.0] — 2026-10-22

> **行为变更**：依据待核对的规则不再产出确定性「不合规」结论。
> 这是本仓第一次让 `basis.status` 真正参与判定，属可感知的行为变更，故升 minor。

### 修复

- **发布物不自足（发布前拦下）**：`data/`（规则库 39 条 / 样例 71 文件 / 模板 / 知识库 26 块，
  2.0 MB / 97 文件）从未进入构建产物，而所有模块都用
  `Path(__file__).parents[2] / "data"` 定位 —— 装成 wheel 后该路径指向 `<venv>/Lib`，
  `demo` 直接 `文件不存在: .../site-packages/data/samples/sample-operating-01.txt`。
  源码态与 editable 安装都正常，所以历年测试一直是绿的。
  - 新增 `powerticket/paths.py`：解析顺序 `POWERTICKET_DATA_DIR` 环境变量 →
    源码态（上溯找 `data/knowledge/rules`）→ `<prefix>/share/powerticket`。
  - `pyproject.toml` 加 `[tool.setuptools.data-files]`，把 7 个数据子目录装到
    `<prefix>/share/powerticket/`（不用 `package-data` —— `data/` 不在包目录下）。
  - 5 处调用点（`cli` / `rules` / `eval.parse_f1` / `eval.endtoend` /
    `knowledge.ingest` / `knowledge.retrieval`）改走 `paths.sub(...)`。
  - 新增 `tests/test_packaging.py`（6 项）：源码态解析、env 覆盖、关键数据齐备、
    `data-files` 覆盖全部子目录、**禁止再出现 `parents[N] / "data"` 写法**、版本守门仍在。
  - CI 新增 `packaging` 作业：真 `python -m build` → 装 wheel 到全新 venv（**不用 `-e`**）
    → 在**仓库外的中立目录**跑 `demo`/`benchmark`/`ingest --check`，并断言
    `powerticket.__file__` 在 site-packages、`data_dir()` 落在 `share/` 下；
    另加 sdist 解包检查确认 `data/` 随源码包分发。
- **依据闸（P0）**：`run_checks` 此前对 `basis.status` 零消费 —— 30 条「待核对」规则
  照常产出「合规」（30/30）与「不合规」（15/15），而 `plan/04:70`、`plan/04:100`、
  README §限制 三处都写着不该这样。现改为：在 `check()` 之后、`conclusions.extend()` 之前，
  把非「已核对」规则的「不合规」结论一律降级为「待人工确认」；「合规」结论保留。
  - 实测：35 份样例共 36 条非 pass 结论，其中 25 条（69%）来自待核对规则；
    闸后「待核对规则产出不合规」= **0**，benchmark 四项**完全不变**。
  - 闸门位置刻意放在 `check()` 之后 —— 若改成「跳过规则不执行」，
    `required_field` 的缺失检测会整块消失（字段缺失本身就是判据）。
  - 新增 `tests/test_pending_gate.py`（阳性降级 / 阴性不降级 / 不吞缺失检测 /
    合规保留 / 生产全量 0 违规 / 30 条待核对守卫）。
- **脱敏门可空转**：`scripts/dessensitize_audit.py`（拼写错误，三个 s）→
  `scripts/desensitize_audit.py`。新增 `--selftest` 阳性 4 + 阴性 6 双对照；
  `tests/test_release_audit.py` 增加「selftest 必须报出全部反证」断言 ——
  此前脚本退化成 `print` 一行仍会被判绿。
- **email 模式误报**：`git@github.com` 形态的 SSH 远端地址被判为个人邮箱，
  加 `(?!git@)` 负向断言（真实邮箱仍被抓到）。
- **版本守门形同虚设**：`tests/test_package.py` 原为 `assert powerticket.__version__`
  （非空字符串即过）。改为与 `pyproject.toml` 的 `[project].version` 真比对。

### 新增

- **复核锚**：6 份 raw 登记卡加 `reviewed_at` / `next_review` / `review_interval`；
  39 条规则的 `basis` 加 `review_due`。此前「已待核对 N 天」不会被任何机器发现。
  新增 `tests/test_review_anchor.py`（逾期**只警告不改退出码**）。
- **`generate.py --check`**：与已提交样例集逐字节对账（不写盘，并把目录里多出的文件
  也算差异），一致输出 `GEN_CHECK_OK 71 个产物逐字节一致`。已接入 CI。

### 变更

- **`requires-python` 3.8 → 3.12**。3.8 已于 2024-10 EOL，且当前 PyPI 上
  fastapi / uvicorn / python-multipart / pytest 全部要求 ≥3.10。
- **CI 矩阵 5 腿 → 4 腿**：`{ubuntu-latest, windows-latest} × {3.12, 3.13}`。
  删掉 EOL 的 `ubuntu-22.04 × 3.8` 与 `ubuntu-latest × 3.9`，补上原本缺失的 3.12 腿，
  保留 3.13 以维持前向兼容验证。
- **PEP 639**：`license = { text = "MIT" }` → `license = "MIT"` + `license-files = ["LICENSE"]`；
  `setuptools>=61` → `>=77`；删 `License :: OSI Approved :: MIT License` classifier
  （PEP 639 下该写法已弃用）。wheel 元数据现为 `Metadata-Version: 2.4` +
  `License-Expression: MIT`，构建零弃用警告。
- **`actions/checkout@v4` → `@v7`、`actions/setup-python@v5` → `@v7`**：
  CI 的 Node20 弃用 warning 注解清零。
- **`addopts = "-q"` → `"-p no:cacheprovider"`**：`-q` 与命令行 `-q` 叠加成 `-qq`
  会让 pytest 的「N passed」汇总行整行消失。
- **README 首屏与 §内置基准**：明写「39 条规则中 30 条（77%）依据待核对」，
  并把「检出率 1.0 的构成」（36 条非 pass 里 25 条来自待核对规则，真实可确定性判定
  只有 11 条）写进基准表下。
- **`/openapi.json` 保留并声明**（纯 JSON 描述、无外部资源，断网可演示不受影响），
  来源是此前 `app.py` 只关了 `docs_url`/`redoc_url` 而 README 一字未提。
- **README 补退出码纪律**：判定退出码时不要加管道（`| tail` 会把后者的 0 当成命令的退出码）。

### 移除

- 空目录 `code/`（0 文件、未跟踪）。

### 数据

- `data/samples/gen` 71 个文件、`data/knowledge/chunks/chunks.json`（26 块）、
  `data/knowledge/raw/nea-25fanCuo-2023.pdf` —— **一字节未变**（`generate.py --check`
  71/71 逐字节一致；`ingest --check` 通过）。
- 39 条规则的 `basis.status`（已核对 9 / 待核对 30）与 6 份登记卡的 `overall_status`
  一个未动 —— 把「待核对」改成「已核对」是造假，本轮有两条测试专门守这个红线。

### 测试

- 205 → **223 passed**（新增 `test_pending_gate.py` 6 项、`test_packaging.py` 6 项、
  `test_review_anchor.py` 5 项、`test_release_audit.py` 1 项；`test_package.py` 与
  `test_rules.py` 为改断言非新增）。
- 8 个既有测试因依据闸需要调整：`test_rules.py` 7 个改用内存副本显式化「依据已核对」前提
  （断言仍是 `== "不合规"`，**未放宽**为 `in (不合规, 待人工确认)`）；
  `test_cli.py` 1 个改为断言真实行为（不合规 0 / 待人工确认 1）。

## [0.1.0] — 2026-10-02

首个公开发布：7 票种解析、39 条规则全 7 类 check_type、知识库三层、
内置基准（F1 1.0 / 误报 0）、CLI + docx 报告 + Web 面板、脱敏四步全 0。
