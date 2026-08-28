"""Run the complete routine perfaud product gate."""

from __future__ import annotations

import os
from pathlib import Path
import site
import subprocess
import sys
import tempfile
import venv
import zipfile


_ROOT = Path(__file__).resolve().parents[1]


def _run(
    command: list[str | Path],
    *,
    cwd: Path = _ROOT,
    env: dict[str, str] | None = None,
) -> None:
    """Run one gate command and stop on failure."""
    normalized = [str(part) for part in command]
    print(f"==> {' '.join(normalized)}", flush=True)
    subprocess.run(normalized, cwd=cwd, check=True, env=env)


def _venv_command(environment: Path, name: str) -> Path:
    """Return an executable path inside a temporary virtual environment."""
    scripts = "Scripts" if os.name == "nt" else "bin"
    suffix = ".exe" if os.name == "nt" else ""
    return environment / scripts / f"{name}{suffix}"


def _build_and_check_wheel(directory: Path) -> Path:
    """Build, inspect, and Twine-check exactly one direct universal wheel."""
    _run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            directory,
        ]
    )
    wheels = list(directory.glob("*.whl"))
    if len(wheels) != 1 or not wheels[0].name.endswith("-py3-none-any.whl"):
        raise RuntimeError(f"Expected one universal wheel, found: {wheels}")
    if list(directory.glob("*.tar.gz")):
        raise RuntimeError("The direct-wheel gate must not create an sdist.")
    wheel = wheels[0]
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    if not any(name.startswith("perfaud/") for name in names):
        raise RuntimeError("Wheel does not contain the perfaud package.")
    forbidden = [
        name
        for name in names
        if name.startswith(("ppar/", "tests/", "scripts/")) or "/__pycache__/" in name
    ]
    if forbidden:
        raise RuntimeError(f"Wheel contains forbidden files: {forbidden}")
    required_resources = {
        "perfaud/templates/axys_apx/perfaud.yaml",
        "perfaud/templates/axys_apx/README.md",
        "perfaud/templates/axys_apx/input/snapshot_a/portperf.csv",
        "perfaud/templates/axys_apx/input/snapshot_b/portperf.csv",
    }
    if not required_resources.issubset(names):
        raise RuntimeError(
            f"Wheel is missing resources: {sorted(required_resources - names)}"
        )
    _run([sys.executable, "-m", "twine", "check", wheel])
    return wheel


def _installed_wheel_smoke(wheel: Path, directory: Path) -> None:
    """Run the installed package outside the checkout with no ppar available."""
    environment = directory / "venv"
    venv.EnvBuilder(with_pip=True).create(environment)
    python = _venv_command(environment, "python")
    pip = _venv_command(environment, "pip")
    _run([pip, "install", "--no-deps", wheel], cwd=directory)
    smoke = directory / "smoke"
    smoke.mkdir()
    workspace = smoke / "workspace"
    dependency_paths = site.getsitepackages()
    if not dependency_paths:
        raise RuntimeError("Could not locate the product-gate dependency environment.")
    smoke_env = os.environ.copy()
    smoke_env["PYTHONPATH"] = dependency_paths[0]
    code = (
        "from pathlib import Path; import importlib.util, perfaud; "
        "origin=Path(perfaud.__file__).resolve(); "
        "assert 'site-packages' in str(origin), origin; "
        "assert importlib.util.find_spec('ppar') is None; "
        "assert perfaud.__all__ == ['run', '__version__']; "
        "print(origin)"
    )
    _run([python, "-c", code], cwd=smoke, env=smoke_env)
    _run([python, "-m", "pip", "check"], cwd=smoke, env=smoke_env)
    _run([python, "-m", "perfaud.cli", "--version"], cwd=smoke, env=smoke_env)
    _run(
        [python, "-m", "perfaud.cli", "setup", workspace],
        cwd=smoke,
        env=smoke_env,
    )
    _run(
        [python, "-m", "perfaud.cli", "run", workspace],
        cwd=smoke,
        env=smoke_env,
    )
    artifacts = [path for path in (workspace / "output").rglob("*") if path.is_file()]
    if len(artifacts) != 10:
        raise RuntimeError(f"Installed workflow wrote {len(artifacts)} artifacts, not 10.")


def main() -> int:
    """Run tests, static checks, drift checks, and installed-wheel acceptance."""
    _run([sys.executable, "-m", "pytest", "-q"])
    _run(
        [
            sys.executable,
            "-m",
            "mypy",
            "src/perfaud",
            "scripts",
        ]
    )
    _run(
        [
            sys.executable,
            "-m",
            "pyright",
            "--pythonpath",
            sys.executable,
            "src/perfaud",
            "tests",
        ]
    )
    _run(
        [
            sys.executable,
            "-m",
            "pylint",
            "--errors-only",
            "src/perfaud",
            "scripts",
            "tests",
        ]
    )
    _run([sys.executable, "scripts/render_demo_extract_availability.py", "--check"])
    _run([sys.executable, "scripts/render_transaction_semantics_matrix.py", "--check"])
    _run([sys.executable, "scripts/render_readme_images.py", "--check"])
    with tempfile.TemporaryDirectory(prefix="perfaud_product_gate_") as directory:
        temporary = Path(directory)
        wheel = _build_and_check_wheel(temporary / "dist")
        _installed_wheel_smoke(wheel, temporary)
    print("perfaud product gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
