import time
import numpy as np
from ortools.linear_solver import pywraplp

def run_benchmark(num_items=50, seed=42):
    np.random.seed(seed)
    # Generate synthetic procurement problem
    purchase_costs = np.random.uniform(500, 5000, num_items)
    selling_prices = purchase_costs + np.random.uniform(200, 1500, num_items)
    capacities = np.random.randint(5, 50, num_items)
    moqs = np.random.randint(2, 10, num_items)
    demands = np.random.randint(5, 60, num_items)
    total_budget = float(np.sum(purchase_costs * capacities) * 0.35)

    solvers = ["CBC", "SCIP", "HIGHS", "SAT"]
    results = {}

    for solver_name in solvers:
        solver = pywraplp.Solver.CreateSolver(solver_name)
        if not solver:
            results[solver_name] = {"available": False}
            continue

        start_time = time.perf_counter()

        # Variables: q_i (integer quantity), y_i (binary selection)
        q = {}
        y = {}
        for i in range(num_items):
            q[i] = solver.IntVar(0.0, float(capacities[i]), f"q_{i}")
            y[i] = solver.BoolVar(f"y_{i}")

        # Objective: Maximize expected net profit = sum((selling_price_i - purchase_cost_i) * q_i)
        objective = solver.Objective()
        for i in range(num_items):
            margin = selling_prices[i] - purchase_costs[i]
            objective.SetCoefficient(q[i], margin)
        objective.SetMaximization()

        # Constraints
        # 1. Total budget: sum(purchase_cost_i * q_i) <= total_budget
        budget_ct = solver.Constraint(0.0, total_budget, "budget")
        for i in range(num_items):
            budget_ct.SetCoefficient(q[i], float(purchase_costs[i]))

        # 2. Demand limit: q_i <= demand_i
        for i in range(num_items):
            solver.Add(q[i] <= float(demands[i]))

        # 3. Capacity & Selection: q_i <= capacity_i * y_i
        for i in range(num_items):
            solver.Add(q[i] <= float(capacities[i]) * y[i])

        # 4. Minimum order quantity: q_i >= moq_i * y_i
        for i in range(num_items):
            solver.Add(q[i] >= float(moqs[i]) * y[i])

        # Solve
        status = solver.Solve()
        elapsed = time.perf_counter() - start_time

        status_str = {
            pywraplp.Solver.OPTIMAL: "OPTIMAL",
            pywraplp.Solver.FEASIBLE: "FEASIBLE",
            pywraplp.Solver.INFEASIBLE: "INFEASIBLE",
            pywraplp.Solver.UNBOUNDED: "UNBOUNDED",
            pywraplp.Solver.ABNORMAL: "ABNORMAL",
            pywraplp.Solver.NOT_SOLVED: "NOT_SOLVED"
        }.get(status, f"CODE_{status}")

        if status in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
            obj_val = solver.Objective().Value()
            total_cost = sum(purchase_costs[i] * q[i].solution_value() for i in range(num_items))
            total_qty = sum(q[i].solution_value() for i in range(num_items))
            selected_suppliers = sum(y[i].solution_value() for i in range(num_items))
            
            # Gap if available
            try:
                best_bound = solver.Objective().BestObjectiveBound()
                gap = abs(best_bound - obj_val) / (abs(obj_val) + 1e-9)
            except Exception:
                best_bound = None
                gap = 0.0 if status == pywraplp.Solver.OPTIMAL else None

            results[solver_name] = {
                "available": True,
                "status": status_str,
                "time_sec": elapsed,
                "objective": obj_val,
                "total_cost": total_cost,
                "total_budget": total_budget,
                "total_qty": total_qty,
                "selected_suppliers": selected_suppliers,
                "best_bound": best_bound,
                "gap": gap,
                "num_variables": solver.NumVariables(),
                "num_constraints": solver.NumConstraints(),
            }
        else:
            results[solver_name] = {
                "available": True,
                "status": status_str,
                "time_sec": elapsed,
            }

    print("=== SOLVER BENCHMARK RESULTS (N=50 items) ===")
    for s_name, res in results.items():
        print(f"Solver: {s_name}")
        for k, v in res.items():
            print(f"  {k}: {v}")
        print()

if __name__ == "__main__":
    run_benchmark()
