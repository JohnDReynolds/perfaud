"""Tests that lock perfaud's established scale-gate boundaries."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import polars as pl

from scripts import check_scale


class TestScaleCheck(unittest.TestCase):
    """Scale construction and thresholds remain independent and unchanged."""

    def test_release_scale_uses_100x_reference_and_unchanged_caps(self) -> None:
        """The 500x gate warns at 5.25x and fails above 5.50x."""
        self.assertEqual(check_scale._large_site_caps(500), (5.25, 5.5))
        self.assertEqual(check_scale._REFERENCE_SCALE, 100)
        self.assertEqual(
            check_scale._large_site_result(500, 10.0, 52.5)[0],
            "PASS",
        )
        self.assertEqual(
            check_scale._large_site_result(500, 10.0, 52.6)[0],
            "WARN",
        )
        with self.assertRaisesRegex(RuntimeError, "5.50x failure boundary"):
            check_scale._large_site_result(500, 10.0, 55.1)

    def test_history_caps_are_unchanged(self) -> None:
        """The complete fivefold history warns above 1.75x and fails above 2x."""
        self.assertEqual(check_scale._history_result(10.0, 17.5)[0], "PASS")
        self.assertEqual(check_scale._history_result(10.0, 17.6)[0], "WARN")
        with self.assertRaisesRegex(RuntimeError, "2.00x failure boundary"):
            check_scale._history_result(10.0, 20.1)

    def test_baseline_records_the_same_release_contract(self) -> None:
        """The renamed observational baseline repeats the active gate values."""
        baseline = json.loads(
            Path("scripts/scale_baseline_500x.json").read_text(encoding="utf-8")
        )
        gate = baseline["established_gate"]
        self.assertEqual(gate["timing_reference_scale"], 100)
        self.assertEqual(gate["warning_ratio_at_500x"], 5.25)
        self.assertEqual(gate["failure_ratio_at_500x"], 5.5)

    def test_expansion_preserves_values_and_scales_portfolios(self) -> None:
        """Synthetic copies change only the portfolio identity."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.csv"
            pl.DataFrame(
                {"Portfolio Code": ["P1"], "Value": [123.45]}
            ).write_csv(path)
            expanded = check_scale._expanded_frame(path, 3)
        self.assertEqual(expanded.height, 3)
        self.assertEqual(expanded.get_column("Value").to_list(), [123.45] * 3)
        self.assertEqual(
            expanded.get_column("Portfolio Code").to_list(),
            ["P1", "P1_SCALE_001", "P1_SCALE_002"],
        )


if __name__ == "__main__":
    unittest.main()
