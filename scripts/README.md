# scripts 发布与审计脚本（M6 固化）

## dessensitize_audit.py —— 脱敏四步审计（发布门）

```bash
py -X utf8 scripts/dessensitize_audit.py    # 全过打印 DESSENSITIZE_AUDIT_OK，任一步 FAIL 非零退出
```

1. **跟踪文件名扫描**：`.env`/`.key`/`secret`/`token` 等禁入模式 + `.gitignore` 必配条目断言；
2. **内容级扫描**：全部跟踪文本文件 × 8 类模式（密钥字面值/密钥赋值/手机号/身份证号/个人路径/内网 IP/邮箱/内部域名）；
3. **跟踪二进制白名单**：sha256 逐个比对（与 `data/README.md` 数据台账联动；新二进制入仓 = 白名单+台账同步更新），zip 型容器逐条目扫描（含 docProps 元数据）；
4. **历史终验三扫**：`git log --all -p` 全文（线性历史下等价于逐提交逐树 grep）/ 全历史二进制对象核查（`rev-list --objects` ⊆ 白名单）/ 全部提交信息。

守门测试 `tests/test_release_audit.py` 随全量测试与 CI 运行。命中输出一律掩码化；
新豁免必须登记脚本内 `ALLOW` 表并写明理由。留档见 `plan/RELEASE-M6.md`。
