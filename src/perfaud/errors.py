"""Define the package-specific exception used for expected failures."""

from __future__ import annotations

from collections.abc import Mapping

__all__ = ["PerfaudError"]


class PerfaudError(Exception):
    """Represent an expected configuration, input, or execution failure.

    Attributes:
        context: Immutable-by-convention diagnostic values copied from the caller.
    """

    def __init__(
        self,
        message: str,
        *,
        context: Mapping[str, object] | None = None,
    ) -> None:
        """Initialize an actionable product error.

        Args:
            message: Concise description of the failure and corrective action.
            context: Optional machine-readable diagnostic values.
        """
        self.context = dict(context or {})
        super().__init__(message)
