"""Dump catalog + last test run as JSON for tools/manuals/make_manuals.js.

    python -m qa.export out.json
"""
import json
import sys

from . import catalog, runner

if __name__ == "__main__":
    d = catalog.as_json()
    d["run"] = runner.last() or runner.run("EXPORT")
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        json.dump(d, f)
