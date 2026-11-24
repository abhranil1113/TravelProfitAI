# TBO InventoryIQ — Complete Database Schema Audit (180 REST API Endpoints)

This document provides the formal audit and endpoint-to-model mapping across all 180 REST API endpoints in the 22 business domains.

## 1. Domain Summary

| # | Domain | Endpoints | T1 | T2 | Primary DB Models | Support Status |
|---|---|---|---|---|---|---|
| 1 | Authentication & Session | 10 | 10 | 0 | `RefreshToken, User, UserActionToken` | 100% Fully Supported |
| 2 | User Management | 9 | 7 | 2 | `RefreshToken, User, UserActionToken` | 100% Fully Supported |
| 3 | Destinations | 7 | 5 | 2 | `CustomerSearchEvent, Destination, DestinationDailyMetrics` | 100% Fully Supported |
| 4 | Suppliers & Contacts | 13 | 10 | 3 | `PurchaseOrder, Supplier, SupplierContact, SupplierOffer, SupplierPerformanceSnapshot` | 100% Fully Supported |
| 5 | Inventory Items & Snapshots | 8 | 4 | 4 | `InventoryItem, InventorySnapshot, SupplierOffer` | 100% Fully Supported |
| 6 | Supplier Offers | 7 | 6 | 1 | `IngestionBatch, InventorySnapshot, OfferPrediction, SupplierOffer` | 100% Fully Supported |
| 7 | Reference Data | 9 | 5 | 4 | `ExchangeRate, MarketSegmentBaseline, MarketSignal` | 100% Fully Supported |
| 8 | Data Pipeline & Quality | 6 | 0 | 6 | `DataQualityReport, IngestionBatch` | 100% Fully Supported |
| 9 | Feature Sets & ML Registry | 12 | 4 | 8 | `FeatureSet, MLModel, ModelTrainingRun` | 100% Fully Supported |
| 10 | Predictions & Forecasts | 6 | 4 | 2 | `DestinationDailyMetrics, DestinationDemandForecast, DestinationInventoryForecast, MLModel, OfferPrediction` | 100% Fully Supported |
| 11 | Admin Config | 9 | 7 | 2 | `OptimizationConfigTemplate, PlatformOptimizationConfig` | 100% Fully Supported |
| 12 | Budgets & Ledger | 9 | 9 | 0 | `BudgetLedgerEntry, ProcurementBudget` | 100% Fully Supported |
| 13 | Optimization Runs | 20 | 18 | 2 | `BudgetLedgerEntry, OptimizationConstraint, OptimizationRun, OptimizationRunArtifact, OptimizationRunEvent, ProcurementBudget, ProcurementRecommendation, PurchaseOrder, PurchaseOrderLine, SensitivityScenario` | 100% Fully Supported |
| 14 | Recommendations & Rejections | 10 | 10 | 0 | `OfferPrediction, ProcurementRecommendation, RejectedOpportunity` | 100% Fully Supported |
| 15 | Purchase Orders & Fulfillment | 11 | 9 | 2 | `BudgetLedgerEntry, ProcurementBudget, ProcurementRecommendation, PurchaseOrder, PurchaseOrderFulfillment, PurchaseOrderLine` | 100% Fully Supported |
| 16 | Reports & Schedules | 11 | 4 | 7 | `Report, ReportSchedule` | 100% Fully Supported |
| 17 | Notifications | 8 | 6 | 2 | `Notification, NotificationDelivery, NotificationPreference` | 100% Fully Supported |
| 18 | Search Events | 4 | 0 | 4 | `CustomerSearchEvent` | 100% Fully Supported |
| 19 | Analytics | 4 | 4 | 0 | `CustomerSearchEvent, DestinationDailyMetrics, Notification, OfferPrediction, OptimizationRun, ProcurementBudget, ProcurementRecommendation, PurchaseOrderFulfillment, Supplier, SupplierOffer, SupplierPerformanceSnapshot` | 100% Fully Supported |
| 20 | Economics | 1 | 1 | 0 | `Stateless` | 100% Fully Supported |
| 21 | Audit Logs | 2 | 2 | 0 | `Stateless` | 100% Fully Supported |
| 22 | Health & System | 4 | 3 | 1 | `MLModel + ML Registry` | 100% Fully Supported |

---

## 2. Complete 180-Endpoint Coverage Matrix

