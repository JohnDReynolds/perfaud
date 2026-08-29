"""Top-level parser and error boundary for the perfaud command."""

from __future__ import annotations

import argparse
from importlib.metadata import version
import sys
from typing import Callable, cast

from perfaud.cli._help import add_help_argument
from perfaud.cli import run as run_command
from perfaud.cli import setup as setup_command
from perfaud.errors import PerfaudError


def main(argv: list[str] | None = None) -> int:
    """Run the ``perfaud`` command and return its documented exit code."""
    parser = _parser()
    effective_argv = sys.argv[1:] if argv is None else argv
    if not effective_argv:
        parser.print_help()
        return 0
    arguments = parser.parse_args(effective_argv)
    handler = cast(Callable[[argparse.Namespace], int], arguments.handler)
    try:
        return handler(arguments)
    except PerfaudError as error:
        print(f"perfaud: {error}", file=sys.stderr)
        return 1


def _parser() -> argparse.ArgumentParser:
    """Return the complete public command parser."""
    parser = argparse.ArgumentParser(
        prog="perfaud",
        description=(
            "Set up and run a portfolio performance audit using files in a local "
            "directory."
        ),
        epilog=(
            "command forms:\n"
            "  perfaud setup DIRECTORY\n"
            "  perfaud run [DIRECTORY]\n\n"
            "DIRECTORY is a local directory used by both commands:\n"
            "  setup creates and populates DIRECTORY with the required files.\n"
            "  run uses the files in DIRECTORY. When DIRECTORY is omitted, run uses the\n"
            "  current directory.\n\n"
            "examples:\n"
            "  perfaud setup ./my_perfaud\n"
            "  perfaud run ./my_perfaud"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        allow_abbrev=False,
        add_help=False,
    )
    add_help_argument(parser)
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {version('perfaud')}",
        help="Show the perfaud version.",
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        title="commands",
    )
    setup_command.add_parser(subparsers)
    run_command.add_parser(subparsers)
    return parser
