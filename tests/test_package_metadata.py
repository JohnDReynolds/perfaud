"""Tests for perfaud identity, packaging, and repository independence."""

from __future__ import annotations

import ast
from dataclasses import fields
from importlib import metadata, resources
from pathlib import Path
import tomllib
from typing import Any
import unittest

import perfaud
from perfaud.workspace import RunResult


_ROOT = Path(__file__).resolve().parents[1]


class TestPackageMetadata(unittest.TestCase):
    """The extracted product has one coherent public and packaged identity."""

    def test_project_identity_is_perfaud(self) -> None:
        """Distribution metadata names only the independent Audit product."""
        project = _pyproject()["project"]
        self.assertEqual(project["name"], "perfaud")
        self.assertEqual(project["version"], "0.1.0")
        self.assertEqual(project["scripts"], {"perfaud": "perfaud.cli:main"})
        self.assertEqual(
            project["urls"]["Repository"],
            "https://github.com/JohnDReynolds/perfaud",
        )
        self.assertEqual(perfaud.__version__, metadata.version("perfaud"))

    def test_runtime_dependencies_are_complete_and_independent(self) -> None:
        """The base install contains the whole workflow without product extras."""
        project = _pyproject()["project"]
        dependencies = project["dependencies"]
        self.assertEqual(
            {dependency.split(">=")[0] for dependency in dependencies},
            {"polars", "openpyxl", "pyyaml"},
        )
        self.assertNotIn("ppar", " ".join(dependencies).lower())
        self.assertEqual(set(project["optional-dependencies"]), {"dev"})

    def test_root_exports_only_run_and_version(self) -> None:
        """Focused APIs stay in their owning modules instead of the root."""
        self.assertEqual(perfaud.__all__, ["run", "__version__"])
        self.assertTrue(callable(perfaud.run))
        for obsolete in (
            "Specification",
            "ComparisonViews",
            "RunResult",
            "write_report_bundle",
            "compare_snapshots",
        ):
            self.assertFalse(hasattr(perfaud, obsolete))

    def test_run_result_contract_is_exact(self) -> None:
        """The workspace result is frozen and has exactly three fields."""
        self.assertEqual(
            [field.name for field in fields(RunResult)],
            ["workspace", "output_directory", "artifacts"],
        )
        self.assertTrue(getattr(RunResult, "__dataclass_params__").frozen)

    def test_templates_are_data_only_resources(self) -> None:
        """The installed resource tree is complete and contains no Python runner."""
        template = resources.files("perfaud").joinpath("templates", "axys_apx")
        names = sorted(item.name for item in template.iterdir())
        self.assertEqual(
            names,
            ["README.md", "demo_extract_availability.yaml", "input", "perfaud.yaml"],
        )
        for snapshot in ("snapshot_a", "snapshot_b"):
            csv_names = sorted(
                item.name
                for item in template.joinpath("input", snapshot).iterdir()
                if item.is_file()
            )
            self.assertEqual(
                csv_names,
                [
                    "holdings.csv",
                    "portperf.csv",
                    "secmast.csv",
                    "secperf.csv",
                    "splits.csv",
                    "transactions.csv",
                ],
            )
        self.assertFalse(any((_ROOT / "src/perfaud/templates").rglob("*.py")))

    def test_source_never_imports_ppar(self) -> None:
        """No runtime module depends on the neighboring Analytics product."""
        offenders: list[str] = []
        for path in (_ROOT / "src/perfaud").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                module = ""
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                elif isinstance(node, ast.Import):
                    module = ",".join(alias.name for alias in node.names)
                if module == "ppar" or module.startswith("ppar."):
                    offenders.append(str(path.relative_to(_ROOT)))
        self.assertEqual(offenders, [])

    def test_obsolete_namespaces_and_catch_all_modules_are_absent(self) -> None:
        """The extracted tree does not retain combined-product compatibility."""
        self.assertFalse((_ROOT / "ppar").exists())
        for relative in (
            "src/perfaud/common.py",
            "src/perfaud/source_files.py",
            "src/perfaud/run_settings.py",
            "src/perfaud/config_validation.py",
            "src/perfaud/review_model.py",
            "src/perfaud/review_keys.py",
            "src/perfaud/review_glossary.py",
        ):
            self.assertFalse((_ROOT / relative).exists(), relative)

    def test_exception_registry_is_absent(self) -> None:
        """Exceptions carry actionable messages rather than numeric registry codes."""
        text = (_ROOT / "src/perfaud/errors.py").read_text(encoding="utf-8")
        self.assertNotIn("ERRORS", text)
        self.assertNotRegex(text, r"Error [0-9]{3}")

    def test_documentation_has_the_small_spine_and_marketing_image(self) -> None:
        """The active user path stays short while retaining the README image."""
        for relative in (
            "README.md",
            "docs/configuration.md",
            "docs/methodology.md",
            "docs/python_api.md",
            "docs/maintenance.md",
            "docs/images/PerformanceAuditPortfolio.jpg",
        ):
            self.assertTrue((_ROOT / relative).is_file(), relative)
        self.assertFalse((_ROOT / "perfaud.pdf").exists())
        self.assertFalse((_ROOT / "docs/archive").exists())
        self.assertFalse((_ROOT / "docs/analytics").exists())


def _pyproject() -> dict[str, Any]:
    """Return parsed project metadata."""
    return tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
