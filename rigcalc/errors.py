class RigCalcError(Exception):
    """Base exception for recoverable RigCalc failures."""


class GeometryError(RigCalcError):
    """Raised when geometry cannot form a trustworthy model."""
