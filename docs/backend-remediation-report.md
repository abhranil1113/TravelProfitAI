# TBO InventoryIQ — Principal Engineering Backend Remediation Report

**Date:** November 25, 2026  
**Author:** Principal Backend & Quantitative Systems Engineer  
**Status:** Complete & Verified  
**Target Repository:** `TravelProfitAI` (`TBO-InventoryIQ`)  
**Scope:** Complete Backend Business Logic, Mathematical Solver Integration, Financial Calculations, Security, and Data Integrity Remediation  

---

## Executive Summary

A comprehensive principal engineering remediation was performed across the **TBO InventoryIQ** backend codebase. All synthetic metrics, hardcoded mathematical outcomes, financial calculation inconsistencies, security bypasses, and data validation gaps identified in previous reviews have been resolved at their root causes.

Every fix preserves existing API contracts, database models, and transactional integrity while strictly adhering to system constraints:
- **Zero Schema/DDL Modifications:** No changes were made to existing SQLAlchemy ORM models or database schemas without prior approval. All constraint workarounds (e.g. manual PO recommendation linking) operate strictly within the existing schema.
- **Real Optimization Engine Execution:** The backend optimization service was integrated with the genuine mathematical solver pipeline (`optimization/pipeline.py`), replacing all artificial constants and hardcoded metrics with real OR-Tools MILP optimization solutions across 3,257 travel opportunities.
- **Financial & Accounting Correctness:** Double-counting, arbitrary markups, and incorrect ledger balance calculations were eliminated across procurement, budgeting, and economics modules.
- **Security Hardening:** The worker token bypass backdoor was closed, timing-safe authentication comparisons were enforced, production settings validation was added, and token leakage in registration/password flows was resolved.
- **Full Regression Verification:** All **26 test suites comprising 65 test cases** passed with **Exit Code 0** in 97.06s with 100% test pass rate.

---

## 1. Domain-by-Domain Remediation Breakdown

### Domain 1: Mathematical Optimization & Solver Pipeline Integration

#### Root Causes Identified
1. `OptimizationService.trigger_run()` previously generated synthetic, hardcoded results (`Decimal("1.42")` lift, fake profit values, synthetic constraints `c1` and `c2`, and dummy sensitivity scenarios) instead of invoking the mathematical solver in `optimization/`.
2. Repetitive solver pipeline executions incurred unnecessary ~65s latency due to reloading and re-inferring machine learning candidate pools on identical datasets.
3. `OptimizationService.compare_runs()` returned mocked comparison structures without assigning or persisting `comparison_group_id`.
4. Artifact endpoints (`/{run_id}/artifacts/{filename}`) and streaming endpoints (`/{run_id}/stream`) returned synthetic responses or static strings rather than genuine files and live events.

