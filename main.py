# ------------------------------------------------------------
# Real-Time AI Security System — Web Dashboard
# Run: python main.py
# Open: http://127.0.0.1:5000
# ------------------------------------------------------------

import os
import sys
import webbrowser
from threading import Timer

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app import app, engine


def open_browser():
    webbrowser.open("http://127.0.0.1:5000")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    print("=" * 52)
    print("  Real Time Security — Web Mode")
    print("=" * 52)
    print(f"  Device: {engine.device.upper()}")
    print(f"  Authorized faces loaded: {len(engine.authorized_encodings)}")
    print(f"  Open dashboard: http://127.0.0.1:{port}")
    print("  Click 'Start Secure Camera' in the browser to begin.")
    print("=" * 52)

    Timer(1.5, open_browser).start()

    try:
        app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
    finally:
        engine.close()
