"""Write the takeover workbook of the ceramic factory demo (all sheets of ZIMPORT):
python tools/demo/ceramic_excel.py [file]   (default: NERP_Ceramic_Factory.xlsx)"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mm import demo_ceramic  # noqa: E402

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "NERP_Ceramic_Factory.xlsx"
    with open(out, "wb") as f:
        f.write(demo_ceramic.excel())
    print("Written:", out)
