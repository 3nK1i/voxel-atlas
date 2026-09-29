#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    previous = ROOT / "scripts/run_phase6f_e_previous_regression.py"
    if not previous.is_file():
        print("PHASE6F_F_PREVIOUS_REGRESSION=FAIL")
        print(f"MISSING_PREVIOUS_GATE={previous}")
        return 2
    completed = subprocess.run([sys.executable, str(previous)], cwd=ROOT, check=False)
    if completed.returncode != 0:
        print(f"PHASE6F_E_PREVIOUS_REGRESSION_RC={completed.returncode}")
        print("PHASE6F_F_PREVIOUS_REGRESSION=FAIL")
        return completed.returncode
    print("PHASE6F_F_PREVIOUS_REGRESSION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
