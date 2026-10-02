"""发布审计守门（M6）：脱敏四步脚本随全量测试与 CI 运行，任一步 FAIL 即红。"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "dessensitize_audit.py"


def test_desensitize_audit():
    r = subprocess.run(
        [sys.executable, "-X", "utf8", str(SCRIPT)],
        capture_output=True,
        timeout=120,
        cwd=str(ROOT),
    )
    out = r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")
    assert r.returncode == 0, out[-2000:]
    assert "DESSENSITIZE_AUDIT_OK" in out
