# RELEASE-M6（发布留档，2026-10-02）

> 发布门留档：干净环境验证、脱敏四步、GitHub 公开动作时序、发布后复核。
> 留档纪律：敏感字面值一律占位符指代，不复述（含提交作者邮箱）。

## §1 干净环境验证（发布门核心）✅

方式：开发机本机新目录 `git clone`（`D:\ProgramData\zcode\potc-m6-clean`，与开发目录隔离）+
全新 `py -m venv`（Python 3.8.8 + 自带 pip 20.2.3），逐条照 README 快速开始执行。

| 验证项 | 命令 | 结论 |
|---|---|---|
| EOL 门（autocrlf=true 全局） | clone 后 `git status` | ✅ 检出工作区零变化（`.gitattributes eol=lf` 守住） |
| demo / check / run / benchmark | venv python 直跑，core 零安装 | ✅ 全过；批量 35 份（7 合规/28 问题/0 失败）；F1 1.0、检出 28/28、误报 0、门槛全过 |
| 位级一致 | `data/generator/generate.py --force` 后 `git status` | ✅ 重生成 71 文件零变化 |
| extras 安装 | venv 内 `pip install -e ".[dev,report,web]"`（清华镜像+NO_PROXY） | ✅ 依赖全部从公共 registry 解析 |
| 全量测试 | venv 内 pytest | ✅（修复后）204 项全绿 0 跳过 |
| 报告 | `report`（单票）+ `run --report`（批量） | ✅ 35 份 docx；`find_external_links` 全 0 |
| Web 真进程 | venv 内 `powerticket web --port 8011` + Python urllib 冒烟 | ✅ healthz/首页 0 外链/真实 multipart 上传（中文 JSON 原样）/docx 下载 0 外链 |

### 干净环境抓回的问题（均已修复+加回归测试）

1. **extras[dev] 缺 httpx**（TestClient 的测试期依赖，fastapi 不传递安装）：
   `tests/test_web.py` 的 `pytest.importorskip("httpx")` 在缺依赖时整模块静默跳过——
   开发机全局装过 httpx 所以全绿（203 项），干净 venv 与 CI 只有 194 项，**CI 一直在漏跑 web 测试**。
   修复：`extras[dev]` 补 `httpx>=0.24` + `test_package.py::test_extras_cover_test_dependencies`
   守门（extras 必须覆盖测试期 import）+ CI 安装改 `.[dev,web,report]`（web/report 测试常驻）。
   提交 52dff75。
2. **Python 3.8 自带 pip 20.2.3 无法可编辑安装 pyproject-only 项目**（报"editable mode
   currently requires a setup.py based build"）：README 快速开始补 `pip install -U pip` 前置行。
   提交 2e2c473。

验证后修订：venv 自升级 pip 20.2.3 → 25.0.1 顺利（未触发姊妹项目记录的 venv pip 段错误坑）。

## §2 脱敏四步 + 终验三扫 ✅

固化脚本：`scripts/dessensitize_audit.py`（守门测试 `tests/test_release_audit.py` 随全量测试与 CI）。
终态运行结论（2026-10-02）：

```
== 脱敏四步审计 ==（跟踪文件 162 个）
[步骤1][OK] 跟踪文件名 0 命中；.gitignore 覆盖 6 项必配条目
[步骤2][OK] 内容级扫描 161 个文本文件，8 类模式全部 0 命中
[步骤3][OK] 跟踪二进制 1 个，全部在白名单且 sha256 与台账登记一致
[步骤4][OK] 历史终验三扫全 0：log -p 全文 / 全历史二进制对象 / 提交信息
DESSENSITIZE_AUDIT_OK
```

- 步骤1：跟踪文件无 `.env`/`.key`/secret/token 类命名；`.gitignore` 覆盖 .env/密钥/个人材料/运行产物。
- 步骤2：8 类模式（密钥字面值/密钥赋值/手机号/身份证/个人路径/内网 IP/邮箱/内部域名）在 161 个文本文件 0 命中。
  初扫时手机号模式曾命中政府官网 PDF 附件 URL 的数字段（`data/knowledge/` 来源台账特意留存的公开出处），
  加词边界后归零——属预期误报，未入 ALLOW 豁免表。
