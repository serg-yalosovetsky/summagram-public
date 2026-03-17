"""Domain exceptions for the model orchestrator.

Typed exceptions per coding rule #8 — explicit domain errors instead of
generic RuntimeError / TimeoutError.
"""


class OrchestratorError(Exception):
    """Base exception for all orchestrator domain errors."""


class UnknownModeError(OrchestratorError):
    """Raised for an unrecognised or unsupported mode."""


class WorkerWakeTimeoutError(OrchestratorError):
    """Raised when wake_up did not complete within the allowed timeout."""


class WorkerReadyTimeoutError(OrchestratorError):
    """Raised when /v1/models did not return 200 within the allowed timeout."""


class WorkerSleepError(OrchestratorError):
    """Raised when a sleep call fails or cannot be verified."""


# Kept for backward compatibility with tests / external callers that still
# reference these names.
ModelReadyTimeoutError = WorkerReadyTimeoutError
