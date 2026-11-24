# TBO InventoryIQ — Hardcoded Values Audit & Configuration Refactoring Report

**Audit Date:** 2026-11-24  
**Author:** Senior Backend QA & Quantitative Optimization Architect  
**Repository:** `https://github.com/abhranil1113/TravelProfitAI.git`  
**Primary Focus Modules:** `optimization/config.py`, `optimization/economics/`, `optimization/data/`, `optimization/predictions/`, `optimization/solvers/`, `optimization/pipeline.py`

---

## Executive Summary

A comprehensive repository-wide audit was conducted across the TBO InventoryIQ codebase, spanning the Phase 5 Mathematical Optimization Engine, Economics Calculators, Machine Learning Inference Services, Data Pipeline, Modeling, and Backend layers.

The objective is to distinguish between:
1. **Business-configurable parameters & commercial thresholds** that belong in centralized, validated configuration models.
2. **Mathematical invariants & structural formulas** that must remain embedded in equations.
3. **Environment/infrastructure settings & test fixtures** that require proper segregation without introducing breaking schema changes.

This document categorizes all discovered hardcoded values, evaluates the refactoring necessity and risk for each, and specifies the target configuration architecture implemented in `optimization/config.py`.

---

## 1. Classification Taxonomies

Findings are classified into 11 standardized categories:
1. **Business Assumptions (BA):** Commercial policies, sell-through expectations, conversion rates, customer behavior models.
2. **Financial Assumptions (FA):** Refund rates, salvage recovery percentages, resale discounts, foreign exchange rates.
3. **Risk Thresholds (RT):** Portfolio concentration limits, exposure ceilings, Bayesian shrinkage weights.
4. **Prediction Thresholds (PT):** Cohort lead-time buckets, seasonality windows, inference clipping bounds.
5. **Solver Parameters (SP):** MILP solver backend, relative optimality gap tolerance, execution time limits.
6. **Default Dates and Budgets (DB):** Point-in-time cutoff timestamps, default procurement budgets, min/max allocations.
7. **Hardcoded Filesystem Paths (FP):** Parquet dataset paths, artifact persistence locations, model directories.
8. **Environment-Specific Values (EV):** Runtime mode flags, CORS policies, prototype override switches.
9. **Credentials, API Keys, and Secrets (CS):** JWT secret keys, worker tokens, broker connection strings.
10. **Mathematical Constants (MC):** Algebraic invariants, probability unit sums ($1.0$), scaling multipliers ($100.0$, $1000$).
11. **Test Fixtures and Synthetic Data (TF):** Unit test budgets, mock purchase costs, fixture identifiers.

---

## 2. Exhaustive Audit Register

