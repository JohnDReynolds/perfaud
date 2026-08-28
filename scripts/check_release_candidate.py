"""Run the complete perfaud release-candidate gate."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


_ROOT = Path(__file__).resolve().parents[1]


def _run(*arguments: str) -> None:
    """Run one release gate with the active project interpreter."""
    command = [sys.executable, *arguments]
    print(f"==> {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=_ROOT, check=True)


def main() -> int:
    """Run routine, demo-health, and unchanged 500x acceptance gates."""
    _run("scripts/check_project.py")
    _run("scripts/check_audit_demo_health.py")
    _run("scripts/check_scale.py", "--scale", "500")
    print("perfaud release-candidate gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
