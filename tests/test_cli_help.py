"""Tests for the public command-line help surface."""

from __future__ import annotations

import subprocess
import sys
import unittest


class TestCliHelp(unittest.TestCase):
    """Ensure CLI help consistently describes local directories."""

    def test_top_level_help_describes_commands_and_directory(self) -> None:
        """Top-level help explains both command forms and directory semantics."""
        result = _command("--help")

        self.assertEqual(result.returncode, 0)
        help_text = result.stdout
        normalized_help = " ".join(help_text.split())
        self.assertIn(
            "Set up and run a portfolio performance audit using files in a local "
            "directory.",
            normalized_help,
        )
        self.assertIn("commands:", help_text)
        self.assertIn(
            "Create and populate a directory for running a portfolio performance "
            "audit.",
            normalized_help,
        )
        self.assertIn(
            "Run a portfolio performance audit from a directory.",
            normalized_help,
        )
        self.assertIn("perfaud setup DIRECTORY", help_text)
        self.assertIn("perfaud run [DIRECTORY]", help_text)
        self.assertIn(
            "DIRECTORY is a local directory used by both commands:",
            help_text,
        )
        self.assertIn(
            "setup creates and populates DIRECTORY with the required files.",
            help_text,
        )
        self.assertIn(
            "When DIRECTORY is omitted, run uses the current directory.",
            normalized_help,
        )
        self.assertIn("perfaud setup ./my_perfaud", help_text)
        self.assertIn("perfaud run ./my_perfaud", help_text)
        self.assertIn("Show this help message.", help_text)
        self.assertIn("Show the perfaud version.", help_text)
        _assert_forbidden_terms_absent(self, help_text)

    def test_setup_help_defines_required_directory(self) -> None:
        """Setup help presents DIRECTORY as a required local destination."""
        result = _command("setup", "--help")

        self.assertEqual(result.returncode, 0)
        help_text = result.stdout
        normalized_help = " ".join(help_text.split())
        self.assertIn("usage: perfaud setup [-h] DIRECTORY", help_text)
        self.assertIn(
            "Create and populate a directory for running a portfolio performance "
            "audit.",
            normalized_help,
        )
        self.assertIn(
            "Local directory to create and populate with configuration, demonstration "
            "inputs, and an output folder.",
            normalized_help,
        )
        self.assertIn("Show this help message.", help_text)
        self.assertIn("perfaud setup ./my_perfaud", help_text)
        _assert_forbidden_terms_absent(self, help_text)

    def test_run_help_defines_optional_directory(self) -> None:
        """Run help presents DIRECTORY as optional and explains its default."""
        result = _command("run", "--help")

        self.assertEqual(result.returncode, 0)
        help_text = result.stdout
        normalized_help = " ".join(help_text.split())
        self.assertIn("usage: perfaud run [-h] [DIRECTORY]", help_text)
        self.assertIn(
            "Run a portfolio performance audit from a local directory.",
            normalized_help,
        )
        self.assertIn("Local directory containing perfaud.yaml", normalized_help)
        self.assertIn("default: current directory", normalized_help)
        self.assertIn("Show this help message.", help_text)
        self.assertIn("perfaud run ./my_perfaud", help_text)
        _assert_forbidden_terms_absent(self, help_text)

    def test_setup_missing_directory_names_required_argument(self) -> None:
        """A setup syntax error identifies the missing value as DIRECTORY."""
        result = _command("setup")

        self.assertEqual(result.returncode, 2)
        self.assertIn("usage: perfaud setup [-h] DIRECTORY", result.stderr)
        self.assertIn(
            "the following arguments are required: DIRECTORY",
            result.stderr,
        )


def _command(*arguments: str) -> subprocess.CompletedProcess[str]:
    """Run the public module command from the repository checkout."""
    return subprocess.run(
        [sys.executable, "-m", "perfaud.cli", *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


def _assert_forbidden_terms_absent(
    test_case: unittest.TestCase,
    help_text: str,
) -> None:
    """Assert that internal terminology does not leak into terminal help."""
    normalized_help = help_text.lower()
    for forbidden_term in ("workspace", "runnable", "configured", "artifact"):
        test_case.assertNotIn(forbidden_term, normalized_help)


if __name__ == "__main__":
    unittest.main()
