"""脱敏四步审计（M6 发布门，ai-tool-project-sprint 阶段7 固化）。

四步：
  1. 跟踪文件名扫描（.env/.key/secret/token 等）+ .gitignore 覆盖断言；
  2. 内容级扫描全部跟踪文本文件（密钥/密钥赋值/手机号/身份证/个人路径/内网IP/邮箱/内部域名）；
  3. 跟踪二进制白名单（sha256 与 data/README.md 数据台账联动；zip 型逐条目扫描）；
  4. 历史终验三扫：
     a. `git log --all -p` 全文（全部提交的文本内容并集，线性历史下等价于逐树 grep）；
     b. 全历史二进制对象核查（rev-list --objects，二进制扩展名路径必须 ⊆ 白名单）；
     c. 全部提交信息。

任一步 FAIL 非零退出；全部通过打印 DESSENSITIZE_AUDIT_OK。
守门测试 tests/test_release_audit.py 随全量测试与 CI 运行。
留档纪律：审计输出对命中内容掩码化，本脚本与留档文档均不复述真实敏感字面值；
新豁免必须登记 ALLOW 并写明理由。
运行：py -X utf8 scripts/dessensitize_audit.py
"""
import hashlib
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 内容级检测模式（通用防泄漏面；命中即 FAIL）。键=模式名（作命名组）。
# email 收紧原因：宽松版会把 diff 前缀符 + 吞进本地部分，误报 @pytest.fixture 类代码。
PATTERNS = {
    "api_key": r"sk-[A-Za-z0-9]{8,}",
    "key_assign": r"(?i:api_?key|secret|passwd|password|token)\s*[=:]\s*['\"]?[A-Za-z0-9+/_-]{12,}",
    "phone": r"\b1[3-9]\d{9}\b",
    "idcard": r"\b\d{17}[\dXx]\b",
    "personal_path": r"[C-Fc-f]:[\\/]+[Uu]sers[\\/]+[^\x00-\x1f\\/:*?\"<>|\s]+",
    "intranet_ip": r"\b(?:10\.\d{1,3}|192\.168\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3})\.\d{1,3}\b",
    "email": r"\b[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+\b",
    "internal_domain": r"\b[\w.-]+\.(?:local|intranet|corp|internal)\b",
}
_COMBINED = "|".join(f"(?P<{k}>{v})" for k, v in PATTERNS.items())

# 步骤1：跟踪文件名禁入模式
NAME_PATTERN = re.compile(
    r"\.(?:env|key|pem|p12|pfx)$|secret|token|password|credential|id_rsa", re.I
)

# .gitignore 必须覆盖的条目（防运行产物/密钥/个人材料误入仓）
GITIGNORE_REQUIRED = [".env", "*.key", "*_private/", "reports/", "output/", "*.log"]

# 步骤3：跟踪二进制白名单 path -> sha256（与 data/README.md 数据台账联动；
# 新二进制入仓 = 白名单 + 台账同步更新，否则此处 FAIL）
BIN_WHITELIST = {
    "data/knowledge/raw/nea-25fanCuo-2023.pdf": "9ba52f104a9054879e80fc75a91d9d50712e5893927e5e78d4e7392951daa4ea",
}
BIN_EXT = {".pdf", ".docx", ".xlsx", ".zip", ".png", ".jpg", ".jpeg", ".gif"}
# zip 型容器：逐条目解压扫描（不只主文档，docProps/core.xml 元数据是真实姓名重灾区）
ZIP_EXT = {".docx", ".xlsx", ".zip"}

# 步骤2 文件级豁免：(相对路径, 模式名) -> 理由。当前为空；新增必须留档。
ALLOW = {}


def git(*args):
    # core.quotepath=false：Windows 下中文路径默认被八进制转义加引号，无法还原成实际文件名
    r = subprocess.run(
        ["git", "-c", "core.quotepath=false"] + list(args), cwd=str(ROOT), capture_output=True
    )
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败: {r.stderr.decode('utf-8', 'replace')}")
    return r.stdout.decode("utf-8", "replace")


def scan_text(name, text):
    """返回 [(模式名, 位置描述)]；命中内容掩码化，不复述敏感字面值。"""
    hits = []
    for pat_name, pattern in PATTERNS.items():
        if (name, pat_name) in ALLOW:
            continue
        for m in re.finditer(pattern, text):
            line_no = text.count("\n", 0, m.start()) + 1
            hits.append((pat_name, f"{name}:{line_no}"))
    return hits


def step1_tracked_names(tracked):
    bad = [f for f in tracked if NAME_PATTERN.search(Path(f).name)]
    if bad:
        print(f"[步骤1][FAIL] 跟踪文件名命中禁入模式: {bad}")
        return False
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
    missing = [e for e in GITIGNORE_REQUIRED if e not in gi]
    if missing:
        print(f"[步骤1][FAIL] .gitignore 缺少覆盖条目: {missing}")
        return False
    print(f"[步骤1][OK] 跟踪文件名 0 命中；.gitignore 覆盖 {len(GITIGNORE_REQUIRED)} 项必配条目")
    return True


