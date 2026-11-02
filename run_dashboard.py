"""
run_dashboard.py
----------------
Entry point to launch the Flask dashboard from the repo root.

Usage:
    python run_dashboard.py

The dashboard runs on http://127.0.0.1:5000
"""

import sys
from pathlib import Path

# Ensure the repo root is on sys.path so all package imports work
ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.app import app

if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=5000, use_reloader=False)

