"""Custom exceptions for AC extension."""


class ACExtensionError(Exception):
    """Base exception type for AC extension errors."""


class InterfaceNotImplementedError(ACExtensionError, NotImplementedError):
    """Raised when an interface stub is intentionally unimplemented."""


class InvalidInputError(ACExtensionError, ValueError):
    """Raised when invalid input is provided to an AC extension interface."""


class MatlabEngineUnavailableError(ACExtensionError, RuntimeError):
    """Raised when MATLAB engine for Python is not importable/available."""


class MatlabPathError(ACExtensionError, RuntimeError):
    """Raised when required MATLAB paths cannot be configured."""


class MatlabExecutionError(ACExtensionError, RuntimeError):
    """Raised when a MATLAB wrapper invocation fails."""