| # | Method | Path | Purpose | Roles | Tier | Database Models | Classification |
|---|---|---|---|---|---|---|---|
| 1 | `POST` | `/auth/register` | Admin-only account creation; sends verification email | `A` | `T1` | `User, UserActionToken, AuditLog` | FULLY SUPPORTED |
| 2 | `POST` | `/auth/login` | Email + password -> tokens; updates last_login_at | `PUB` | `T1` | `User, RefreshToken, AuditLog` | FULLY SUPPORTED |
| 3 | `POST` | `/auth/refresh` | Rotate refresh token; reuse detection | `PUB` | `T1` | `RefreshToken, User, AuditLog` | FULLY SUPPORTED |
| 4 | `POST` | `/auth/logout` | Revoke current refresh token | `ALL` | `T1` | `RefreshToken, AuditLog` | FULLY SUPPORTED |
| 5 | `POST` | `/auth/logout-all` | Revoke all sessions for user | `ALL` | `T1` | `RefreshToken, AuditLog` | FULLY SUPPORTED |
| 6 | `POST` | `/auth/verify-email` | Consume UserActionToken -> set email_verified_at | `PUB` | `T1` | `UserActionToken, User, AuditLog` | FULLY SUPPORTED |
| 7 | `POST` | `/auth/forgot-password` | Send reset email | `PUB` | `T1` | `User, UserActionToken, AuditLog` | FULLY SUPPORTED |
| 8 | `POST` | `/auth/reset-password` | Consume reset token -> new password hash | `PUB` | `T1` | `UserActionToken, User, RefreshToken, AuditLog` | FULLY SUPPORTED |
| 9 | `POST` | `/auth/change-password` | Authenticated password change | `ALL` | `T1` | `User, RefreshToken, AuditLog` | FULLY SUPPORTED |
| 10 | `GET` | `/auth/me` | Current user profile + role + permissions | `ALL` | `T1` | `User` | FULLY SUPPORTED |
| 11 | `GET` | `/users` | List users (filter role, is_active, search) | `A` | `T1` | `User` | FULLY SUPPORTED |
| 12 | `POST` | `/users` | Create user with explicit role | `A` | `T1` | `User, UserActionToken, AuditLog` | FULLY SUPPORTED |
| 13 | `GET` | `/users/{id}` | User detail | `A / self` | `T1` | `User` | FULLY SUPPORTED |
| 14 | `PATCH` | `/users/{id}` | Update name/role/active/permissions | `A` | `T1` | `User, AuditLog` | FULLY SUPPORTED |
| 15 | `POST` | `/users/{id}/deactivate` | Soft-disable + revoke tokens | `A` | `T1` | `User, RefreshToken, AuditLog` | FULLY SUPPORTED |
| 16 | `POST` | `/users/{id}/reactivate` | Re-enable | `A` | `T1` | `User, AuditLog` | FULLY SUPPORTED |
| 17 | `POST` | `/users/{id}/unlock` | Clear lockout counters | `A` | `T1` | `User, AuditLog` | FULLY SUPPORTED |
| 18 | `POST` | `/users/{id}/force-password-reset` | Send reset + revoke sessions | `A` | `T2` | `User, UserActionToken, RefreshToken, AuditLog` | FULLY SUPPORTED |
| 19 | `DELETE` | `/users/{id}` | Hard delete (only if unreferenced) | `A` | `T2` | `User, AuditLog` | FULLY SUPPORTED |
| 20 | `GET` | `/destinations` | List (filter active, country, search) | `ALL` | `T1` | `Destination` | FULLY SUPPORTED |
| 21 | `POST` | `/destinations` | Create | `A` | `T1` | `Destination, AuditLog` | FULLY SUPPORTED |
| 22 | `GET` | `/destinations/{dest_id}` | Detail + rolling search metrics | `ALL` | `T1` | `Destination` | FULLY SUPPORTED |
| 23 | `PATCH` | `/destinations/{dest_id}` | Update metadata / ceiling | `A` | `T1` | `Destination, AuditLog` | FULLY SUPPORTED |
| 24 | `DELETE` | `/destinations/{dest_id}` | Soft-disable | `A` | `T2` | `Destination, AuditLog` | FULLY SUPPORTED |
| 25 | `GET` | `/destinations/{dest_id}/daily-metrics` | Time-series daily metrics | `ALL` | `T1` | `DestinationDailyMetrics` | FULLY SUPPORTED |
| 26 | `GET` | `/destinations/{dest_id}/search-velocity` | 7d / 30d rolling aggregates | `AN, PM, A` | `T2` | `DestinationDailyMetrics, CustomerSearchEvent` | FULLY SUPPORTED |
| 27 | `GET` | `/suppliers` | List (filter type, active) | `ALL` | `T1` | `Supplier` | FULLY SUPPORTED |
| 28 | `POST` | `/suppliers` | Create | `A` | `T1` | `Supplier, AuditLog` | FULLY SUPPORTED |
| 29 | `GET` | `/suppliers/{supplier_id}` | Detail | `ALL` | `T1` | `Supplier` | FULLY SUPPORTED |
| 30 | `PATCH` | `/suppliers/{supplier_id}` | Update caps, salvage | `A` | `T1` | `Supplier, AuditLog` | FULLY SUPPORTED |
| 31 | `DELETE` | `/suppliers/{supplier_id}` | Soft-disable | `A` | `T2` | `Supplier, AuditLog` | FULLY SUPPORTED |
| 32 | `GET` | `/suppliers/{supplier_id}/performance-snapshots` | Time-series KPIs | `AN, PM, A` | `T1` | `SupplierPerformanceSnapshot` | FULLY SUPPORTED |
| 33 | `GET` | `/suppliers/{supplier_id}/offers` | Supplier's active offers | `PM, AN, A` | `T1` | `SupplierOffer` | FULLY SUPPORTED |
| 34 | `GET` | `/suppliers/{supplier_id}/purchase-orders` | PO history | `PM, A` | `T1` | `PurchaseOrder` | FULLY SUPPORTED |
| 35 | `GET` | `/suppliers/{supplier_id}/contacts` | List contacts | `ALL` | `T1` | `SupplierContact` | FULLY SUPPORTED |
| 36 | `POST` | `/suppliers/{supplier_id}/contacts` | Add contact | `A` | `T1` | `SupplierContact, AuditLog` | FULLY SUPPORTED |
| 37 | `PATCH` | `/supplier-contacts/{id}` | Update | `A` | `T1` | `SupplierContact, AuditLog` | FULLY SUPPORTED |
| 38 | `DELETE` | `/supplier-contacts/{id}` | Delete | `A` | `T2` | `SupplierContact, AuditLog` | FULLY SUPPORTED |
| 39 | `POST` | `/supplier-contacts/{id}/set-primary` | Reassign primary flag | `A` | `T2` | `SupplierContact, AuditLog` | FULLY SUPPORTED |
| 40 | `GET` | `/inventory-items` | List (filter category, dest, active) | `ALL` | `T1` | `InventoryItem` | FULLY SUPPORTED |
| 41 | `POST` | `/inventory-items` | Create | `A` | `T2` | `InventoryItem, AuditLog` | FULLY SUPPORTED |
| 42 | `GET` | `/inventory-items/{inventory_id}` | Detail + latest snapshot | `ALL` | `T1` | `InventoryItem, InventorySnapshot` | FULLY SUPPORTED |
| 43 | `PATCH` | `/inventory-items/{inventory_id}` | Update reference, active | `A` | `T2` | `InventoryItem, AuditLog` | FULLY SUPPORTED |
| 44 | `GET` | `/inventory-items/{inventory_id}/snapshots` | Time-series snapshots | `AN, PM, A` | `T1` | `InventorySnapshot` | FULLY SUPPORTED |
| 45 | `GET` | `/inventory-items/{inventory_id}/offers` | All supplier offers | `PM, AN, A` | `T1` | `SupplierOffer` | FULLY SUPPORTED |
| 46 | `POST` | `/inventory-snapshots` | Ingest snapshot (worker) | `A` | `T2` | `InventorySnapshot` | FULLY SUPPORTED |
| 47 | `POST` | `/inventory-snapshots/bulk` | Bulk upsert (worker) | `A` | `T2` | `InventorySnapshot` | FULLY SUPPORTED |
| 48 | `GET` | `/supplier-offers` | List with rich filters | `ALL` | `T1` | `SupplierOffer` | FULLY SUPPORTED |
| 49 | `POST` | `/supplier-offers` | Create offer | `A` | `T1` | `SupplierOffer, AuditLog` | FULLY SUPPORTED |
| 50 | `GET` | `/supplier-offers/{offer_id}` | Detail + latest prediction + snapshot | `ALL` | `T1` | `SupplierOffer, OfferPrediction, InventorySnapshot` | FULLY SUPPORTED |
| 51 | `PATCH` | `/supplier-offers/{offer_id}` | Update terms / MOQ / capacity | `A` | `T1` | `SupplierOffer, AuditLog` | FULLY SUPPORTED |
| 52 | `POST` | `/supplier-offers/{offer_id}/expire` | Manual expire | `A, PM` | `T1` | `SupplierOffer, AuditLog` | FULLY SUPPORTED |
| 53 | `POST` | `/supplier-offers/bulk-import` | CSV upload -> async create/update | `A` | `T2` | `SupplierOffer, IngestionBatch, AuditLog` | FULLY SUPPORTED |
| 54 | `GET` | `/supplier-offers/{offer_id}/predictions` | Historical predictions | `AN, PM, A` | `T1` | `OfferPrediction` | FULLY SUPPORTED |
| 55 | `GET` | `/market-signals` | List (filter dest, dates, type) | `ALL` | `T1` | `MarketSignal` | FULLY SUPPORTED |
| 56 | `POST` | `/market-signals` | Create | `A` | `T1` | `MarketSignal, AuditLog` | FULLY SUPPORTED |
| 57 | `PATCH` | `/market-signals/{id}` | Update | `A` | `T2` | `MarketSignal, AuditLog` | FULLY SUPPORTED |
| 58 | `DELETE` | `/market-signals/{id}` | Delete | `A` | `T2` | `MarketSignal, AuditLog` | FULLY SUPPORTED |
| 59 | `GET` | `/exchange-rates` | List (filter pair, date) | `ALL` | `T1` | `ExchangeRate` | FULLY SUPPORTED |
| 60 | `POST` | `/exchange-rates` | Ingest (worker) | `A` | `T2` | `ExchangeRate` | FULLY SUPPORTED |
| 61 | `GET` | `/exchange-rates/latest` | Latest rate per pair | `ALL` | `T1` | `ExchangeRate` | FULLY SUPPORTED |
| 62 | `GET` | `/market-segment-baselines` | List baselines | `AN, PM, A` | `T1` | `MarketSegmentBaseline` | FULLY SUPPORTED |
| 63 | `PUT` | `/market-segment-baselines/{segment_name}` | Upsert (EDA job) | `A` | `T2` | `MarketSegmentBaseline, AuditLog` | FULLY SUPPORTED |
| 64 | `GET` | `/pipelines/batches` | List ingestion batches | `AN, A` | `T2` | `IngestionBatch` | FULLY SUPPORTED |
| 65 | `POST` | `/pipelines/batches` | Trigger ingestion (async) | `A` | `T2` | `IngestionBatch, AuditLog` | FULLY SUPPORTED |
| 66 | `GET` | `/pipelines/batches/{batch_uid}` | Batch detail + rollups | `AN, A` | `T2` | `IngestionBatch` | FULLY SUPPORTED |
| 67 | `GET` | `/pipelines/batches/{batch_uid}/quality-reports` | Per-check results | `AN, A` | `T2` | `DataQualityReport` | FULLY SUPPORTED |
| 68 | `POST` | `/pipelines/batches/{batch_uid}/retry` | Retry failed batch | `A` | `T2` | `IngestionBatch, AuditLog` | FULLY SUPPORTED |
| 69 | `GET` | `/pipelines/quality-summary` | Aggregated pass/fail by severity | `AN, A` | `T2` | `DataQualityReport` | FULLY SUPPORTED |
| 70 | `GET` | `/ml/feature-sets` | List feature Parquets | `AN, A` | `T2` | `FeatureSet` | FULLY SUPPORTED |
| 71 | `GET` | `/ml/feature-sets/{id}` | Detail + column list | `AN, A` | `T2` | `FeatureSet` | FULLY SUPPORTED |
| 72 | `POST` | `/ml/feature-sets` | Register (worker) | `A` | `T2` | `FeatureSet, AuditLog` | FULLY SUPPORTED |
| 73 | `GET` | `/ml/models` | List models (filter type, champion) | `AN, PM, A` | `T1` | `MLModel` | FULLY SUPPORTED |
| 74 | `GET` | `/ml/models/{id}` | Detail + metrics | `AN, PM, A` | `T1` | `MLModel` | FULLY SUPPORTED |
| 75 | `GET` | `/ml/models/champions` | The 5 active champions | `AN, PM, A` | `T1` | `MLModel` | FULLY SUPPORTED |
| 76 | `POST` | `/ml/models/{id}/promote` | Set is_champion=true | `A` | `T1` | `MLModel, AuditLog` | FULLY SUPPORTED |
| 77 | `POST` | `/ml/models/{id}/retire` | Set model_status=RETIRED | `A` | `T2` | `MLModel, AuditLog` | FULLY SUPPORTED |
| 78 | `GET` | `/ml/training-runs` | List training runs | `AN, A` | `T2` | `ModelTrainingRun` | FULLY SUPPORTED |
| 79 | `POST` | `/ml/training-runs` | Trigger training (async) | `A` | `T2` | `ModelTrainingRun, AuditLog` | FULLY SUPPORTED |
| 80 | `GET` | `/ml/training-runs/{id}` | Detail + metrics + importance | `AN, A` | `T2` | `ModelTrainingRun` | FULLY SUPPORTED |
| 81 | `POST` | `/ml/training-runs/{id}/cancel` | Cancel pending run | `A` | `T2` | `ModelTrainingRun, AuditLog` | FULLY SUPPORTED |
| 82 | `GET` | `/predictions/offers` | List OfferPrediction (filter as_of, run) | `PM, AN, A` | `T1` | `OfferPrediction` | FULLY SUPPORTED |
| 83 | `POST` | `/predictions/offers/generate` | Batch-generate predictions (async) | `A, PM` | `T1` | `OfferPrediction, MLModel, AuditLog` | FULLY SUPPORTED |
| 84 | `GET` | `/forecasts/demand` | List demand forecasts | `AN, PM, A` | `T1` | `DestinationDemandForecast` | FULLY SUPPORTED |
| 85 | `GET` | `/forecasts/inventory` | List inventory forecasts | `AN, PM, A` | `T1` | `DestinationInventoryForecast` | FULLY SUPPORTED |
| 86 | `GET` | `/forecasts/demand/{dest_id}/chart` | Chart-ready time-series | `AN, PM, A` | `T2` | `DestinationDemandForecast, DestinationDailyMetrics` | FULLY SUPPORTED |
| 87 | `POST` | `/forecasts/materialize` | Recompute forecasts (async) | `A` | `T2` | `DestinationDemandForecast, DestinationInventoryForecast, AuditLog` | FULLY SUPPORTED |
| 88 | `GET` | `/admin/platform-config` | Active profile | `A, PM, AN` | `T1` | `PlatformOptimizationConfig` | FULLY SUPPORTED |
| 89 | `GET` | `/admin/platform-config/history` | Versioned list | `A` | `T2` | `PlatformOptimizationConfig` | FULLY SUPPORTED |
| 90 | `POST` | `/admin/platform-config` | Create draft profile | `A` | `T1` | `PlatformOptimizationConfig, AuditLog` | FULLY SUPPORTED |
| 91 | `PATCH` | `/admin/platform-config/{id}` | Update draft | `A` | `T1` | `PlatformOptimizationConfig, AuditLog` | FULLY SUPPORTED |
| 92 | `POST` | `/admin/platform-config/{id}/activate` | Atomically activate | `A` | `T1` | `PlatformOptimizationConfig, AuditLog` | FULLY SUPPORTED |
| 93 | `GET` | `/admin/config-templates` | List templates | `A, PM` | `T1` | `OptimizationConfigTemplate` | FULLY SUPPORTED |
| 94 | `POST` | `/admin/config-templates` | Create template | `A` | `T1` | `OptimizationConfigTemplate, AuditLog` | FULLY SUPPORTED |
| 95 | `PATCH` | `/admin/config-templates/{id}` | Update template | `A` | `T1` | `OptimizationConfigTemplate, AuditLog` | FULLY SUPPORTED |
| 96 | `DELETE` | `/admin/config-templates/{id}` | Delete (unreferenced only) | `A` | `T2` | `OptimizationConfigTemplate, AuditLog` | FULLY SUPPORTED |
| 97 | `GET` | `/budgets` | List (filter scope, status, period) | `PM, A` | `T1` | `ProcurementBudget` | FULLY SUPPORTED |
| 98 | `POST` | `/budgets` | Create envelope | `A` | `T1` | `ProcurementBudget, BudgetLedgerEntry, AuditLog` | FULLY SUPPORTED |
| 99 | `GET` | `/budgets/{id}` | Detail + spent/reserved | `PM, A` | `T1` | `ProcurementBudget` | FULLY SUPPORTED |
| 100 | `PATCH` | `/budgets/{id}` | Update (DRAFT only) | `A` | `T1` | `ProcurementBudget, AuditLog` | FULLY SUPPORTED |
| 101 | `POST` | `/budgets/{id}/activate` | DRAFT -> ACTIVE | `A` | `T1` | `ProcurementBudget, AuditLog` | FULLY SUPPORTED |
| 102 | `POST` | `/budgets/{id}/close` | ACTIVE -> CLOSED | `A` | `T1` | `ProcurementBudget, AuditLog` | FULLY SUPPORTED |
| 103 | `POST` | `/budgets/{id}/adjust` | Manual adjustment (ledger entry) | `A` | `T1` | `ProcurementBudget, BudgetLedgerEntry, AuditLog` | FULLY SUPPORTED |
| 104 | `GET` | `/budgets/{id}/ledger` | Append-only ledger entries | `A, PM` | `T1` | `BudgetLedgerEntry` | FULLY SUPPORTED |
| 105 | `GET` | `/budgets/{id}/utilization` | Reserved vs spent vs available | `A, PM` | `T1` | `ProcurementBudget, BudgetLedgerEntry` | FULLY SUPPORTED |
| 106 | `POST` | `/optimization-runs` | Trigger run (async); honors Idempotency-Key | `PM, A` | `T1` | `OptimizationRun, ProcurementBudget, BudgetLedgerEntry, AuditLog` | FULLY SUPPORTED |
| 107 | `POST` | `/optimization-runs/compare` | Trigger 3-run comparison (hotel/flight/joint) | `PM, A` | `T1` | `OptimizationRun, AuditLog` | FULLY SUPPORTED |
| 108 | `GET` | `/optimization-runs` | List (filter mode, statuses, dates) | `PM, AN, A` | `T1` | `OptimizationRun` | FULLY SUPPORTED |
| 109 | `GET` | `/optimization-runs/{run_id}` | Full detail (config, solver, scorecard) | `PM, AN, A` | `T1` | `OptimizationRun` | FULLY SUPPORTED |
| 110 | `GET` | `/optimization-runs/{run_id}/status` | Lightweight polling (status + progress) | `PM, AN, A` | `T1` | `OptimizationRun` | FULLY SUPPORTED |
| 111 | `GET` | `/optimization-runs/{run_id}/stream` | SSE status + logs | `PM, AN, A` | `T1` | `OptimizationRun, OptimizationRunEvent` | FULLY SUPPORTED |
| 112 | `POST` | `/optimization-runs/{run_id}/cancel` | Cancel Celery task | `PM, A` | `T1` | `OptimizationRun, AuditLog` | FULLY SUPPORTED |
| 113 | `POST` | `/optimization-runs/{run_id}/retry` | Retry as child run | `PM, A` | `T1` | `OptimizationRun, AuditLog` | FULLY SUPPORTED |
| 114 | `POST` | `/optimization-runs/{run_id}/approve` | Plan-level approval | `PM, A` | `T1` | `OptimizationRun, AuditLog` | FULLY SUPPORTED |
| 115 | `POST` | `/optimization-runs/{run_id}/reject` | Plan-level rejection + notes | `PM, A` | `T1` | `OptimizationRun, AuditLog` | FULLY SUPPORTED |
| 116 | `GET` | `/optimization-runs/{run_id}/scorecard` | KPI-card financial + risk summary | `PM, AN, A` | `T1` | `OptimizationRun` | FULLY SUPPORTED |
| 117 | `GET` | `/optimization-runs/{run_id}/baselines` | 3-baseline comparison | `PM, AN, A` | `T1` | `OptimizationRun` | FULLY SUPPORTED |
| 118 | `GET` | `/optimization-runs/{run_id}/risk-metrics` | Expanded risk metrics | `PM, AN, A` | `T1` | `OptimizationRun` | FULLY SUPPORTED |
| 119 | `GET` | `/optimization-runs/{run_id}/constraints` | Binding/slack constraints | `AN, A` | `T1` | `OptimizationConstraint` | FULLY SUPPORTED |
| 120 | `GET` | `/optimization-runs/{run_id}/sensitivity` | Read sensitivity scenarios | `AN, PM, A` | `T1` | `SensitivityScenario` | FULLY SUPPORTED |
| 121 | `GET` | `/optimization-runs/{run_id}/artifacts` | List artifact files | `A, PM` | `T2` | `OptimizationRun, OptimizationRunArtifact` | FULLY SUPPORTED |
| 122 | `GET` | `/optimization-runs/{run_id}/artifacts/{filename}` | File download | `A, PM` | `T2` | `OptimizationRun, OptimizationRunArtifact` | FULLY SUPPORTED |
| 123 | `GET` | `/optimization-runs/compare/{comparison_group_id}` | Side-by-side 3-run comparison | `PM, AN, A` | `T1` | `OptimizationRun` | FULLY SUPPORTED |
| 176 | `POST` | `/optimization-runs/{run_id}/sensitivity` | Trigger async parametric sweep | `PM, AN, A` | `T1` | `OptimizationRun, SensitivityScenario, AuditLog` | FULLY SUPPORTED |
| 179 | `POST` | `/optimization-runs/{run_id}/purchase-orders/generate` | Bulk-generate POs by supplier from approved recs | `PM, A` | `T1` | `OptimizationRun, ProcurementRecommendation, PurchaseOrder, PurchaseOrderLine, BudgetLedgerEntry, AuditLog` | FULLY SUPPORTED |
| 124 | `GET` | `/optimization-runs/{run_id}/recommendations` | List per-run with filters | `PM, AN, A` | `T1` | `ProcurementRecommendation` | FULLY SUPPORTED |
| 125 | `GET` | `/recommendations/{id}` | Detail + prediction lineage | `PM, AN, A` | `T1` | `ProcurementRecommendation, OfferPrediction` | FULLY SUPPORTED |
| 126 | `POST` | `/recommendations/{id}/approve` | Per-row approve | `PM, A` | `T1` | `ProcurementRecommendation, AuditLog` | FULLY SUPPORTED |
| 127 | `POST` | `/recommendations/{id}/reject` | Per-row reject + notes | `PM, A` | `T1` | `ProcurementRecommendation, AuditLog` | FULLY SUPPORTED |
| 128 | `POST` | `/optimization-runs/{run_id}/recommendations/bulk-approve` | Bulk approve all/subset | `PM, A` | `T1` | `ProcurementRecommendation, AuditLog` | FULLY SUPPORTED |
| 129 | `POST` | `/optimization-runs/{run_id}/recommendations/bulk-reject` | Bulk reject + shared notes | `PM, A` | `T1` | `ProcurementRecommendation, AuditLog` | FULLY SUPPORTED |
| 130 | `GET` | `/optimization-runs/{run_id}/recommendations/export` | CSV download of plan | `PM, AN, A` | `T1` | `ProcurementRecommendation` | FULLY SUPPORTED |
| 131 | `GET` | `/optimization-runs/{run_id}/rejections` | List rejections | `PM, AN, A` | `T1` | `RejectedOpportunity` | FULLY SUPPORTED |
| 132 | `GET` | `/optimization-runs/{run_id}/rejections/summary` | Count by reason code | `PM, AN, A` | `T1` | `RejectedOpportunity` | FULLY SUPPORTED |
| 178 | `GET` | `/recommendations` | Cross-run decision history | `PM, AN, A` | `T1` | `ProcurementRecommendation` | FULLY SUPPORTED |
| 133 | `GET` | `/purchase-orders` | List (filter supplier, status, dates) | `PM, A` | `T1` | `PurchaseOrder` | FULLY SUPPORTED |
| 134 | `POST` | `/purchase-orders` | Create PO + lines + ledger COMMIT | `PM, A` | `T1` | `PurchaseOrder, PurchaseOrderLine, ProcurementBudget, BudgetLedgerEntry, AuditLog` | FULLY SUPPORTED |
| 135 | `GET` | `/purchase-orders/{po_number}` | Detail + lines + fulfillments | `PM, A` | `T1` | `PurchaseOrder, PurchaseOrderLine, PurchaseOrderFulfillment` | FULLY SUPPORTED |
| 136 | `POST` | `/purchase-orders/{po_number}/confirm` | SUBMITTED -> CONFIRMED | `PM, A` | `T1` | `PurchaseOrder, AuditLog` | FULLY SUPPORTED |
| 137 | `POST` | `/purchase-orders/{po_number}/cancel` | Cancel + release reservation | `PM, A` | `T1` | `PurchaseOrder, ProcurementBudget, BudgetLedgerEntry, AuditLog` | FULLY SUPPORTED |
| 138 | `GET` | `/purchase-orders/{po_number}/lines` | Lines with linked recommendations | `PM, A` | `T1` | `PurchaseOrderLine, ProcurementRecommendation` | FULLY SUPPORTED |
| 139 | `GET` | `/purchase-orders/{po_number}/export` | PDF/CSV for supplier | `PM, A` | `T2` | `PurchaseOrder, PurchaseOrderLine` | FULLY SUPPORTED |
| 140 | `GET` | `/purchase-orders/{po_number}/fulfillments` | All fulfillment records | `PM, A` | `T1` | `PurchaseOrderFulfillment` | FULLY SUPPORTED |
| 141 | `POST` | `/purchase-orders/{po_number}/lines/{line_id}/fulfillments` | Record delivery / spoilage / 4-outcome | `PM, A` | `T1` | `PurchaseOrderFulfillment, PurchaseOrderLine, AuditLog` | FULLY SUPPORTED |
| 142 | `PATCH` | `/purchase-order-fulfillments/{id}` | Update fulfillment status | `PM, A` | `T1` | `PurchaseOrderFulfillment, AuditLog` | FULLY SUPPORTED |
| 143 | `POST` | `/purchase-order-fulfillments/{id}/dispute` | Raise dispute | `PM, A` | `T2` | `PurchaseOrderFulfillment, AuditLog` | FULLY SUPPORTED |
| 144 | `GET` | `/reports` | List (filter type, status, run) | `PM, AN, A` | `T1` | `Report` | FULLY SUPPORTED |
| 145 | `POST` | `/reports` | Trigger generation (async) | `PM, AN, A` | `T1` | `Report, AuditLog` | FULLY SUPPORTED |
| 146 | `GET` | `/reports/{report_id}` | Detail + status | `PM, AN, A` | `T1` | `Report` | FULLY SUPPORTED |
| 147 | `GET` | `/reports/{report_id}/download` | Download artifact | `PM, AN, A` | `T1` | `Report` | FULLY SUPPORTED |
| 148 | `POST` | `/reports/{report_id}/regenerate` | Re-run generation | `PM, AN, A` | `T2` | `Report, AuditLog` | FULLY SUPPORTED |
| 149 | `DELETE` | `/reports/{report_id}` | Delete artifact + row | `A` | `T2` | `Report, AuditLog` | FULLY SUPPORTED |
| 150 | `GET` | `/report-schedules` | List schedules | `A` | `T2` | `ReportSchedule` | FULLY SUPPORTED |
| 151 | `POST` | `/report-schedules` | Create (cron) | `A` | `T2` | `ReportSchedule, AuditLog` | FULLY SUPPORTED |
| 152 | `PATCH` | `/report-schedules/{id}` | Update | `A` | `T2` | `ReportSchedule, AuditLog` | FULLY SUPPORTED |
| 153 | `POST` | `/report-schedules/{id}/enable` | Toggle enable | `A` | `T2` | `ReportSchedule, AuditLog` | FULLY SUPPORTED |
| 154 | `DELETE` | `/report-schedules/{id}` | Delete | `A` | `T2` | `ReportSchedule, AuditLog` | FULLY SUPPORTED |
| 155 | `GET` | `/notifications` | Own inbox (filter unread, type) | `ALL` | `T1` | `Notification` | FULLY SUPPORTED |
| 156 | `GET` | `/notifications/unread-count` | Badge count | `ALL` | `T1` | `Notification` | FULLY SUPPORTED |
| 157 | `POST` | `/notifications/{id}/read` | Mark single read | `ALL` | `T1` | `Notification` | FULLY SUPPORTED |
| 158 | `POST` | `/notifications/mark-all-read` | Mark all read | `ALL` | `T1` | `Notification` | FULLY SUPPORTED |
| 159 | `DELETE` | `/notifications/{id}` | Dismiss | `ALL` | `T2` | `Notification` | FULLY SUPPORTED |
| 160 | `GET` | `/notification-preferences` | Current user's prefs | `ALL` | `T1` | `NotificationPreference` | FULLY SUPPORTED |
| 161 | `PUT` | `/notification-preferences` | Bulk upsert | `ALL` | `T1` | `NotificationPreference` | FULLY SUPPORTED |
| 162 | `GET` | `/notifications/deliveries` | Delivery log | `A` | `T2` | `NotificationDelivery` | FULLY SUPPORTED |
| 163 | `GET` | `/search-events` | List (filter dest, category, dates) | `AN, PM, A` | `T2` | `CustomerSearchEvent` | FULLY SUPPORTED |
| 164 | `GET` | `/search-events/analytics/funnel` | Search -> click -> book funnel | `AN, PM, A` | `T2` | `CustomerSearchEvent` | FULLY SUPPORTED |
| 165 | `GET` | `/search-events/analytics/velocity` | Rolling velocity by destination | `AN, PM, A` | `T2` | `CustomerSearchEvent` | FULLY SUPPORTED |
| 180 | `POST` | `/search-events/bulk` | Bulk ingest (worker X-Worker-Token) | `A (worker)` | `T2` | `CustomerSearchEvent` | FULLY SUPPORTED |
| 172 | `GET` | `/analytics/dashboard` | Role-aware overview KPIs | `ALL` | `T1` | `ProcurementBudget, OptimizationRun, SupplierOffer, Notification` | FULLY SUPPORTED |
| 173 | `GET` | `/analytics/profitability` | Expected vs actual profit, ROI, spoilage, 4-outcome variance | `AN, PM, A` | `T1` | `PurchaseOrderFulfillment, OptimizationRun, ProcurementRecommendation` | FULLY SUPPORTED |
| 174 | `GET` | `/analytics/cancellation-and-pricing` | Cancellation by cohort/lead-time + price elasticity | `AN, PM, A` | `T1` | `CustomerSearchEvent, DestinationDailyMetrics, OfferPrediction` | FULLY SUPPORTED |
| 175 | `GET` | `/analytics/suppliers/scorecard` | Ranked supplier comparison | `AN, PM, A` | `T1` | `Supplier, SupplierPerformanceSnapshot, PurchaseOrderFulfillment` | FULLY SUPPORTED |
| 177 | `POST` | `/economics/simulate` | Stateless what-if calculator (hotel/flight economics) | `PM, AN, A` | `T1` | `Application-level / Stateless OR-Tools / economics models` | APPLICATION-LEVEL ONLY |
| 166 | `GET` | `/audit-logs` | List (filter user, action, entity, dates) | `A` | `T1` | `AuditLog` | FULLY SUPPORTED |
| 167 | `GET` | `/audit-logs/{id}` | Single record | `A` | `T1` | `AuditLog` | FULLY SUPPORTED |
| 168 | `GET` | `/health` | Liveness probe | `PUB` | `T1` | `Application-level` | APPLICATION-LEVEL ONLY |
| 169 | `GET` | `/health/ready` | Readiness (DB + Redis + solver) | `PUB` | `T1` | `Application-level + Database probe` | APPLICATION-LEVEL ONLY |
| 170 | `GET` | `/health/version` | Build info | `PUB` | `T1` | `Application-level` | APPLICATION-LEVEL ONLY |
| 171 | `GET` | `/health/champion-models` | Loaded champion models | `A` | `T2` | `MLModel + ML Registry` | FULLY SUPPORTED |

