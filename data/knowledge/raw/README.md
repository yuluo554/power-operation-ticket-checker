# data/knowledge/raw/ — 规范原文与来源台账（知识库第一层）

> 纪律（plan/05 §3）：入库渠道 fallback 官方 API > openstd/nea.gov.cn 直连 > 镜像；逐文件校验（魔数/大小）。
> 每条条文挂 `standard+clause+quote+channel+status`；**查不到原文 → status=待核对 + 登记渠道，不编造、不停摆**。
> 搜索通道可能被污染：摘要一律不采信，只用可直连官方原文核验。

## 文件清单

| 文件 | 内容 | status |
|---|---|---|
| nea-25fanCuo-2023.json + nea-25fanCuo-2023.pdf | 《防止电力生产事故的二十五项重点要求（2023版）》登记卡 + 官方原文 PDF（国家能源局官网附件直连下载，245 页，魔数/大小已校验）| **已核对**（§1.2.7 / §1.2.19 / §3.1.1 / §3.2.1 / §3.2.2 逐字誊录） |
| qgdw-1799.1-2013.json | 变电部分登记卡：4 张附录票样字段重构 + 时间栏目/第二种票适用范围/双重名称语义条目 | 待核对（条文原文未获取） |
| qgdw-1799.2-2013.json | 线路部分登记卡：同上线路版 | 待核对（条文原文未获取） |
| gb-26859-2011.json | 电力线路部分登记卡（openstd 在线图片版，机器可读条文未获取） | 待核对 |
| gb-26860-2011.json | 发电厂和变电站电气部分登记卡（hcno=3428089C6475E0B29FF38B8C6D8EC205 已验证） | 待核对 |
| dl-t-408-2023.json | 行业标准更新版登记卡（版本适用性待核对） | 待核对 |

## 格式约定

- 登记卡 = JSON：顶层 `standard/title/doc_type/channel/source_urls/acquisition/overall_status/clauses`。
- `clauses[]` 每条：`clause`（条款号或条款名）、`topic`、`text`（说明或原文）、`quote`（原文逐字摘录，
  **quote 非空的 status 必须是已核对**）、`channel`（该条获取渠道）、`status`（已核对/待核对）。
- 引用官方 PDF 逐字誊录时在 channel 注明页码；pypdf 提取的换行/页眉噪声已手工合并。
- 已核对条文仅限官方可直连原文（当前唯一来源：国家能源局 25 项反措 2023）；其余一律待核对。

## 下游

- 第二层：`py -X utf8 -m powerticket.knowledge.ingest` 从本目录确定性建块 → `../chunks/chunks.json`
  （`--check` 位级校验，常驻测试锁定）。
- 第三层：`../rules/rules-*.json` 每条规则的 `(basis.standard, basis.clause)` 必须能解析到本层产出的条文块。
