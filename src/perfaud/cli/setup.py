"""Create complete Axys/APX perfaud workspaces."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path
import shutil
import tempfile

from perfaud.config import load_config, settings, validate_config
from perfaud.errors import PerfaudError
from perfaud.workspace import CONFIG_FILE_NAME, OUTPUT_DIRECTORY_NAME


@dataclass(frozen=True)
class SetupResult:
    """Describe one successfully created workspace."""

    workspace: Path
    configuration: Path


def setup(workspace: str | Path) -> SetupResult:
    """Create and validate a complete Axys/APX demonstration workspace.

    Args:
        workspace: Explicit destination directory.

    Returns:
        Resolved workspace and configuration paths.

    Raises:
        PerfaudError: If the destination is unsuitable or validation fails.
    """
    destination = Path(workspace).expanduser().resolve()
    if destination.exists() and not destination.is_dir():
        raise PerfaudError(f"Workspace destination is not a directory: {destination}")
    if destination.exists() and any(destination.iterdir()):
        raise PerfaudError(
            f"Workspace destination must be empty: {destination}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.setup-",
            dir=destination.parent,
        )
    )
    try:
        _copy_template(staging)
        validate_config(staging / CONFIG_FILE_NAME)
        settings(load_config(staging / CONFIG_FILE_NAME))
        if destination.exists():
            destination.rmdir()
        staging.replace(destination)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return SetupResult(
        workspace=destination,
        configuration=destination / CONFIG_FILE_NAME,
    )


def _copy_template(destination: Path) -> None:
    """Copy the packaged data-only Axys/APX template into a standard workspace."""
    resource = files("perfaud").joinpath("templates", "axys_apx")
    _copy_resource(resource.joinpath("README.md"), destination / "README.md")
    _copy_resource(
        resource.joinpath(CONFIG_FILE_NAME),
        destination / CONFIG_FILE_NAME,
    )
    for snapshot_name in ("snapshot_a", "snapshot_b"):
        _copy_resource_tree(
            resource.joinpath("input", snapshot_name),
            destination / "input" / snapshot_name,
        )
    (destination / OUTPUT_DIRECTORY_NAME).mkdir(parents=True)


def _copy_resource_tree(source: Traversable, destination: Path) -> None:
    """Copy one packaged resource directory recursively."""
    destination.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        target = destination / child.name
        if child.is_dir():
            _copy_resource_tree(child, target)
        elif child.is_file():
            _copy_resource(child, target)


def _copy_resource(source: Traversable, destination: Path) -> None:
    """Copy one packaged resource file."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(source.read_bytes())


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Add the setup command to the top-level parser."""
    parser = subparsers.add_parser(
        "setup",
        help="Create a complete Axys/APX workspace.",
        description="Create a complete Axys/APX perfaud workspace.",
    )
    parser.add_argument("workspace", type=Path, help="New workspace directory.")
    parser.set_defaults(handler=_handle_setup)


def _handle_setup(arguments: argparse.Namespace) -> int:
    """Execute setup and print its concise handoff."""
    result = setup(arguments.workspace)
    print(f"Workspace: {result.workspace}")
    print("Source: axys_apx")
    print(f"Configuration: {result.configuration}")
    print(f"Next: perfaud run {result.workspace}")
    return 0
