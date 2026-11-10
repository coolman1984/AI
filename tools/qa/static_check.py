"""Static check for CI: pyflakes on every Python file; fails on real problems
(undefined names, syntax errors, duplicate arguments ...) and ignores style-only
messages (unused imports / variables)."""
import subprocess
import sys

IGNORE = ("imported but unused", "is assigned to but never used", "redefinition of unused",
          "unable to detect undefined names", "f-string is missing placeholders")
files = subprocess.run(["git", "ls-files", "*.py"], capture_output=True, text=True).stdout.split()
out = subprocess.run([sys.executable, "-m", "pyflakes"] + files, capture_output=True, text=True)
bad = [l for l in (out.stdout + out.stderr).splitlines() if l.strip() and not any(i in l for i in IGNORE)]
print("\n".join(bad) or "pyflakes: no problems in %d files" % len(files))
sys.exit(1 if bad else 0)
