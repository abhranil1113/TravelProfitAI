"""
optimization/solvers/base_solver.py

Abstract base class for all procurement optimization models.
"""

from abc import ABC, abstractmethod
import time
import logging
from typing import List, Dict, Optional, Tuple
from ortools.linear_solver import pywraplp

from optimization.config import OptimizationConfig
from optimization.schemas import CandidateOffer, SolverResult, SolverTerminationStatus

logger = logging.getLogger(__name__)


class BaseProcurementOptimizer(ABC):
    """Abstract interface and common utilities for MILP procurement models."""

    def __init__(self, name: str = "BaseOptimizer"):
        self.name = name

    @abstractmethod
    def solve(
        self,
        candidates: List[CandidateOffer],
        config: OptimizationConfig
    ) -> SolverResult:
        """Formulate and solve the procurement optimization problem."""
        pass

    @staticmethod
    def _translate_status(status_code: int) -> Tuple[str, bool]:
        """Maps OR-Tools integer status to standardized SolverTerminationStatus."""
        if status_code == pywraplp.Solver.OPTIMAL:
            return SolverTerminationStatus.OPTIMAL, True
        elif status_code == pywraplp.Solver.FEASIBLE:
            return SolverTerminationStatus.FEASIBLE, False
        elif status_code == pywraplp.Solver.INFEASIBLE:
            return SolverTerminationStatus.INFEASIBLE, False
        elif status_code == pywraplp.Solver.UNBOUNDED:
            return SolverTerminationStatus.UNBOUNDED, False
        elif status_code == pywraplp.Solver.ABNORMAL:
            return SolverTerminationStatus.ABNORMAL, False
        elif status_code == pywraplp.Solver.NOT_SOLVED:
            return SolverTerminationStatus.TIMEOUT, False
        else:
            return SolverTerminationStatus.ABNORMAL, False

    @staticmethod
    def _create_empty_result(
        solver_name: str,
        total_budget: float,
        status: str = SolverTerminationStatus.OPTIMAL
    ) -> SolverResult:
        """Generates an empty result when no eligible candidates exist."""
        return SolverResult(
            status=status,
            is_proven_optimal=(status == SolverTerminationStatus.OPTIMAL),
            objective_value=0.0,
            best_bound=0.0,
            optimality_gap=0.0,
            execution_time_seconds=0.001,
            solver_name=solver_name,
            num_variables=0,
            num_constraints=0,
            selected_quantities={},
            selected_offers={},
            total_spend=0.0,
            hotel_spend=0.0,
            flight_spend=0.0,
            remaining_budget=total_budget
        )