| # | File Path | Line(s) | Existing Value | Purpose | Classification | Refactoring Necessary? | Recommended Target Location | Risk of Changing |
|---|---|---|---|---|---|---|---|---|
| **1** | `optimization/economics/flight_economics.py` | 42 | `0.05`, `0.99` | Minimum & maximum bounds for elasticity-adjusted flight sell-through ($\theta_{\text{adj}}$) | **Business Assumption** | **YES** | `FinancialAssumptions.flight_min_sell_through`, `FinancialAssumptions.flight_max_sell_through` | Medium (Affects seat procurement volume for overpriced flights) |
| **2** | `optimization/economics/flight_economics.py` | 30 | `0.85` | Baseline unadjusted flight sell-through probability ($\theta_0$) | **Business Assumption** | Already in Config | `FinancialAssumptions.flight_base_sell_through` | Low |
| **3** | `optimization/economics/flight_economics.py` | 31 | `1.5` | Price elasticity exponent ($\eta$) when contract price exceeds market ceiling | **Business Assumption** | Already in Config | `FinancialAssumptions.flight_price_elasticity` | Low |
| **4** | `optimization/economics/flight_economics.py` | 17–18 | `0.00`, `0.10` | 0% default baseline spoilage vs 10% contractual salvage recovery ($s$) | **Financial Assumption** | Already in Config | `FinancialAssumptions.flight_salvage_rate_default`, `FinancialAssumptions.flight_salvage_rate_optional` | Low |
| **5** | `optimization/economics/flight_economics.py` | 19 | `0.0` | Penalty per unsold seat ($\psi$) | **Financial Assumption** | Already in Config | `FinancialAssumptions.flight_unsold_penalty` | Low |
| **6** | `optimization/economics/hotel_economics.py` | 29 | `0.85` | Baseline hotel room-night sell-through probability ($\theta$) | **Business Assumption** | Already in Config | `FinancialAssumptions.hotel_base_sell_through` | Low |
| **7** | `optimization/economics/hotel_economics.py` | 32 | `0.80` | Customer refund rate on cancellation ($r_{\text{cust}}$) | **Financial Assumption** | Already in Config | `FinancialAssumptions.hotel_customer_refund_rate` | Low |
| **8** | `optimization/economics/hotel_economics.py` | 33 | `0.40` | Room resale probability after cancellation ($f_{\text{resale}}$) | **Business Assumption** | Already in Config | `FinancialAssumptions.hotel_room_resale_probability` | Low |
| **9** | `optimization/economics/hotel_economics.py` | 34 | `0.90` | Discount factor on resold cancelled rooms ($\delta$) | **Financial Assumption** | Already in Config | `FinancialAssumptions.hotel_resale_discount_factor` | Low |
| **10** | `optimization/economics/hotel_economics.py` | 35 | `2.0` | Assumed stay duration (nights) per booking | **Business Assumption** | Already in Config | `FinancialAssumptions.hotel_assumed_stay_duration` | Low |
| **11** | `optimization/economics/hotel_economics.py` | 38 | `0.85` | Supplier refund rate on cancellation for refundable contracts ($r_{\text{supp,cancel}}$) | **Financial Assumption** | Already in Config | `FinancialAssumptions.hotel_supplier_refund_rate_cancel` | Low |
| **12** | `optimization/economics/hotel_economics.py` | 35 | `0.00` | Supplier refund rate on unsold room nights ($r_{\text{supp,unsold}}$) | **Financial Assumption** | Already in Config | `FinancialAssumptions.hotel_supplier_refund_rate_unsold` | Low |
| **13** | `optimization/data/currency.py` | 20 | `{"EUR", "USD", "GBP"}` | Set of verified corporate settlement currencies | **Financial Assumption** | **YES** | `OptimizationConfig.verified_currencies` | Low (Allows adding currencies without modifying class source) |
| **14** | `optimization/config.py` | 45 | `90.0` | Prototype scale rate for EUR to INR conversion | **Financial Assumption** | Already in Config | `FinancialAssumptions.prototype_eur_to_inr_rate` | High (FX changes directly alter scaled ADR values) |
| **15** | `optimization/data/demand.py` | 19 | `2.0` | Default stay duration fallback | **Business Assumption** | Already in Config | `FinancialAssumptions.hotel_assumed_stay_duration` | Low |
| **16** | `optimization/data/demand.py` | 20 | `1.0` | Demand scenario stress multiplier ($\mu_{\text{demand}}$) | **Business Assumption** | **YES** | `FinancialAssumptions.demand_scenario_multiplier` | Medium (Directly scales destination procurement absorption caps) |
| **17** | `optimization/data/demand.py` | 74 | `0.15` | Fallback search-to-booking conversion rate for unseen destinations | **Business Assumption** | **YES** | `FinancialAssumptions.default_search_conversion_rate` | Low |
| **18** | `optimization/data/demand.py` | 75–76 | `2.0`, `1.0` | Fallback average travellers and rooms per booking | **Business Assumption** | **YES** | `FinancialAssumptions.default_travellers_per_booking`, `FinancialAssumptions.default_rooms_per_booking` | Low |
| **19** | `optimization/predictions/hotel_cancellation.py` | 38–40 | `stay_duration`, `90.0` | ADR EUR scaling denominator and FX rate | **Financial Assumption** | Already in Config | `FinancialAssumptions.hotel_assumed_stay_duration`, `prototype_eur_to_inr_rate` | Low |
| **20** | `optimization/predictions/hotel_cancellation.py` | 42–53 | `7`, `30`, `90`, `180`, `365` | Booking lead time cohort discretization buckets | **Prediction Threshold** | **NO** (Fixed by Phase 4 ML Model schema) | Keep in module (Matches trained LightGBM feature encoding) | High if modified (Model schema mismatch) |
| **21** | `optimization/predictions/hotel_cancellation.py` | 67 | `[6, 7, 8, 12]` | High-season peak arrival months | **Prediction Threshold** | **NO** (Fixed by Phase 4 ML Model schema) | Keep in module | High if modified |
| **22** | `optimization/predictions/hotel_cancellation.py` | 118–119 | `0.01`, `0.99` | Cancellation probability clipping boundaries $[\epsilon, 1-\epsilon]$ | **Risk Threshold** | **YES** | `RiskConfig.min_cancellation_prob`, `RiskConfig.max_cancellation_prob` | Low |
| **23** | `optimization/predictions/hotel_cancellation.py` | 116–117 | `0.70`, `0.25` | Bayesian shrinkage weight $\lambda$ and destination prior $p_0$ | **Risk Threshold** | Already in Config | `RiskConfig.bayesian_shrinkage_lambda`, `RiskConfig.hotel_default_cancellation_prior` | Medium |
| **24** | `optimization/predictions/flight_price.py` | 49–54 | `15`, `30`, `2.5`, `150.0` | Representative flight cohort duration and departure buckets | **Prediction Threshold** | **NO** (Fixed by Phase 4 ML Model schema) | Keep in module | High if modified |
| **25** | `optimization/predictions/demand_forecasting.py` | 41 | `30` days | Historical observation window for recent search velocity | **Prediction Threshold** | **YES** | `OptimizationConfig.demand_history_window_days` | Medium |
| **26** | `optimization/predictions/demand_forecasting.py` | 49 | `7.0` days | Search volume forecast normalization horizon | **Prediction Threshold** | **YES** | `OptimizationConfig.demand_forecast_horizon_days` | Low |
| **27** | `optimization/predictions/demand_forecasting.py` | 61 | `10.0` | Default 7-day search volume baseline when no prior data exists | **Prediction Threshold** | **YES** | `OptimizationConfig.default_search_volume` | Low |
| **28** | `optimization/predictions/inventory_forecasting.py` | 41 | `10.0` | Fallback available inventory units on inference exception | **Prediction Threshold** | **YES** | `OptimizationConfig.default_available_inventory` | Low |
| **29** | `optimization/config.py` | 51 | `0.25` | Maximum portfolio spend concentration per destination ($25\%$) | **Risk Threshold** | Already in Config | `RiskConfig.destination_exposure_limit` | Medium |
| **30** | `optimization/config.py` | 54 | `0.20` | Maximum portfolio spend concentration per supplier ($20\%$) | **Risk Threshold** | Already in Config | `RiskConfig.supplier_concentration_limit` | Medium |
| **31** | `optimization/config.py` | 63 | `60.0` | MILP solver time limit (seconds) | **Solver Parameter** | Already in Config | `SolverConfig.time_limit_seconds` | Low |
| **32** | `optimization/config.py` | 64 | `1e-4` | Relative MIP gap optimality tolerance ($0.01\%$) | **Solver Parameter** | Already in Config | `SolverConfig.relative_gap_tolerance` | Low |
| **33** | `optimization/solvers/solver_factory.py` | 35 | `[SCIP, CBC, HIGHS, SAT]` | Fallback backend instantiation sequence | **Solver Parameter** | **YES** | `SolverConfig.fallback_order` | Low |
| **34** | `optimization/evaluation/sensitivity.py` | 43 | `[50k, 100k, 250k, 500k, 1M]` | Default budget sensitivity sweep levels | **Business Assumption** | **YES** | `OptimizationConfig.sensitivity_budget_levels` | Low |
| **35** | `optimization/evaluation/sensitivity.py` | 80 | `[0.10, 0.20, 0.35, 0.50, 1.0]` | Default supplier concentration sweep levels | **Risk Threshold** | **YES** | `OptimizationConfig.sensitivity_supplier_limits` | Low |
| **36** | `optimization/data/loader.py` | 16–21 | Processed parquet filepaths | Relative paths to input datasets | **Filesystem Path** | **YES** | `DataPathsConfig` (configurable in `OptimizationConfig`) | Low |
| **37** | `optimization/predictions/model_registry.py` | 17 | `"data/models"` | Base directory for Phase 4 serialized ML models | **Filesystem Path** | **YES** | `OptimizationConfig.models_base_dir` | Low |
| **38** | `optimization/pipeline.py` | 48 | `"data/optimization"` | Default directory for output recommendations and plans | **Filesystem Path** | Already parameterized | `output_dir` in `OptimizationPipeline.run()` | Low |
| **39** | `backend/app/core/config.py` | 14–15 | `sqlite:///./inventoryiq.db` | Local SQLite database filepaths | **Filesystem Path** | Already in Settings | `Settings.DATABASE_URL` | Low |
| **40** | `backend/app/core/config.py` | 18, 23 | `"tbo_inventoryiq_super_secret..."` | Prototype JWT Secret & Worker Token | **Credentials / Secret** | Already in Settings (Env override) | `Settings.SECRET_KEY`, `Settings.WORKER_SECRET_TOKEN` | High in Prod |
| **41** | `backend/app/core/config.py` | N/A | Missing `ENVIRONMENT` | Target environment tag | **Environment Value** | **YES** | `Settings.ENVIRONMENT: str = "development"` | Low |
| **42** | `optimization/economics/hotel_economics.py` | 42–58 | State space formulas | Net contribution & probability equations | **Mathematical Constant** | **NO** (Preserve equation integrity) | Keep in formula | Extreme (Core economic logic) |
| **43** | `optimization/economics/flight_economics.py` | 79–83 | Analytical break-even formula | $\theta^* = \frac{c(1-s) + \psi}{p - sc + \psi}$ | **Mathematical Constant** | **NO** (Preserve analytical formula) | Keep in formula | Extreme (Core analytical benchmark) |