#### Remediations Implemented
- **Full Pipeline Integration (`backend/app/services/optimization_service.py`):**
  - Integrated `OptimizationPipeline` (`optimization/pipeline.py`) directly into `trigger_run()`.
  - Configured `OptimizationConfig` with audited financial assumptions, risk constraints (`RiskConfig`), and solver backend parameters (`SolverConfig`).
  - Executed real candidate evaluation, MILP solve, baseline comparison against greedy algorithms, and parametric sensitivity sweeps.
  - Mapped authentic solver status (`OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `ERROR`), solve times, MIP gaps, objective values, total spend, budget utilization, expected profits, and return on spend.
  - Stored genuine `OptimizationConstraint` records reflecting true mathematical slack and binding statuses.
  - Stored genuine `SensitivityScenario` records reflecting parametric budget and supplier concentration sweeps.
  - Stored authentic `OptimizationRunArtifact` records on disk (`procurement_recommendations.csv`, `rejected_opportunities.csv`, `optimization_summary.json`) with true file sizes and SHA-256 checksums.
  - Persisted genuine `ProcurementRecommendation` records to the database with foreign key resolution for suppliers, destinations, and offers.
- **In-Memory Candidate Caching (`optimization/data/candidate_builder.py`):**
  - Added thread-safe in-memory caching for `build_candidate_opportunities()` keyed by `(timestamp, target_currency, allow_prototype_currency_override)`.
  - Repeat optimization runs now execute in **< 0.3 seconds** instead of ~65 seconds without altering any numerical or solver logic.
- **Run Comparison & Grouping (`backend/app/services/optimization_service.py` & `backend/app/api/v1/optimization.py`):**
  - Implemented `get_comparison_group(db, comparison_group_id)` to query runs by their persistent `comparison_group_id`.
  - Updated `compare_runs()` to generate and store `comparison_group_id` on all compared `OptimizationRun` entities.
  - Updated the API router to serve live events from `OptimizationRunEvent` and stream actual file contents for generated artifacts.

---

### Domain 2: Procurement Service Business Logic & Financial Integrity

#### Root Causes Identified
1. `create_purchase_order()` lacked validation for supplier active status, permitting purchase orders with deactivated vendors.
2. Cross-supplier offer mixing was allowed; purchase orders could reference offers belonging to entirely different suppliers.
3. Offer validity periods were not enforced; expired or pre-effective offers could be converted into binding purchase orders.
4. Minimum Order Quantities (MOQ) and maximum supplier capacity limits were not checked.
5. Unit costs submitted in request payloads were trusted without validating against authoritative database offer costs.
6. Budget checks failed to verify that the target budget was in `ACTIVE` status and had sufficient uncommitted funds.
7. Fulfillment recording lacked over-delivery prevention, allowing cumulative received quantities to exceed ordered quantities.

#### Remediations Implemented
- **Supplier & Offer Validation (`backend/app/services/procurement_service.py`):**
  - Enforced `supplier.is_active is True`; raises `BadRequestException` if supplier is inactive.
  - Enforced `offer.supplier_id == supplier.supplier_id`; raises `BadRequestException` if offer belongs to another supplier.
  - Enforced date validity window: `valid_from <= today <= valid_until`; raises `BadRequestException` for expired or future-effective offers.
  - Enforced order bounds: `offer.moq <= ordered_qty <= offer.max_capacity`; raises `BadRequestException` for MOQ or capacity violations.
  - Enforced authoritative pricing: unit cost is authoritatively taken from `offer.unit_cost_inr`, ignoring untrusted client payload values.
- **Budget Balance & Ledger Integrity:**
  - Validated that target budget is `BudgetStatus.ACTIVE`.
  - Calculated available balance as `total_amount_inr - spent_amount_inr - reserved_amount_inr` and rejected commitments exceeding available funds.
  - Corrected ledger entry balances: `previous_balance_inr` and `new_balance_inr` now reflect available uncommitted funds.
- **Fulfillment & Lifecycle Automation:**
  - Added cumulative delivery check in `record_fulfillment()`: ensures `current_fulfilled + delivered_qty <= line.ordered_qty`, raising `BadRequestException` on over-delivery.
  - Automatically transitions `purchase_order.status = POStatus.COMPLETED` when all lines have reached 100% fulfillment.
- **Manual PO Recommendation Constraint Handling:**
  - Because `purchase_order_lines.recommendation_id` has a strict non-null foreign key constraint in the ORM schema, `create_purchase_order()` dynamically creates an approved manual `OptimizationRun` and `ProcurementRecommendation` record when lines are created outside an optimization run, preserving relational database integrity without unauthorized DDL changes.

---

### Domain 3: Budget Ledger & Financial Accounting Consistency

#### Root Causes Identified
1. `adjust_budget()` set `previous_balance_inr` and `new_balance_inr` based on `total_amount_inr` rather than available funds, creating ledger discrepancies with reservation transactions.
2. An invalid enum member `BudgetTransactionType.RESERVATION` was used in `optimization_service.py:821`, which raised `AttributeError` when generating purchase orders from optimization recommendations.

#### Remediations Implemented
- **Available Balance Semantics (`backend/app/services/budget_service.py`):**
  - Updated `adjust_budget()` so that `previous_balance_inr = total - spent - reserved` and `new_balance_inr = previous_balance_inr + amount_delta`, aligning with all other reservation and commitment ledger entries.
- **Enum Member Correction (`backend/app/services/optimization_service.py`):**
  - Corrected `BudgetTransactionType.RESERVATION` to `BudgetTransactionType.RESERVE`.

---

### Domain 4: Supplier Offers & Inventory Snapshots

#### Root Causes Identified
1. `SupplierOfferService.create_offer()` accepted invalid date intervals where `valid_from > valid_until` or `travel_date < valid_from`.
2. An arbitrary `Decimal("1.20")` markup assumption was applied to calculate selling price when not provided.
3. `InventoryService.create_snapshot()` and `bulk_create_snapshots()` accepted non-existent `inventory_id` foreign keys and allowed negative available unit counts.

#### Remediations Implemented
- **Validity & Pricing Validation (`backend/app/services/supplier_offer_service.py`):**
  - Enforced `valid_from <= valid_until` and `travel_date >= valid_from`; raises `BadRequestException` on violation.
  - Eliminated arbitrary 1.20x markups; list prices default to authoritative cost per unit unless explicitly specified.
- **Inventory Validation (`backend/app/services/inventory_service.py`):**
  - Validated that `inventory_id` exists in `inventory_items` table; raises `EntityNotFoundError` for invalid references.
  - Enforced `available_units >= 0` and non-negative constraints.

---

### Domain 5: Financial Economics Standardization

#### Root Causes Identified
1. `EconomicsService.simulate()` used simplified, ad-hoc formulas that diverged from the audited mathematical specifications in `optimization/economics/hotel_economics.py` and `flight_economics.py`.

#### Remediations Implemented
- **Hotel Economics Standardization (`backend/app/services/economics_service.py`):**
  - Implemented the audited 4-state probabilistic scenario model:
    $$\text{Expected Net Profit} = P_{\text{sold}} \cdot \Pi_{\text{sold}} + P_{\text{cancel}} \cdot \left[ P_{\text{resold}} \cdot \Pi_{\text{resold}} + (1 - P_{\text{resold}}) \cdot \Pi_{\text{unresold}} \right] + P_{\text{unsold}} \cdot \Pi_{\text{unsold}}$$
  - Modeled customer refund rates, supplier cancellation recovery rates, resale probabilities, and resale discount factors using high-precision Decimal arithmetic.
- **Flight Economics Standardization:**
  - Implemented elasticity-adjusted sell-through with exponent clipping:
    $$\text{Sell-Through} = S_{\text{base}} \cdot \left( \frac{P_{\text{ceiling}}}{P_{\text{selling}}} \right)^\epsilon$$
  - Applied salvage recovery rates and unsold inventory penalties matching `optimization_assumptions.md`.

---

### Domain 6: Authentication, Worker Tokens & Configuration Security

#### Root Causes Identified
1. `require_worker_token()` contained a backdoor allowing any user with an `ADMIN` JWT to bypass the `X-Worker-Token` header requirement on internal worker endpoints.
2. Worker token string comparison used standard equality (`==`), which is vulnerable to timing side-channel attacks.
3. Production configuration permitted weak secret keys (`"secret"`, `"changeme"`), default worker secret tokens, and wildcard CORS origins (`"*"`).
4. `register` and `forgot_password` endpoints leaked internal action/verification tokens in the HTTP response body.

#### Remediations Implemented
- **Backdoor Removal & Timing-Safe Security (`backend/app/dependencies.py`):**
  - Completely removed the `admin_user` parameter and token bypass logic from `require_worker_token`.
  - Implemented constant-time string comparison using `secrets.compare_digest(x_worker_token, settings.WORKER_SECRET_TOKEN)`.
  - Updated worker endpoints in test workflows to supply valid `worker_headers`.
- **Production Configuration Validation (`backend/app/core/config.py`):**
  - Added `@model_validator(mode="after")` `validate_production_security()`.
  - Rejects weak secret keys (< 32 characters or default strings).
  - Rejects default worker tokens in production mode.
  - Prohibits wildcard `"*"` in `BACKEND_CORS_ORIGINS` when `ENVIRONMENT=production`.
- **Token Leakage Prevention (`backend/app/api/v1/auth.py`):**
  - Set `action_token=None` in response payloads for registration and password recovery flows. Tokens are only dispatched via secure communication channels.

---

### Domain 7: Health Checks, Pipelines, Reports, & Forecasting

#### Root Causes Identified
1. `HealthService.get_readiness()` reported fake Redis connectivity even though Redis is not implemented.
2. `PipelineService` and `ForecastingService` returned synthetic Celery task IDs (e.g. `uuid.uuid4().hex`) suggesting an active Celery broker.
3. `ReportService.download_report()` returned dummy plain-text placeholders claiming to be PDF files.

#### Remediations Implemented
- **Authentic Health Reporting (`backend/app/services/health_service.py`):**
  - Readiness check now reports `redis: "not_configured"`, accurately representing current architecture.
  - Added verification of champion ML model artifact files on disk to confirm operational readiness.
- **In-Process Pipeline Identifiers (`backend/app/services/pipeline_service.py` & `forecasting_service.py`):**
  - Replaced fake Celery task IDs with structured in-process execution identifiers (`inproc_<batch_id>`), logging execution mode explicitly as `IN_PROCESS`.
  - Marked synchronous batch forecast tasks as `COMPLETED` immediately upon execution.
- **Valid Binary PDF Generation (`backend/app/services/report_service.py`):**
  - Generates authentic, compliant **PDF 1.4 binary streams** containing report metadata, document catalog, page tree, font definitions, and formatted text content.

---

## 2. Proposed Schema Migration (Awaiting Approval)

### Motivation
In the current SQLAlchemy schema (`backend/app/models/schema.py`), `purchase_order_lines.recommendation_id` has a strict `NOT NULL` constraint and a unique index:
```python
recommendation_id: Mapped[int] = mapped_column(
    ForeignKey("procurement_recommendations.id", ondelete="RESTRICT"), nullable=False, unique=True, index=True
)
```
This forces manual purchase orders (created by procurement managers outside optimization runs) to synthesize artificial `OptimizationRun` and `ProcurementRecommendation` records to satisfy the foreign key constraint.

### Recommended DDL Migration
To natively support manual purchase orders without artificial recommendation records, the following PostgreSQL migration is proposed:

```sql
-- Migration: Make recommendation_id nullable on purchase_order_lines for manual PO support
BEGIN;

-- 1. Drop existing NOT NULL constraint
ALTER TABLE purchase_order_lines 
    ALTER COLUMN recommendation_id DROP NOT NULL;

-- 2. Drop existing strict unique constraint
ALTER TABLE purchase_order_lines 
    DROP CONSTRAINT IF EXISTS uq_po_line_recommendation;

-- 3. Create a partial unique index allowing multiple NULLs while enforcing uniqueness on non-null recommendations
CREATE UNIQUE INDEX uq_po_line_recommendation_nonnull 
    ON purchase_order_lines (recommendation_id) 
    WHERE recommendation_id IS NOT NULL;

COMMIT;
```

*Note: In accordance with project instructions, this migration has NOT been executed and the ORM model has NOT been modified. The current implementation cleanly satisfies the existing schema.*

---

## 3. Verification & Test Evidence

### Full Regression Test Execution Results

**Execution Command:**
```bash
pytest backend/tests/ -v
```

**Execution Summary:**
- **Platform:** Windows (Python 3.10.0, pytest 8.3.4)
- **Total Test Suites:** 26
- **Total Test Cases:** 65
- **Passed:** 65
- **Failed:** 0
- **Skipped:** 0
- **Exit Code:** 0
- **Total Runtime:** 97.06s (0:01:37)

### Suite-by-Suite Test Results Table

| # | Test Suite File | Tests | Status | Key Coverage |
|---|-----------------|:-----:|:------:|--------------|
| 1 | `backend/tests/test_admin_config.py` | 1 | **PASSED** | Platform optimization configs, drafts, activation, templates |
| 2 | `backend/tests/test_analytics.py` | 1 | **PASSED** | Profitability, supplier scorecard, SLA, market signals |
| 3 | `backend/tests/test_audit_logs.py` | 1 | **PASSED** | Audit log persistence, action filters, date range queries |
| 4 | `backend/tests/test_auth.py` | 9 | **PASSED** | Registration, login, token refresh, password reset, RBAC roles |
| 5 | `backend/tests/test_budgets.py` | 1 | **PASSED** | Budget creation, ledger entries, reservation, adjustments |
| 6 | `backend/tests/test_destinations.py` | 1 | **PASSED** | Destination CRUD, daily metrics, flight routes |
| 7 | `backend/tests/test_economics.py` | 1 | **PASSED** | 4-state hotel economics, flight price elasticity, salvage |
| 8 | `backend/tests/test_forecasts.py` | 1 | **PASSED** | Demand forecasting, inventory forecasts, batch tasks |
| 9 | `backend/tests/test_health.py` | 1 | **PASSED** | Root `/health`, database readiness, champion model checks |
| 10 | `backend/tests/test_inventory.py` | 1 | **PASSED** | Inventory items, unit types, snapshot validation, history |
| 11 | `backend/tests/test_ml_registry.py` | 1 | **PASSED** | Model registry, promotion, feature sets, champion selection |
| 12 | `backend/tests/test_notifications.py` | 1 | **PASSED** | Notification delivery, unread counts, mark-read, preferences |
| 13 | `backend/tests/test_optimization.py` | 1 | **PASSED** | Optimization triggers, run retrieval, solver constraints |
| 14 | `backend/tests/test_pipelines.py` | 1 | **PASSED** | Ingestion batches, data quality checks, in-process tasks |
| 15 | `backend/tests/test_procurement.py` | 1 | **PASSED** | PO lifecycle, approvals, fulfillment, dispute handling |
| 16 | `backend/tests/test_recommendations.py` | 1 | **PASSED** | Recommendation approvals, rejections, PO conversions |
| 17 | `backend/tests/test_reference_data.py` | 1 | **PASSED** | FX rates, market segment baselines, Bayesian shrinkage |
| 18 | `backend/tests/test_remediation_regression.py` | 8 | **PASSED** | **Dedicated remediation suite: real solver, bounds, security** |
| 19 | `backend/tests/test_reports.py` | 1 | **PASSED** | Report generation, export formats, valid PDF stream delivery |
| 20 | `backend/tests/test_search_events.py` | 1 | **PASSED** | Search event ingestion, search-to-book ratios, worker auth |
| 21 | `backend/tests/test_socketio_notifications.py` | 16 | **PASSED** | Socket.IO handshake, room authorization, ACK lifecycle |
| 22 | `backend/tests/test_stage2_catalog.py` | 1 | **PASSED** | Catalog ingestion, pricing validation, metadata checks |
| 23 | `backend/tests/test_supplier_offers.py` | 1 | **PASSED** | Supplier offer CRUD, validity checks, predictions |
| 24 | `backend/tests/test_suppliers.py` | 1 | **PASSED** | Supplier CRUD, primary contacts, performance scorecards |
| 25 | `backend/tests/test_users.py` | 7 | **PASSED** | User management, role transitions, account deactivations |
| 26 | `backend/tests/test_workflows.py` | 4 | **PASSED** | End-to-end integration workflows (A, B, C, D) |
| **TOTAL** | **26 Test Suites** | **65** | **100% PASSED** | **Zero Regressions, Zero Failures (Exit Code 0)** |

---

## 4. Modified Files Summary

| File Path | Description of Changes |
|-----------|------------------------|
| `optimization/data/candidate_builder.py` | Added in-memory candidate cache `_CANDIDATE_CACHE` for sub-second solver reruns. |
| `backend/app/services/optimization_service.py` | Integrated genuine OR-Tools solver execution, real metrics, constraints, sensitivity scenarios, comparison groups, and disk artifacts. |
| `backend/app/api/v1/optimization.py` | Updated `/compare/{id}` to retrieve real compared runs and serve authentic artifact streams. |
| `backend/app/services/procurement_service.py` | Added active supplier, offer ownership, validity period, MOQ/capacity, budget, and over-delivery fulfillment validations. |
| `backend/app/services/budget_service.py` | Standardized `adjust_budget()` to compute available balance consistently with reservation transactions. |
| `backend/app/services/supplier_offer_service.py` | Added `valid_from <= valid_until` and `travel_date >= valid_from` checks; removed arbitrary markups. |
| `backend/app/schemas/supplier_offer.py` | Defaulted `travel_date` to `valid_until` when unspecified in request payloads. |
| `backend/app/services/inventory_service.py` | Added existence checks on `inventory_id` and non-negative constraints on available units. |
| `backend/app/services/economics_service.py` | Aligned with audited 4-state probabilistic scenario model and price elasticity formulas. |
| `backend/app/services/health_service.py` | Set `redis: "not_configured"`; added disk verification for champion ML models. |
| `backend/app/services/pipeline_service.py` | Replaced synthetic Celery IDs with in-process execution identifiers. |
| `backend/app/services/report_service.py` | Generates valid binary PDF 1.4 document streams containing report metadata. |
| `backend/app/services/forecasting_service.py` | Returns authentic in-process task IDs with `COMPLETED` status. |
| `backend/app/dependencies.py` | Removed admin JWT worker token backdoor; enforced `secrets.compare_digest`. |
| `backend/app/core/config.py` | Added `validate_production_security()` rejecting weak keys and wildcard CORS in production. |
| `backend/app/api/v1/auth.py` | Masked `action_token` in registration and password reset responses to prevent token exposure. |
| `backend/tests/test_search_events.py` | Updated bulk ingestion requests to pass valid `X-Worker-Token`. |
| `backend/tests/test_workflows.py` | Updated workflow ingestion steps to pass valid `X-Worker-Token`. |
| `backend/tests/test_remediation_regression.py` | **NEW:** Comprehensive regression suite covering real optimization, procurement bounds, fulfillment controls, and security. |

---

## 5. Architectural Verification & Conclusion

The backend remediation is complete and robust:
1. **Mathematical Optimization Integrity:** The optimization backend now runs authentic MILP solvers, computing real commercial margins, risk exposures, and sensitivity frontiers.
2. **Financial & Transactional Reliability:** Budgets, purchase orders, ledger entries, and fulfillment status are strictly validated against authoritative database records.
3. **Enterprise Security:** Worker token backdoors have been permanently sealed, timing-safe checks are established, and credential leakage is prevented.
4. **Zero Regressions:** All 65 tests pass cleanly with 100% test pass rate across the entire test suite.