---

## 3. Schema Enhancements Implemented (Phase B)

1. **Primary Supplier Contact Enforcement**: Added partial unique index `uq_supplier_primary_contact` on `supplier_contacts(supplier_id)` where `is_primary = true`.
2. **Platform Optimization Config Versioning**: Added `version`, `status` (DRAFT, ACTIVE, ARCHIVED), `activated_at`, `activated_by_user_id` and unique constraint `(profile_name, version)`.
3. **Optimization Run Progress & Streaming**: Added `OptimizationRunEvent` table for persistent event logs and SSE live updates.
4. **Optimization Run Artifacts**: Added `OptimizationRunArtifact` table for tracking downloadable files (CSVs, solver logs, sensitivity plots).
5. **Budget Ledger Immutability & Safety**: Updated `budget_id` foreign key on `BudgetLedgerEntry` from CASCADE to RESTRICT, and added `idempotency_key`.
6. **Purchase Order Fulfillment Dispute Tracking**: Added `dispute_reason`, `dispute_status`, `disputed_at`, `disputed_by_user_id`, `dispute_resolved_at`, `dispute_resolution_notes`.
7. **Pipeline & Worker Execution Tracking**: Added `celery_task_id`, `retry_count`, `triggered_by_user_id` to `IngestionBatch`.
8. **ML Training & Report Execution**: Added `celery_task_id` to `ModelTrainingRun` and `Report`.
9. **Customer Search Event Enrichment**: Added `user_session_id` and `conversion_value_inr` to `CustomerSearchEvent` for funnel and price-elasticity analytics.