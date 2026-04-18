"""Allow running as: python -m neuroncli"""

import sys
import os

# Fix Windows terminal encoding — MUST be before any print()
if sys.platform == "win32":
    os.system("")  # Enable ANSI escape codes on Windows
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from neuroncli.cli import main

raise SystemExit(main())
