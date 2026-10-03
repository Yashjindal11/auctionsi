"""Exception hierarchy. Every error raised deliberately by AuctionSI derives from AuctionSIError."""


class AuctionSIError(Exception):
    """Base class for AuctionSI errors."""


class ValidationError(AuctionSIError, ValueError):
    """Input failed validation (task, agent metadata, configuration, payload)."""


class InvalidTransitionError(AuctionSIError):
    """A state machine was asked to make a transition its rules do not allow."""


class NotFoundError(AuctionSIError, KeyError):
    """A referenced task, agent, auction or plugin does not exist."""


class ConfigurationError(AuctionSIError):
    """A configuration file or plugin specification is invalid."""


class OptionalDependencyError(AuctionSIError, ImportError):
    """An optional extra (for example ``plotly``) is required but not installed."""
