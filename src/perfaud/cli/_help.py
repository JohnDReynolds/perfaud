"""Shared helpers for consistent command-line help."""

from __future__ import annotations

import argparse


def add_help_argument(parser: argparse.ArgumentParser) -> None:
    """Add the consistently styled help option to a command parser."""
    parser.add_argument(
        "-h",
        "--help",
        action="help",
        help="Show this help message.",
    )
