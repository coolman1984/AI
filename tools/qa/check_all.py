"""All quality checks in one go (the same as the GitHub quality gate, without the
browser and desktop parts): unit / end-to-end tests, process test catalog, data
consistency of a fresh demo system, static check (if pyflakes is installed).
Usage:  python tools/qa/check_all.py      (exit code 1 = something is wrong)"""
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
results = []


def step(name, args, cwd=ROOT):
    t = time.time()
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    ok = r.returncode == 0
    results.append((name, ok, time.time() - t))
    print("%-38s %s  (%.0f s)" % (name, "OK" if ok else "FAILED", time.time() - t))
    if not ok:
        print((r.stdout + r.stderr)[-3000:])
    return ok


py = sys.executable
step("Unit and end-to-end tests", [py, "-m", "unittest", "discover", "-q"], os.path.join(ROOT, "tests"))
step("Process test catalog (QA runner)", [py, "-m", "qa.runner"])
step("Data consistency of a fresh demo system", [py, "-c",
     "import sys; sys.path.insert(0, 'tests'); import fixture; from mm import seed; from mm.db import connect; "
     "from qa.invariants import check; c = connect(':memory:'); seed.seed(c); v = check(c); print(v); sys.exit(1 if v else 0)"])
try:
    import pyflakes  # noqa: F401
    step("Static check (pyflakes)", [py, os.path.join("tools", "qa", "static_check.py")])
except ImportError:
    print("%-38s skipped (pip install pyflakes)" % "Static check (pyflakes)")
bad = [n for n, ok, _ in results if not ok]
print("\nALL CHECKS PASSED" if not bad else "\nFAILED: " + ", ".join(bad))
sys.exit(1 if bad else 0)