---

## 3. Detailed Audit by Functional Module

### 3.1 Flight Economics (`optimization/economics/flight_economics.py`)
* **Finding 1.1:** Elasticity-adjusted sell-through bounds (`0.05` and `0.99`) were hardcoded on line 42:
  ```python
  return max(0.05, min(0.99, theta_adj))
  ```
  *Refactoring Action:* Refactor into `FinancialAssumptions.flight_min_sell_through` and `FinancialAssumptions.flight_max_sell_through` with cross-field Pydantic validation ($0.0 \le \text{min} \le \text{max} \le 1.0$).
* **Finding 1.2:** Mathematical analytical formulas for break-even sell-through:
  $$\theta^* = \frac{c(1-s) + \psi}{p - sc + \psi}$$
  *Refactoring Action:* Preserved exactly inside the method; these are mathematical derivations, not configurable business parameters.

### 3.2 Hotel Economics (`optimization/economics/hotel_economics.py`)
* **Finding 2.1:** Four-outcome probability partitioning:
  $$P(S_1) = 1 - \theta, \quad P(S_2) = \theta(1 - p_c), \quad P(S_{3a}) = \theta p_c f_{\text{resale}}, \quad P(S_{3b}) = \theta p_c (1 - f_{\text{resale}})$$
  *Refactoring Action:* Preserved as exact mathematical formulas. All commercial rate parameters ($r_{\text{cust}}$, $f_{\text{resale}}$, $\delta$, $r_{\text{supp,cancel}}$, $r_{\text{supp,unsold}}$) are already properly sourced from `FinancialAssumptions`.

