"""Strategy layer loading and validation errors."""

from __future__ import annotations


class StrategyNotFoundError(FileNotFoundError):
    """Raised when no strategy directory exists for a dataset."""


class StrategyValidationError(ValueError):
    """Raised when strategy YAML content fails validation."""


class StrategyRevisionConflictError(ValueError):
    """Raised when expected revision does not match current revision."""


class StrategyYamlParseError(ValueError):
    """Raised when incoming YAML cannot be parsed into an object."""

