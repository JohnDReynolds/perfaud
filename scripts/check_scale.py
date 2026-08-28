"""Run perfaud's unchanged large-site and long-history scale gates."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

import polars as pl

try:
    from scripts import audit_scale_contract
except ModuleNotFoundError:  # Direct script execution.
    import audit_scale_contract  # type: ignore[import-not-found, no-redef]


_ROOT = Path(__file__).resolve().parents[1]
_TEMPLATE = _ROOT / "src" / "perfaud" / "templates" / "axys_apx"
_ALLOWED_SCALES = (*range(10, 101, 10), 500, 1000)
_RELEASE_SCALE = 500
_REFERENCE_SCALE = 100
_WARNING_MULTIPLIER = 1.05
_FAILURE_MULTIPLIER = 1.10
_ROUTINE_DIVISOR = 7.64
_EXTREME_SCALE = 1000
_EXTREME_WARNING_RATIO = 85.0
_EXTREME_FAILURE_RATIO = 95.0
_HISTORY_SCALE = 5
_HISTORY_BLOCK_YEARS = 5
_HISTORY_WARNING_RATIO = 1.75
_HISTORY_FAILURE_RATIO = 2.00
_TIMEOUT_GRACE_SECONDS = 5.0


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse the selected large-site workload."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scale",
        type=int,
        choices=_ALLOWED_SCALES,
        default=10,
        help="Input multiplier; release candidates use 500.",
    )
    return parser.parse_args(argv)


def _large_site_caps(scale: int) -> tuple[float, float]:
    """Return the established warning and failure time ratios."""
    if scale == _EXTREME_SCALE:
        return _EXTREME_WARNING_RATIO, _EXTREME_FAILURE_RATIO
    expected = scale / _REFERENCE_SCALE if scale == _RELEASE_SCALE else 1 + scale / _ROUTINE_DIVISOR
    return expected * _WARNING_MULTIPLIER, expected * _FAILURE_MULTIPLIER


def _large_site_result(
    scale: int,
    reference_elapsed: float,
    scaled_elapsed: float,
) -> tuple[str, float, float, float]:
    """Evaluate the large-site timing without changing its boundaries."""
    if reference_elapsed <= 0:
        raise ValueError("Scale reference time must be greater than zero.")
    warning, failure = _large_site_caps(scale)
    ratio = scaled_elapsed / reference_elapsed
    if ratio > failure:
        raise RuntimeError(
            f"perfaud large-site exceeded the {failure:.2f}x failure boundary: "
            f"reference={reference_elapsed:.2f}s, scaled={scaled_elapsed:.2f}s, "
            f"ratio={ratio:.2f}x."
        )
    return ("WARN" if ratio > warning else "PASS", ratio, warning, failure)


def _history_result(
    baseline_elapsed: float,
    scaled_elapsed: float,
) -> tuple[str, float, float, float]:
    """Evaluate the unchanged fivefold long-history timing boundaries."""
    if baseline_elapsed <= 0:
        raise ValueError("History baseline time must be greater than zero.")
    ratio = scaled_elapsed / baseline_elapsed
    if ratio > _HISTORY_FAILURE_RATIO:
        raise RuntimeError(
            "perfaud long-history exceeded the "
            f"{_HISTORY_FAILURE_RATIO:.2f}x failure boundary: "
            f"baseline={baseline_elapsed:.2f}s, scaled={scaled_elapsed:.2f}s, "
            f"ratio={ratio:.2f}x."
        )
    return (
        "WARN" if ratio > _HISTORY_WARNING_RATIO else "PASS",
        ratio,
        _HISTORY_WARNING_RATIO,
        _HISTORY_FAILURE_RATIO,
    )


def _expanded_frame(path: Path, scale: int) -> pl.DataFrame:
    """Replicate source rows across distinct portfolio identifiers."""
    source = pl.read_csv(path)
    if "Portfolio Code" not in source.columns:
        return source
    copies = [source]
    for copy_number in range(1, scale):
        suffix = f"_SCALE_{copy_number:03d}"
        copies.append(
            source.with_columns(
                (pl.col("Portfolio Code").cast(pl.String) + suffix).alias(
                    "Portfolio Code"
                )
            )
        )
    return pl.concat(copies, how="vertical")


def _prepare_large_site(directory: Path, scale: int) -> tuple[Path, int]:
    """Create one isolated standard workspace at the requested input scale."""
    shutil.copytree(_TEMPLATE, directory)
    if scale == _EXTREME_SCALE:
        _limit_extreme_changed_rows(directory)
    rows = 0
    for snapshot in (directory / "input").iterdir():
        for path in snapshot.glob("*.csv"):
            expanded = _expanded_frame(path, scale)
            expanded.write_csv(path)
            rows += expanded.height
    (directory / "output").mkdir()
    return directory, rows


def _limit_extreme_changed_rows(workspace: Path) -> None:
    """Retain the 1000x input while keeping reviewer rows below the fixed ceiling."""
    snapshot_a = workspace / "input" / "snapshot_a"
    snapshot_b = workspace / "input" / "snapshot_b"
    for changed_path in snapshot_b.glob("*.csv"):
        baseline_path = snapshot_a / changed_path.name
        if not baseline_path.is_file():
            continue
        baseline = pl.read_csv(baseline_path)
        changed = pl.read_csv(changed_path)
        if "Portfolio Code" not in baseline.columns or "Portfolio Code" not in changed.columns:
            continue
        selected = ["BALANCED"]
        pl.concat(
            (
                changed.filter(pl.col("Portfolio Code").is_in(selected)),
                baseline.filter(~pl.col("Portfolio Code").is_in(selected)),
            )
        ).write_csv(changed_path)


def _shifted_history(source: pl.DataFrame, scale: int) -> pl.DataFrame:
    """Return chronologically shifted copies of one source table."""
    date_columns = [name for name in source.columns if name.endswith(" Date")]
    if not date_columns:
        return pl.concat([source] * scale, how="vertical")
    dated = source.with_columns(pl.col(name).str.to_date() for name in date_columns)
    return pl.concat(
        [
            dated.with_columns(
                pl.col(name).dt.offset_by(f"{copy * _HISTORY_BLOCK_YEARS}y")
                for name in date_columns
            )
            for copy in range(scale)
        ],
        how="vertical",
    )


def _prepare_history(directory: Path) -> tuple[Path, int, int]:
    """Create the established fivefold history with static security reference rows."""
    shutil.copytree(_TEMPLATE, directory)
    rows = 0
    static_rows = 0
    for snapshot in (directory / "input").iterdir():
        for path in snapshot.glob("*.csv"):
            source = pl.read_csv(path)
            if path.name == "secmast.csv":
                expanded = source
                static_rows += source.height
            else:
                expanded = _shifted_history(source, _HISTORY_SCALE)
            expanded.write_csv(path)
            rows += expanded.height
    (directory / "output").mkdir()
    return directory, rows, static_rows


def _run(workspace: Path, timeout: float = 300.0) -> float:
    """Run one complete workspace and return elapsed seconds."""
    started = time.perf_counter()
    result = subprocess.run(
        [sys.executable, "-m", "perfaud.cli", "run", str(workspace)],
        cwd=_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip())
    return time.perf_counter() - started


def _check_large_site(root: Path, scale: int) -> None:
    """Run timing, financial equivalence, and output checks at one scale."""
    baseline, baseline_rows = _prepare_large_site(root / "baseline", 1)
    scaled, scaled_rows = _prepare_large_site(root / "scaled", scale)
    baseline_elapsed = _run(baseline)
    reference_scale = _REFERENCE_SCALE if scale == _RELEASE_SCALE else 1
    reference = baseline
    reference_rows = baseline_rows
    reference_elapsed = baseline_elapsed
    if reference_scale != 1:
        reference, reference_rows = _prepare_large_site(root / "reference", reference_scale)
        reference_elapsed = _run(reference)
    _, failure = _large_site_caps(scale)
    scaled_elapsed = _run(
        scaled,
        timeout=reference_elapsed * failure + _TIMEOUT_GRACE_SECONDS,
    )
    for report_name in ("portfolio", "security"):
        baseline_report = baseline / "output" / report_name
        scaled_report = scaled / "output" / report_name
        audit_scale_contract.assert_scaled_audit_equivalent(
            baseline_report,
            scaled_report,
            scale,
        )
        audit_scale_contract.print_output_metrics(report_name, scaled_report)
    status, ratio, warning, failure = _large_site_result(
        scale,
        reference_elapsed,
        scaled_elapsed,
    )
    print(
        f"{status} perfaud large-site {scale}x: rows={reference_rows:,}->"
        f"{scaled_rows:,}; time={reference_elapsed:.2f}s->{scaled_elapsed:.2f}s; "
        f"ratio={ratio:.2f}x; warning>{warning:.2f}x; failure>{failure:.2f}x"
    )


def _check_history(root: Path) -> None:
    """Run the complete fivefold history and verify year coverage."""
    baseline, baseline_rows = _prepare_large_site(root / "history_baseline", 1)
    history, history_rows, static_rows = _prepare_history(root / "history")
    expected_rows = (baseline_rows - static_rows) * _HISTORY_SCALE + static_rows
    if history_rows != expected_rows:
        raise RuntimeError(
            f"History row count changed: expected={expected_rows}, actual={history_rows}."
        )
    baseline_elapsed = _run(baseline)
    history_elapsed = _run(
        history,
        timeout=baseline_elapsed * _HISTORY_FAILURE_RATIO + _TIMEOUT_GRACE_SECONDS,
    )
    for report_name in ("portfolio", "security"):
        baseline_findings = audit_scale_contract.read_supporting_csv(
            baseline / "output" / report_name,
            "findings.csv",
        )
        findings = audit_scale_contract.read_supporting_csv(
            history / "output" / report_name,
            "findings.csv",
        )
        baseline_years = set(
            baseline_findings.get_column("from_date").drop_nulls().dt.year().to_list()
        )
        expected_years = {
            year + copy * _HISTORY_BLOCK_YEARS
            for year in baseline_years
            for copy in range(_HISTORY_SCALE)
        }
        actual_years = set(
            findings.get_column("from_date").drop_nulls().dt.year().to_list()
        )
        if not expected_years.issubset(actual_years):
            raise RuntimeError(
                f"{report_name} history output is missing years: "
                f"{sorted(expected_years - actual_years)}"
            )
    status, ratio, warning, failure = _history_result(
        baseline_elapsed,
        history_elapsed,
    )
    print(
        f"{status} perfaud long-history {_HISTORY_SCALE}x: rows={baseline_rows:,}->"
        f"{history_rows:,}; time={baseline_elapsed:.2f}s->{history_elapsed:.2f}s; "
        f"ratio={ratio:.2f}x; warning>{warning:.2f}x; failure>{failure:.2f}x"
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run all applicable perfaud scale gates."""
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        with tempfile.TemporaryDirectory(prefix="perfaud_scale_") as directory:
            root = Path(directory)
            _check_large_site(root, args.scale)
            _check_history(root)
    except (RuntimeError, subprocess.SubprocessError) as error:
        print(f"Scale checks failed: {error}", file=sys.stderr)
        return 1
    print(f"perfaud scale checks passed at {args.scale}x.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
