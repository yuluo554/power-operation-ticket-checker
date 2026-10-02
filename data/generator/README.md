# generator 数据生成器（M1）

程序化自制带真值数据是核心资产：固定 seed 可复现、可注入已知缺陷做配对评测（评测零成本重复）。

## 用法

```bash
py -X utf8 data/generator/generate.py                 # 生成到 data/samples/gen/（目录非空则拒绝）
py -X utf8 data/generator/generate.py --force         # 先清空输出目录再重生成（先清旧行）
py -X utf8 data/generator/generate.py --dry-run       # 只打印文件清单
py -X utf8 data/generator/generate.py --seed 20261002 # 指定种子（默认 20261002）
```

位级一致门：`--force` 重跑后 `git status` 零变化；`tests/test_data_generator.py` 常驻比对「内存产物 == 已提交文件」。

## 组成

- `generate.py`：生成器（stdlib，Python 3.8 兼容）。`build_all(seed)` 返回 `{文件名: 内容}` 内存态，`main()` 落盘（显式 LF，锁位级一致）。
- `defect_catalog.json`：缺陷类型↔check_type 对齐清单 + 互斥注入矩阵 + 多值封顶参数（机器可读，生成器启动即校验）。
- 输出：`gen-<票种>-<序号>-<缺陷>.txt` + 同名 `.truth.json` + `manifest.json`（每份样例的缺陷/期望/来源/许可，与 data/README.md 台账联动）。

## 真值语义（既定口径）

- **expect**：注入项的主期望结论，check_type 粒度（对齐 `defect_catalog.json`）。
- **also_expect**：同一注入由本仓**已声明规则语义**强制推出的其余非 pass 结论。当前唯一来源：`missing_field` 注入时间字段（start_time/end_time/plan_start/plan_end）→ `time_order` 因字段缺失判待人工确认=非 pass（M0 已实现）。**不对未实现的 M3 规则行为做猜测**。
- 评测（M4）按"文档全部非 pass 集合"对账：`expected = set(expect) | set(also_expect)`；正常样例 expected 为空集，任何非 pass 判定即误报。
- `fields`（时间 ISO）/`operation_sequence`/`safety_measures` 为**解析真值**（M2/M4 字段级 F1 对账）；被注入缺失的字段不出现在 fields；时间倒挂时真值照实登记票面所见（交换后）的值。
- 真值是 M2 解析器的目标规格：M0 骨架解析器只抽 operating 6 个规则字段（dispatcher 等字段属 M2 范围），M1 回归测试按"当前已声明字段"对账。

## 缺陷类型 ↔ check_type 对齐（详见 defect_catalog.json）

| 缺陷类型 | check_type | 状态 |
|---|---|---|
| missing_field（必填字段留空） | required_field | M0 已实现 |
| time_order（起止时间倒挂） | time_order | M0 已实现 |
| permit_time_out_of_range（许可时间越计划区间） | time_order | 规则 M3 |
| signature_gap（签发/许可签字缺环） | process_signature | 规则 M3 |
| ticket_type_mismatch（第二种票含需停电任务） | ticket_type_match | 规则 M3 |
| measure_missing（四要素缺一） | measure_coverage | 规则 M3 |
| five_prevention_violation（带负荷拉隔离开关） | five_prevention | 规则 M3 |
| double_name_mismatch（任务与操作项电压等级冲突） | consistency | 规则 M3 |

## 已知坑（plan/05 §2 预登记的落地方案）

1. **互斥坑**：`mutual_exclusions` 矩阵（4 条），计划先验校验不过即拒绝生成（`_validate_plans`）。
   - time_order × permit_time_out_of_range：同属时间域，归因不唯一；
   - missing_field × time_order（目标为时间字段时）：缺字段影响已由 also_expect 覆盖；
   - missing_field × permit_time_out_of_range（目标为计划时间字段时）：越界判定无基准；
   - five_prevention_violation × double_name_mismatch：均整体改写操作序列文本。
2. **多值封顶**：`caps`（操作序列 2–10 步、措施 1–8 条、班组成员 1–5 人、组合样例≤2 缺陷），构建期断言。
3. **先清旧行**：`--force` 才允许覆盖，覆盖前清空整个输出目录；文件写入显式 LF。
4. **结果语义**：每样本 `random.Random(f"{seed}:{票种}:{slug}")` 独立播种，样本顺序/增删不影响既有样本内容。

## 样例集构成（seed=20261002，35 份）

| 票种 | 正常 | 单缺陷 | 组合 |
|---|---|---|---|
| operating | 1 | 5（missing-start-time / missing-task / time-order / five-prevention / name-mismatch） | 1（missing-guardian × name-mismatch） |
| line_operating | 1 | 3（missing-end-time / time-order / five-prevention） | 1（missing-task × five-prevention） |
| work_first | 1 | 5（missing-task / missing-plan-end / permit-out-of-range / measure-missing / signature-gap-permitor） | 1（measure-missing × signature-gap） |
| work_second | 1 | 3（missing-crew / signature-gap-issuer / type-mismatch） | — |
| line_work_first | 1 | 4（missing-location / permit-out-of-range / measure-missing / signature-gap-permitor） | — |
| line_work_second | 1 | 2（missing-task / type-mismatch） | — |
| emergency_repair | 1 | 3（missing-crew / time-order / signature-gap-permitor） | — |

M3 规则入库后若新增 check_type 行为影响既有样例的隐含结论，先改 also_expect 口径再重生成（位级一致门会拦住未登记的漂移）。
