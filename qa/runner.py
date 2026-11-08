"""Automatic test run of all processes (screen ZQA_TEST, CLI below).

Runs the unit and end-to-end tests of tests/ on a freshly seeded in-memory
system (the productive database is never touched), maps every result to the
test cases of the catalog and returns / stores the test log.

    python -m qa.runner            -> prints the summary, writes exports/qa_last_run.json
"""
import datetime
import json
import os
import sys
import time
import unittest

from . import catalog

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(ROOT, "tests")
LAST = os.path.join(ROOT, "exports", "qa_last_run.json")


class _Collect(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.res = {}
        self._t0 = {}

    def startTest(self, test):
        self._t0[test.id()] = time.time()
        super().startTest(test)

    def _set(self, test, status, msg=""):
        self.res[test.id()] = dict(status=status, msg=msg[-600:],
                                   ms=int((time.time() - self._t0.get(test.id(), time.time())) * 1000))

    def addSuccess(self, test):
        self._set(test, "P")

    def addFailure(self, test, err):
        self._set(test, "F", self._exc_info_to_string(err, test))

    def addError(self, test, err):
        self._set(test, "E", self._exc_info_to_string(err, test))

    def addSkip(self, test, reason):
        self._set(test, "S", reason)


def run(user="QA"):
    if TESTS not in sys.path:
        sys.path.insert(0, TESTS)
    t0 = time.time()
    for name in [m for m in sys.modules if m.startswith("test_")]:
        del sys.modules[name]           # fresh test modules = fresh sample system every run
    suite = unittest.defaultTestLoader.discover(TESTS, top_level_dir=TESTS)
    res = _Collect()
    suite.run(res)
    tests = res.res
    procs, total, passed = [], 0, 0
    mapped = set()
    for p in catalog.PROCESSES:
        cases = []
        for cid, title, tcodes, expected, ids in p["cases"]:
            parts = []
            for i in ids:
                mapped.add(i)
                parts.append(dict(id=i, **tests.get(i, dict(status="E", msg="test not found", ms=0))))
            st = "P" if all(x["status"] == "P" for x in parts) else "F"
            total += 1
            passed += st == "P"
            cases.append(dict(id=cid, title=title, tcodes=tcodes, expected=expected, status=st,
                              actual="As expected" if st == "P" else
                              "; ".join(x["msg"].strip().splitlines()[-1] for x in parts if x["status"] != "P"),
                              ms=sum(x["ms"] for x in parts), tests=parts))
        ok = sum(c["status"] == "P" for c in cases)
        procs.append(dict(id=p["id"], name=p["name"], module=p["module"], cases=cases, passed=ok,
                          total=len(cases)))
    unmapped = sorted(set(tests) - mapped)
    out = dict(run_at=datetime.datetime.now().isoformat(timespec="seconds"), user=user,
               seconds=round(time.time() - t0, 1), unit_tests=len(tests),
               unit_passed=sum(v["status"] == "P" for v in tests.values()),
               cases=total, passed=passed, failed=total - passed, processes=procs, unmapped=unmapped)
    os.makedirs(os.path.dirname(LAST), exist_ok=True)
    with open(LAST, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    return out


def last():
    try:
        with open(LAST, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


if __name__ == "__main__":
    r = run("CLI")
    for p in r["processes"]:
        print("%-4s %-28s %2d / %2d" % (p["id"], p["name"], p["passed"], p["total"]))
        for c in p["cases"]:
            if c["status"] != "P":
                print("     FAIL %s %s: %s" % (c["id"], c["title"], c["actual"]))
    print("cases %d/%d passed, unit tests %d/%d, %.1fs, unmapped: %s"
          % (r["passed"], r["cases"], r["unit_passed"], r["unit_tests"], r["seconds"], r["unmapped"]))
    sys.exit(0 if r["failed"] == 0 else 1)
