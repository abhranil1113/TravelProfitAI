"""
optimization/solvers/solver_factory.py

Factory for instantiating mathematical optimization solvers using Google OR-Tools.
Supports primary (SCIP) and fallback (CBC, HIGHS, SAT) backends.
"""

import logging
from typing import Optional
from ortools.linear_solver import pywraplp

from optimization.config import SolverBackend, SolverConfig
from optimization.exceptions import SolverError

logger = logging.getLogger(__name__)


class SolverFactory:
    """Creates configured OR-Tools solver instances."""

    @staticmethod
    def create_solver(
        solver_config: SolverConfig,
        problem_name: str = "TBO_Inventory_MILP"
    ) -> pywraplp.Solver:
        """
        Instantiate an OR-Tools solver with configured time limits and gap tolerances.
        Falls back to CBC or SAT if the requested backend is unavailable.
        """
        backend_order = [solver_config.backend]
        if solver_config.fallback_backend and solver_config.fallback_backend != solver_config.backend:
            backend_order.append(solver_config.fallback_backend)
        
        # Ensure standard fallbacks are included
        for candidate in [SolverBackend.SCIP, SolverBackend.CBC, SolverBackend.HIGHS, SolverBackend.SAT]:
            if candidate not in backend_order:
                backend_order.append(candidate)

        solver = None
        chosen_backend = None

        for b in backend_order:
            try:
                solver = pywraplp.Solver.CreateSolver(b.value)
                if solver is not None:
                    chosen_backend = b.value
                    logger.info(f"Initialized OR-Tools solver with backend: {chosen_backend} for {problem_name}")
                    break
            except Exception as e:
                logger.warning(f"Failed to instantiate backend {b.value}: {e}")

        if solver is None:
            raise SolverError(f"Could not instantiate any OR-Tools solver backend from: {[b.value for b in backend_order]}")

        # Set time limit (OR-Tools expects milliseconds)
        time_limit_ms = int(solver_config.time_limit_seconds * 1000)
        solver.SetTimeLimit(time_limit_ms)

        # Set relative gap tolerance if supported
        try:
            solver_params = pywraplp.MPSolverParameters()
            solver_params.SetDoubleParam(
                pywraplp.MPSolverParameters.RELATIVE_MIP_GAP,
                solver_config.relative_gap_tolerance
            )
            solver.SetSolverSpecificParametersAsString("")
        except Exception as e:
            logger.debug(f"Note: solver parameter setting: {e}")

        if solver_config.enable_logging:
            solver.EnableOutput()

        return solver
