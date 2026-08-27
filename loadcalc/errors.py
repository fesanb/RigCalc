class LoadCalcError(Exception):
    """Base exception for recoverable LoadCalc failures."""


class GeometryError(LoadCalcError):
    """Raised when geometry cannot form a trustworthy model."""