### 3.3 Currency & Internationalization (`optimization/data/currency.py`)
* **Finding 3.1:** `VERIFIED_PRODUCTION_CURRENCIES = {"EUR", "USD", "GBP"}` is statically declared on the class.
  *Refactoring Action:* Add `verified_currencies: Set[str]` to `OptimizationConfig` with default `{"EUR", "USD", "GBP"}` so enterprise users can configure active bank settlement currencies dynamically without editing source code.

### 3.4 Demand & Funnel Conversion (`optimization/data/demand.py`)
* **Finding 4.1:** Fallback conversion rate (`0.15`), average travellers (`2.0`), and average rooms (`1.0`) were embedded in fallback branches.
  *Refactoring Action:* Move to `FinancialAssumptions` as:
  - `demand_scenario_multiplier: float = 1.0`
  - `default_search_conversion_rate: float = 0.15`
  - `default_travellers_per_booking: float = 2.0`
  - `default_rooms_per_booking: float = 1.0`

### 3.5 Prediction Services (`optimization/predictions/`)
* **Finding 5.1:** In `hotel_cancellation.py`, probability clipping values `0.01` and `0.99` were hardcoded:
  ```python
  return float(np.clip(calibrated_prob, 0.01, 0.99))
  ```
  *Refactoring Action:* Move to `RiskConfig` as `min_cancellation_prob: float = 0.01` and `max_cancellation_prob: float = 0.99`.
* **Finding 5.2:** Feature cohort encodings (`lead_time_bucket`, `meal`, `market_segment`, `duration_hours`):
  *Refactoring Action:* Kept in service files. These are not business assumptions; they are strict syntactic feature contracts required by the pre-trained LightGBM scikit-learn preprocessing pipelines.

