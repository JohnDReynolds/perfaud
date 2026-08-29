"""Run complete perfaud workspaces from the command line."""

from __future__ import annotations

import argparse
from pathlib import Path

from perfaud.cli._help import add_help_argument
from perfaud.workspace import run


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add the run command to the top-level parser."""
    parser = subparsers.add_parser(
        "run",
        help="Run a portfolio performance audit from a directory.",
        description="Run a portfolio performance audit from a local directory.",
        epilog="example:\n  perfaud run ./my_perfaud",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        allow_abbrev=False,
        add_help=False,
    )
    add_help_argument(parser)
    parser.add_argument(
        "workspace",
        metavar="DIRECTORY",
        nargs="?",
        type=Path,
        default=Path("."),
        help="Local directory containing perfaud.yaml (default: current directory).",
    )
    parser.set_defaults(handler=_handle_run)


def _handle_run(arguments: argparse.Namespace) -> int:
    """Execute one workspace and print the published artifact inventory."""
    result = run(arguments.workspace)
    print(f"Workspace: {result.workspace}")
    print(f"Output: {result.output_directory}")
    for artifact in result.artifacts:
        print(f"Artifact: {artifact}")
    print("Validation: passed")
    return 0
