"""Strategy layer loading and validation errors."""

from __future__ import annotations


class StrategyNotFoundError(FileNotFoundError):
    """Raised when no strategy directory exists for a dataset."""


class StrategyValidationError(ValueError):
    """Raised when strategy YAML content fails validation."""

