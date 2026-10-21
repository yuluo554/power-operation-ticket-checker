"""发布审计守门（M6）：脱敏四步脚本随全量测试与 CI 运行，任一步 FAIL 即红。

2026-10-22 二次迭代：脚本正名为 desensitize_audit.py（旧名多一个 s，已订正），
并新增 --selftest（阳性/阴性双对照）——单靠「rc=0 + 含 OK 标记」的断言无法
发现脚本退化成只 print 一行，故补 test_selftest_reports_all_controls。
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "desensitize_audit.py"


def _run(*args):
    r = subprocess.run(
        [sys.executable, "-X", "utf8", str(SCRIPT), *args],
        capture_output=True,
        timeout=120,
        cwd=str(ROOT),
    )
    out = r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")
    return r.returncode, out


def test_desensitize_audit():
    rc, out = _run()
    assert rc == 0, out[-2000:]
    assert "DESSENSITIZE_AUDIT_OK" in out


def test_selftest_reports_all_controls():
    """门有自证：--selftest 必须真的跑出反证，不能只打一行 OK。"""
    rc, out = _run("--selftest")
    assert rc == 0, out[-2000:]
    assert "DESENSITIZE_SELFTEST_OK" in out
    control_lines = [ln for ln in out.splitlines() if ln.startswith(("PASS ", "FAIL "))]
    assert len(control_lines) >= 5, out
    assert not [ln for ln in control_lines if ln.startswith("FAIL ")], out
    # 阳性与阴性都必须存在（只跑阳性 = 门只验「能抓」，不验「不乱抓」）
    assert any(ln.startswith("PASS 阳性") for ln in control_lines), out
    assert any(ln.startswith("PASS 阴性") for ln in control_lines), out
