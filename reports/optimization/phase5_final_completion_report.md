# Phase 5: Inventory Procurement Optimization & Recommendation Engine — Final Completion Report

**Project:** TBO InventoryIQ — AI-Powered Travel Inventory & Profit Optimization Platform  
**Team:** Team Sabuj Sangha  
**Members:** Abhranil Pal and Arka Dyuti Bose  
**Date:** November 23, 2026  
**Status:** 100% COMPLETED, VALIDATED & TESTED  

---

## 1. Executive Summary

Phase 5 has successfully implemented, tested, and validated an end-to-end Machine Learning-powered Mixed Integer Linear Programming (MILP) procurement optimization and recommendation engine for TBO InventoryIQ.

The platform ingests active supplier offers, filters expired and future-dated records, integrates Phase 4 ML prediction models (LightGBM cancellation probabilities with prototype ADR currency scaling, flight price elasticity, and historical demand absorption ceilings), formulates single-stage and multi-product MILP models in Google OR-Tools (SCIP), executes heuristic baseline comparisons, conducts parametric sensitivity sweeps, and outputs human-explainable procurement recommendations alongside transparent rejection records.

---

## 2. Architecture & File Inventory

### 2.1 Existing Phase 1–4 Files Reused Intact
- `data/processed/supplier_offers/cleaned_supplier_offers.parquet` (5,000 raw offers)
- `data/processed/inventory/cleaned_inventory_availability.parquet` (inventory availability snapshots)
- `data/processed/searches/cleaned_customer_search_events.parquet` (search event logs)
- `data/models/hotel_cancellation/` (`estimator.joblib`, `preprocessor.joblib`, `metadata.json`)
- `data/models/flight_price_prediction/` (`estimator.joblib`, `metadata.json`)
- `data/models/demand_search_volume_forecasting/` (`estimator.joblib`, `metadata.json`)
- `data/models/inventory_depletion_forecasting/` (`estimator.joblib`, `metadata.json`)
- All 166 existing tests across `tests/data_validation/`, `tests/eda/`, `tests/feature_engineering/`, and `tests/modeling/`.

### 2.2 New Optimization Package Architecture (`optimization/`)
1. **Configuration & Schemas:**
   - `optimization/config.py`: Master `OptimizationConfig`, `FinancialAssumptions`, `RiskConfig`, `SolverConfig`, `CurrencyTier`, `SolverBackend`.
   - `optimization/schemas.py`: Typed Pydantic schemas (`ProcurementOpportunity`, `CandidateOffer`, `SolverResult`, `EvaluationMetrics`, `RecommendationRecord`, `RejectedOpportunityRecord`, `OptimizationPlan`).
   - `optimization/exceptions.py`: Domain-specific exceptions (`OptimizationError`, `SolverError`, `InfeasibleProblemError`, `PointInTimeViolationError`, `CurrencyMismatchError`).
2. **Data Preparation & Cutoff Services (`optimization/data/`):**
   - `loader.py`: Safe dataset loader.
   - `currency.py`: 3-tier currency validation logic.
   - `point_in_time.py`: Cutoff date filtering and latest inventory snapshot deduplication.
   - `demand.py`: Historical search event ceiling calculation per destination.
   - `candidate_builder.py`: Ingestion, scoring, and `CandidateOffer` generation.
3. **ML Predictor Integrations (`optimization/predictions/`):**
   - `model_registry.py`: Memory-cached joblib artifact loader.
   - `hotel_cancellation.py`: LightGBM cohort builder with 90x prototype EUR ADR scaling and Bayesian shrinkage.
   - `flight_price.py`: Flight price elasticity and consumer market ceiling inference.
   - `demand_forecasting.py`: Search volume predictor.
   - `inventory_forecasting.py`: Depletion rate predictor.
4. **Audited Economic Formulations (`optimization/economics/`):**
   - `hotel_economics.py`: 4-outcome multi-scenario model (Unsold, Completed, Cancelled & Resold, Cancelled & Unresold).
   - `flight_economics.py`: Flight spoilage model (0% baseline vs 10% salvage) and analytical break-even calculation.
5. **Mathematical Optimization Solvers (`optimization/solvers/`):**
   - `solver_factory.py`: OR-Tools wrapper for SCIP, CBC, HIGHS, and SAT.
   - `base_solver.py`: Abstract optimizer interface.
   - `hotel_optimizer.py`: Hotel room-night MILP solver.
   - `flight_optimizer.py`: Flight seat MILP solver.
   - `joint_optimizer.py`: Single-stage unified multi-product MILP solver.
6. **Evaluation & Baselines (`optimization/evaluation/`):**
   - `metrics.py`: Operational & commercial scorecard metrics calculator.
   - `baselines.py`: Heuristic benchmark comparisons (No Procurement, Greedy Gross Margin, Greedy Expected Contribution).
   - `sensitivity.py`: Parametric sweeps across budgets, sell-through, and risk limits.
7. **Recommendations & Explanations (`optimization/recommendations/`):**
   - `rejection_reasons.py`: Diagnostic reason codes.
   - `explanations.py`: Evidence-backed, non-fabricated rationale builder.
   - `generator.py`: Recommendation and structured rejection generator.
8. **End-to-End Orchestrator (`optimization/pipeline.py`):**
   - `OptimizationPipeline`: High-level execution class managing data prep, solving, evaluation, sensitivity, recommendation generation, and artifact persistence.