### 3.6 Sensitivity Sweeps & Evaluation (`optimization/evaluation/sensitivity.py`)
* **Finding 6.1:** Budget sweep steps `[50k, 100k, 250k, 500k, 1M]` and concentration limits `[0.10, 0.20, 0.35, 0.50, 1.0]` were hardcoded in method signatures.
  *Refactoring Action:* Add `sensitivity_budget_levels` and `sensitivity_supplier_limits` to `OptimizationConfig`.

### 3.7 Data Paths (`optimization/data/loader.py`)
* **Finding 7.1:** Relative parquet dataset paths in `DatasetLoader.DEFAULT_PATHS`.
  *Refactoring Action:* Add optional `data_paths: Optional[Dict[str, str]]` to `OptimizationConfig` defaulting to the canonical Phase 1 paths.

---

## 4. Configuration Model Extension Blueprint (Phase 2)

All refactored configurable values are integrated into `optimization/config.py` following strict Pydantic v2 patterns:

```python
class FinancialAssumptions(BaseModel):
    # Hotel assumptions
    hotel_base_sell_through: float = Field(0.85, ge=0.0, le=1.0)
    hotel_customer_refund_rate: float = Field(0.80, ge=0.0, le=1.0)
    hotel_supplier_refund_rate_cancel: float = Field(0.85, ge=0.0, le=1.0)
    hotel_supplier_refund_rate_unsold: float = Field(0.00, ge=0.0, le=1.0)
    hotel_room_resale_probability: float = Field(0.40, ge=0.0, le=1.0)
    hotel_resale_discount_factor: float = Field(0.90, ge=0.1, le=1.5)
    hotel_assumed_stay_duration: float = Field(2.0, ge=1.0, le=14.0)

    # Flight assumptions
    flight_base_sell_through: float = Field(0.85, ge=0.0, le=1.0)
    flight_min_sell_through: float = Field(0.05, ge=0.0, le=1.0)
    flight_max_sell_through: float = Field(0.99, ge=0.0, le=1.0)
    flight_salvage_rate_default: float = Field(0.00, ge=0.0, le=1.0)
    flight_salvage_rate_optional: float = Field(0.10, ge=0.0, le=1.0)
    flight_unsold_penalty: float = Field(0.0, ge=0.0)
    flight_price_elasticity: float = Field(1.5, ge=0.1, le=5.0)

    # Currency & Demand Assumptions
    prototype_eur_to_inr_rate: float = Field(90.0, gt=0.0)
    demand_scenario_multiplier: float = Field(1.0, gt=0.0)
    default_search_conversion_rate: float = Field(0.15, ge=0.0, le=1.0)
    default_travellers_per_booking: float = Field(2.0, ge=1.0)
    default_rooms_per_booking: float = Field(1.0, ge=1.0)
```

### Cross-Field Validations Enforced
1. **Flight Sell-Through Bounds:** `flight_min_sell_through <= flight_max_sell_through`.
2. **Category Budget Consistency:** `hotel_budget_min <= hotel_budget_max`, `flight_budget_min <= flight_budget_max`.
3. **Master Budget Coverage:** `hotel_budget_min + flight_budget_min <= total_budget`.
4. **Cancellation Risk Bounds:** `min_cancellation_prob <= max_cancellation_prob`.
5. **Positive Currency Rates:** `prototype_eur_to_inr_rate > 0.0`.
6. **Positive Solver Time Limits:** `time_limit_seconds > 0.0`.

---

## 5. Configuration Traceability & Reproducibility (Phase 4)

To guarantee 100% mathematical auditability and deterministic reproducibility:
1. Every configuration instance computes a deterministic SHA-256 fingerprint:
   $$\text{config\_fingerprint} = \text{SHA256}(\text{JSON}(\text{config\_dict}))$$
2. The fingerprint, timestamp, solver metadata, and exact financial/risk parameters are embedded into:
   - `OptimizationPlan.config_summary`
   - `OptimizationPlan.solver_metadata["config_fingerprint"]`
   - Canonical `optimization_summary.json`
   - Isolated run archive `data/optimization/optimization_runs/{run_id}/optimization_summary.json`

---

## 6. Conclusion

By centralizing these assumptions:
- **Zero changes** to existing default business values or mathematical formulas.
- **100% backwards compatibility** is preserved for all existing test suites.
- Quantitative analysts can safely tune risk tolerances, FX rates, and commercial terms via validated configuration without codebase modifications.
