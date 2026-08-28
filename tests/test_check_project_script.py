"""Tests for the simplified project and release gates."""

from __future__ import annotations

import inspect
import unittest

from scripts import check_project, check_release_candidate


class TestCheckProjectScript(unittest.TestCase):
    """The executable gate retains every required independent-product check."""

    def test_product_gate_uses_direct_wheel_only(self) -> None:
        """The build path creates a wheel and explicitly rejects an sdist."""
        source = inspect.getsource(check_project._build_and_check_wheel)
        self.assertIn('"--wheel"', source)
        self.assertIn('"--no-isolation"', source)
        self.assertNotIn('"--sdist"', source)
        self.assertIn("*.tar.gz", source)
        self.assertIn("py3-none-any.whl", source)

    def test_product_gate_runs_all_routine_checks(self) -> None:
        """Tests, typing, lint, drift, wheel, and installed workflow stay present."""
        source = inspect.getsource(check_project.main)
        for marker in (
            "pytest",
            "mypy",
            "pyright",
            "pylint",
            "render_demo_extract_availability.py",
            "render_transaction_semantics_matrix.py",
            "render_readme_images.py",
            "_build_and_check_wheel",
            "_installed_wheel_smoke",
        ):
            self.assertIn(marker, source)

    def test_release_candidate_keeps_500x_and_demo_health(self) -> None:
        """The release gate composes the routine gate, demos, and unchanged scale."""
        source = inspect.getsource(check_release_candidate.main)
        self.assertIn("check_project.py", source)
        self.assertIn("check_audit_demo_health.py", source)
        self.assertIn("check_scale.py", source)
        self.assertIn('"500"', source)


if __name__ == "__main__":
    unittest.main()