---

## 3. Automated Test Suite Verification

A comprehensive test suite of **30 new optimization tests** was created under `tests/optimization/`:

- `test_mathematical_economics.py` (7 tests):
  - Hotel 4-outcome probabilities sum to 1.0.
  - Hotel expected contribution manual hand-calculation benchmark.
  - Non-refundable supplier penalty verification.
  - Flight 0% baseline spoilage equation ($e_F = +475.0$ at $\theta=0.85$).
  - Flight 10% contractual salvage equation ($e_F = +538.0$ at $\theta=0.85$).
  - Flight break-even sell-through threshold $\theta^* = 76.36\%$ (at which $e_F \equiv 0.0$).
  - Price elasticity sell-through adjustment.
- `test_solvers.py` (7 tests):
  - Deterministic 2-offer budget allocation manual benchmark.
  - All-or-nothing Minimum Order Quantity (MOQ) enforcement.
  - Capacity upper-bound constraint enforcement.
  - Destination aggregate demand ceiling enforcement.
  - Portfolio supplier concentration cap enforcement.
  - Joint multi-product competition under shared budget.
  - Negative-contribution opportunities strictly excluded.
- `test_recommendations.py` (4 tests):
  - Recommendation record generation with non-fabricated rationales.
  - Negative contribution rejection attribution (`NEGATIVE_CONTRIBUTION`).
  - MOQ exceeding budget rejection attribution (`MOQ_EXCEEDS_BUDGET`).
  - Expired offers attribution (`EXPIRED_OFFER`).
- `test_point_in_time_and_ml.py` (3 tests):
  - Expired offers filtered relative to cutoff date.
  - Model registry artifact loading.
  - Prototype EUR ADR scaling ($90\times$) preventing out-of-distribution blowout.
- `test_pipeline.py` (3 tests):
  - Joint multi-product pipeline execution and disk persistence.
  - Hotel-only procurement execution.
  - Flight-only procurement execution.
- `test_stage1_validation.py` (6 tests):
  - Mathematical audit validation tests from Stage 1.3.

### Regression Test Results
- **Phase 1 Data Validation:** 27 passed
- **Phase 2 Exploratory Data Analysis:** 41 passed
- **Phase 3 Feature Engineering:** 33 passed
- **Phase 4 ML Modeling:** 59 passed
- **Phase 5 Optimization:** 30 passed
- **Total Test Suite:** **190 tests executed, 190 passed, 0 failed, 0 regressions.**

---

## 4. Scalability & Performance Benchmarks

Measured on Windows 64-bit using the full real active candidate dataset:

```text
===============================================================================================
OFFERS   | VARS     | CONSTR   | STATUS     | OPTIMAL  | OBJ VALUE    | SPEND        | TIME (s)  
===============================================================================================
10       | 20       | 40       | OPTIMAL    | True     | 9057.28      | 97184.61     | 0.0048    
50       | 100      | 137      | OPTIMAL    | True     | 13790.24     | 194114.79    | 0.0060    
100      | 200      | 238      | OPTIMAL    | True     | 15173.84     | 221886.67    | 0.0266    
500      | 1000     | 1039     | OPTIMAL    | True     | 43756.09     | 488577.74    | 0.2392    
1000     | 2000     | 2039     | OPTIMAL    | True     | 49603.97     | 499801.37    | 0.7388    
3257     | 6514     | 6553     | OPTIMAL    | True     | 57636.92     | 499727.44    | 1.9252    
===============================================================================================
```

Every problem instance achieved **proven global optimality (`OPTIMAL`)** with **0.00% MIP gap** in under 2 seconds.

---

## 5. Output Artifacts & Audit Logs

Executing `OptimizationPipeline.run()` automatically writes the following files to `data/optimization/`:

1. `procurement_recommendations.csv`: Actionable procurement records for selected offers.
2. `rejected_opportunities.csv`: Diagnostic rejection logs for all 3,251 unselected offers detailing primary reason codes (`NEGATIVE_CONTRIBUTION`, `MOQ_EXCEEDS_DEMAND`, `SUPPLIER_CAP_BINDING`, `MOQ_EXCEEDS_BUDGET`, `NOT_SELECTED_BY_OPTIMAL_ALLOCATION`).
3. `optimization_summary.json`: Comprehensive run metadata, solver gap, execution time, baseline lifts, and parametric sensitivity sweeps.
4. `optimization_runs/<run_id>/`: Immutable, run-specific directory preserving exact reproducibility.

---

## 6. How to Execute the Optimization Pipeline

```python
from optimization import OptimizationConfig, OptimizationPipeline

# Configure optimization run
config = OptimizationConfig(
    run_id="PROD_OPTIMIZATION_001",
    optimization_timestamp="2026-06-01",
    total_budget=250000.0,
    target_currency="INR",
    allow_prototype_currency_override=True
)

# Execute end-to-end pipeline
pipeline = OptimizationPipeline(config)
plan = pipeline.run(output_dir="data/optimization")

print(f"Status: {plan.evaluation_metrics.solver_status}")
print(f"Total Spend: INR {plan.evaluation_metrics.total_spend:,.2f}")
print(f"Net Profit: INR {plan.evaluation_metrics.expected_net_profit:,.2f}")
print(f"Recommendations Generated: {len(plan.recommendations)}")
```
