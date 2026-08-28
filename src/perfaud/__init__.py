"""Audit changes in reported portfolio performance."""

from importlib.metadata import version

from perfaud.workspace import run

__version__ = version("perfaud")

__all__ = ["run", "__version__"]
