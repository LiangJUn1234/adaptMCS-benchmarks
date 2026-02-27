"""Custom exceptions for AC extension Phase 1 skeleton."""


class ACExtensionError(Exception):
    """Base exception type for AC extension errors."""


class InterfaceNotImplementedError(ACExtensionError, NotImplementedError):
    """Raised when a Phase 1 interface stub is intentionally unimplemented."""


class InvalidInputError(ACExtensionError, ValueError):
    """Raised when invalid input is provided to an AC extension interface."""
