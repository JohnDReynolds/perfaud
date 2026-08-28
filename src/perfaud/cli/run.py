"""Run complete perfaud workspaces from the command line."""

from __future__ import annotations

import argparse
from pathlib import Path

from perfaud.workspace import run


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add the run command to the top-level parser."""
    parser = subparsers.add_parser(
        "run",
        help="Validate and run a workspace.",
        description="Validate and run a complete perfaud workspace.",
    )
    parser.add_argument(
        "workspace",
        nargs="?",
        type=Path,
        default=Path("."),
        help="Workspace directory. Defaults exactly to '.'.",
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
