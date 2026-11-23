"""
optimization/exceptions.py

Domain-specific exceptions for TBO InventoryIQ Phase 5 Optimization Engine.
"""

class OptimizationError(Exception):
    """Base exception for all optimization and procurement errors."""
    pass


class InfeasibleProblemError(OptimizationError):
    """Raised when the MILP solver proves the problem is mathematically infeasible."""
    pass


class UnboundedProblemError(OptimizationError):
    """Raised when the optimization problem is mathematically unbounded."""
    pass


class SolverTimeoutError(OptimizationError):
    """Raised when the solver exceeds the configured time limit without finding a feasible solution."""
    pass


class ExpiredOfferError(OptimizationError):
    """Raised when an expired supplier offer is submitted for optimization."""
    pass


class CurrencyMismatchError(OptimizationError):
    """Raised when incompatible or mixed currencies are detected in procurement inputs."""
    pass


class UnverifiedCurrencyError(OptimizationError):
    """Raised when an unverified currency is used without explicit prototype authorization."""
    pass


class SchemaValidationError(OptimizationError):
    """Raised when input datasets or features fail schema validation rules."""
    pass


class PointInTimeViolationError(OptimizationError):
    """Raised when future-dated observations or snapshots are detected at optimization time."""
    pass


class ModelInferenceError(OptimizationError):
    """Raised when an ML prediction service fails or produces invalid outputs."""
    pass


class SolverError(OptimizationError):
    """Raised when an optimization solver fails to initialize or execute."""
    pass

