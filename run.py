"""Start MM Core:   python run.py   [--port 8080] [--reset] [--no-browser]

--reset       delete the database and load fresh demo data
--empty       start with an empty database (no demo data)
"""
import argparse
import os
import sys
import threading
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mm import seed  # noqa: E402
from mm.db import DEFAULT_DB, connect  # noqa: E402
from web.server import serve  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="MM Core - inventory management")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--empty", action="store_true")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    db_path = os.environ.get("MM_DB") or DEFAULT_DB
    if a.reset and os.path.exists(db_path):
        os.remove(db_path)
        print("Database deleted:", db_path)
    conn = connect(db_path)
    if not a.empty and seed.seed(conn) is not None:
        print("Demo data loaded.")
    conn.close()
    httpd = serve(a.host, a.port)
    url = "http://%s:%d" % ("localhost" if a.host in ("127.0.0.1", "0.0.0.0")
                            else a.host, a.port)
    print("MM Core is running:  %s   (press Ctrl+C to stop)" % url)
    if not a.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