- 步骤3：唯一跟踪二进制为官方 25 反措 PDF（公开发布的政府文件，data/README.md 台账已登记），
  sha256 与白名单一致；无 docx/xlsx 类容器入仓。
- 步骤4：全历史（10 提交）文本内容并集、全部提交信息 0 命中；历史二进制对象 ⊆ 白名单。

脚本固化过程记录（两处实测修正）：
1. Windows `git ls-files` 中文路径默认八进制转义——脚本统一 `-c core.quotepath=false`；
2. email 模式宽松版会把 `git log -p` 的 diff 前缀符 `+` 吞进本地部分、误报 `@pytest.fixture`
   类测试代码——收紧为"首字符字母数字 + 域名至少两段"，历史复扫归零。

### 提交作者元信息（专项）

全历史 10 个提交的作者邮箱为**个人 QQ 邮箱**（真实个人信息，内容级扫描不覆盖提交元数据）。
处置：发布前改写为 GitHub noreply 地址 + 本地 git config 同步（用户已确认，见 §3）；
历史改写后重跑四步审计复核。

## §3 GitHub 公开（待发布后回填）

- [x] 用户确认（2026-10-02，对话内三问三答）：公开仓库 yuluo554/power-operation-ticket-checker（MIT 随仓）、
  提交邮箱全历史改写 GitHub noreply（12 提交，filter-branch env-filter + reflog expire + gc aggressive，
  改写后旧邮箱字面值 log -p/提交信息 0 残留，审计/205 测试复跑全绿）、tag v0.1.0 + release + topics 全部执行
- [x] 建仓+推送（2026-10-02）：`gh repo create --public`（description 中英双语）；
  推送走 SSH remote（git 主机别名形式，不展开字面 URL）——gh token 无 workflow scope
  且历史含 `.github/workflows/`，HTTPS 推送必被拒（方法论实录坑，SSH 不受 OAuth scope 限制），实测一次通过
- [x] tag + release（2026-10-02）：`git tag -a v0.1.0`（打在发布提交 565ee17）+ push tag；
  `gh release create v0.1.0`（notes：基准表/快速体验命令/extras 依赖分层/质量门/免责声明）
- [x] topics（2026-10-02）：8 个（compliance/document-parsing/nlp/operation-ticket/power-systems/python/
  rule-engine/work-ticket），`gh api` 回读确认生效；description/visibility/MIT license 元信息同回读核验
- [x] CI 首跑核验（2026-10-02）：main 与 v0.1.0 两次 push 触发，5 矩阵作业（ubuntu 3.8/3.9/3.11/3.13 +
  windows 3.11）全部 success（本轮 CI 已改装 `.[dev,web,report]`，web/report 测试在 CI 常驻）

## §4 发布后复核 ✅（2026-10-02）

- [x] GitHub 全新 clone（`potc-gh-verify`，SSH clone 自远端）：HEAD==发布提交 565ee17、工作区零变化
  （EOL 门在 GitHub 检出同样守住）→ 四步审计 DESSENSITIZE_AUDIT_OK（历史三扫对已发布历史全 0）+
  205 项测试全绿 + 基准门槛全过 + demo 通过
- [x] `gh api` 元信息核验：public / MIT / topics 8 个 / description 双语；README 渲染核验
  （Accept: application/vnd.github.html）：3 表格、演示命令、F1 数值、mermaid 图均正常渲染
- [x] plan/00/05/06 回写（M6 ✅ + D-1/D-3 落定）+ 本档 §3/§4 回填，随收尾提交推送（正常开发流）

### 收尾提交实测插曲（如实留痕）

首版收尾提交因本档写了 SSH remote 字面 URL（git@ 主机形式触发 email 模式）致脱敏审计 FAIL，
且因 `审计 | tail` 管道吃退出码而照常提交推送（方法论既录坑再次实测命中，守门测试进 CI 的价值
当即兑现：该推送的 CI 必红）。处置 = 留档措辞占位化 + amend + `git push --force-with-lease`
（新仓库无协作者，安全；tag v0.1.0 指向的发布提交不受影响）+ CI 复核。教训：发布链上的长命令
一律单独跑、直接看退出码，不接管道。