def step2_content(tracked):
    hits = []
    scanned = 0
    for f in tracked:
        p = ROOT / f
        if p.suffix.lower() in BIN_EXT or not p.is_file():
            continue  # 二进制归步骤3
        scanned += 1
        hits.extend(scan_text(f, p.read_bytes().decode("utf-8", "replace")))
    if hits:
        print(f"[步骤2][FAIL] 内容级扫描 {scanned} 个文本文件命中 {len(hits)} 处：")
        for pat, loc in hits[:20]:
            print(f"  [{pat}] {loc}")
        return False
    print(f"[步骤2][OK] 内容级扫描 {scanned} 个文本文件，{len(PATTERNS)} 类模式全部 0 命中")
    return True


def step3_binaries(tracked):
    bins = [f for f in tracked if (ROOT / f).suffix.lower() in BIN_EXT]
    fails = []
    ledger = (ROOT / "data" / "README.md").read_text(encoding="utf-8")
    for f in bins:
        digest = hashlib.sha256((ROOT / f).read_bytes()).hexdigest()
        if f not in BIN_WHITELIST:
            fails.append(f"{f} 不在二进制白名单（新二进制入仓 = 白名单+data/README.md 台账同步）")
            continue
        if BIN_WHITELIST[f] != digest:
            fails.append(f"{f} sha256 与白名单不一致（文件已变动，需重登台账并更新白名单）")
            continue
        if f.startswith("data/") and Path(f).name not in ledger:
            fails.append(f"{f} 在白名单但 data/README.md 数据台账未登记")
        if (ROOT / f).suffix.lower() in ZIP_EXT:
            with zipfile.ZipFile(ROOT / f) as z:
                for info in z.infolist():
                    for pat, _loc in scan_text(
                        f"{f}!{info.filename}", z.read(info).decode("utf-8", "replace")
                    ):
                        fails.append(f"[{pat}] {f}!{info.filename}")
    if fails:
        print("[步骤3][FAIL] 二进制白名单/扫描问题：")
        for x in fails:
            print("  " + x)
        return False
    extra = "；zip 型逐条目扫描 0 命中" if any(Path(f).suffix.lower() in ZIP_EXT for f in bins) else ""
    print(f"[步骤3][OK] 跟踪二进制 {len(bins)} 个，全部在白名单且 sha256 与台账登记一致{extra}")
    return True


def step4_history():
    # 4a：git log --all -p 全文。--format 去掉作者头（提交邮箱属账号元信息，不在内容
    # 脱敏范围，否则 email 模式必误报）；线性历史下补丁并集 == 全部文本内容并集。
    log_all = git("log", "--all", "--format=commit %H", "-p")
    hits = [(m.lastgroup or "?", log_all.count("\n", 0, m.start()) + 1)
            for m in re.finditer(_COMBINED, log_all)]
    if hits:
        print(f"[步骤4][FAIL] git log -p 全文命中 {len(hits)} 处（模式:行号）：{hits[:10]}")
        return False
    # 4b：全历史二进制对象必须 ⊆ 白名单路径（含已删除的二进制也要有台账交代）
    hist_bins = set()
    for line in git("rev-list", "--all", "--objects").splitlines():
        parts = line.split(" ", 1)
        if len(parts) == 2 and Path(parts[1]).suffix.lower() in BIN_EXT:
            hist_bins.add(parts[1])
    stray = hist_bins - set(BIN_WHITELIST)
    if stray:
        print(f"[步骤4][FAIL] 历史中存在白名单外的二进制路径: {sorted(stray)}")
        return False
    # 4c：提交信息
    msgs = git("log", "--all", "--format=%s%n%b")
    m_hits = [p for p in PATTERNS if re.search(PATTERNS[p], msgs)]
    if m_hits:
        print(f"[步骤4][FAIL] 提交信息命中模式: {m_hits}")
        return False
    print("[步骤4][OK] 历史终验三扫全 0：log -p 全文 / 全历史二进制对象 / 提交信息")
    return True


def main():
    tracked = [f for f in git("ls-files").splitlines() if f.strip()]
    print(f"== 脱敏四步审计 ==（跟踪文件 {len(tracked)} 个）")
    ok = step1_tracked_names(tracked)
    ok = step2_content(tracked) and ok
    ok = step3_binaries(tracked) and ok
    ok = step4_history() and ok
    if not ok:
        print("DESSENSITIZE_AUDIT_FAIL")
        return 1
    print("DESSENSITIZE_AUDIT_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
