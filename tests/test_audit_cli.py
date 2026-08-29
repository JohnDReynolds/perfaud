"""Tests for the complete perfaud command surface and workspace service."""

from __future__ import annotations

from dataclasses import fields
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import yaml

import perfaud
from perfaud.cli import main as cli_main
from perfaud.cli.setup import setup
from perfaud.errors import PerfaudError
from perfaud.workspace import RunResult, run


class TestPerfaudCli(unittest.TestCase):
    """The CLI exposes only setup, run, help, and version."""

    def test_help_has_only_approved_commands(self) -> None:
        """Top-level help keeps the complete public command surface small."""
        result = _command("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("{setup,run}", result.stdout)
        for obsolete_command in ("audit", "analytics", "validate"):
            self.assertNotIn(f"\n    {obsolete_command}", result.stdout)
        self.assertNotIn("--verbose", result.stdout)

    def test_version_is_metadata_backed(self) -> None:
        """The command and package report the same installed version."""
        result = _command("--version")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), f"perfaud {perfaud.__version__}")

    def test_invalid_syntax_returns_two(self) -> None:
        """Argparse owns invalid-command syntax and its conventional exit code."""
        result = _command("unknown")
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid choice", result.stderr)

    def test_expected_failure_is_concise(self) -> None:
        """Expected product errors return one without a traceback."""
        result = _command("run", "/path/that/does/not/exist")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Workspace is not a directory", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_unexpected_failure_is_not_caught(self) -> None:
        """Programming failures retain their traceback for diagnosis."""
        with mock.patch("perfaud.cli.run.run", side_effect=RuntimeError("boom")):
            with self.assertRaisesRegex(RuntimeError, "boom"):
                cli_main(["run", "."])

    def test_setup_and_run_complete_workspace(self) -> None:
        """The visible onboarding workflow produces both selected report levels."""
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            setup_result = _command("setup", str(workspace))
            run_result = _command("run", str(workspace))
            self.assertEqual(setup_result.returncode, 0, setup_result.stderr)
            self.assertEqual(run_result.returncode, 0, run_result.stderr)
            self.assertTrue((workspace / "perfaud.yaml").is_file())
            self.assertFalse(any(workspace.glob("*.py")))
            self.assertTrue((workspace / "input" / "snapshot_a").is_dir())
            self.assertTrue((workspace / "input" / "snapshot_b").is_dir())
            artifacts = sorted(
                path.relative_to(workspace / "output").as_posix()
                for path in (workspace / "output").rglob("*")
                if path.is_file()
            )
            self.assertEqual(len(artifacts), 10)
            self.assertTrue(
                all(name.startswith(("portfolio/", "security/")) for name in artifacts)
            )
            self.assertIn("Validation: passed", run_result.stdout)

    def test_setup_refuses_nonempty_destination(self) -> None:
        """Setup never overwrites an existing user's files."""
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            workspace.mkdir()
            sentinel = workspace / "keep.txt"
            sentinel.write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(PerfaudError, "must be empty"):
                setup(workspace)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_run_defaults_exactly_to_current_directory(self) -> None:
        """A bare run inspects only dot and never searches a parent directory."""
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            setup(workspace)
            child = workspace / "child"
            child.mkdir()
            previous = Path.cwd()
            try:
                os.chdir(child)
                with self.assertRaisesRegex(PerfaudError, "perfaud.yaml.*missing"):
                    run()
            finally:
                os.chdir(previous)

    def test_python_and_cli_publish_same_inventory(self) -> None:
        """Both entry points delegate to the same complete workspace service."""
        with tempfile.TemporaryDirectory() as directory:
            api_workspace = Path(directory) / "api"
            cli_workspace = Path(directory) / "cli"
            setup(api_workspace)
            setup(cli_workspace)
            api_result = run(api_workspace)
            cli_result = _command("run", str(cli_workspace))
            self.assertEqual(cli_result.returncode, 0, cli_result.stderr)
            api_names = [
                path.relative_to(api_result.output_directory)
                for path in api_result.artifacts
            ]
            cli_names = sorted(
                path.relative_to(cli_workspace / "output")
                for path in (cli_workspace / "output").rglob("*")
                if path.is_file()
            )
            self.assertEqual(api_names, cli_names)

    def test_failed_run_preserves_previous_output(self) -> None:
        """A failed run leaves the prior successful result byte-for-byte intact."""
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            setup(workspace)
            first = run(workspace)
            before = {
                path.relative_to(first.output_directory): path.read_bytes()
                for path in first.artifacts
            }
            config_path = workspace / "perfaud.yaml"
            configuration = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            configuration["snapshots"]["b"]["path"] = "input/missing"
            config_path.write_text(
                yaml.safe_dump(configuration, sort_keys=False),
                encoding="utf-8",
            )
            with self.assertRaises(PerfaudError):
                run(workspace)
            after = {
                path.relative_to(first.output_directory): path.read_bytes()
                for path in first.output_directory.rglob("*")
                if path.is_file()
            }
            self.assertEqual(after, before)

    def test_run_result_is_minimal_and_immutable(self) -> None:
        """The result has exactly the three documented fields."""
        self.assertEqual(
            [field.name for field in fields(RunResult)],
            ["workspace", "output_directory", "artifacts"],
        )
        self.assertTrue(getattr(RunResult, "__dataclass_params__").frozen)


def _command(*arguments: str) -> subprocess.CompletedProcess[str]:
    """Run the public module command from the repository checkout."""
    return subprocess.run(
        [sys.executable, "-m", "perfaud.cli", *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


if __name__ == "__main__":
    unittest.main()
