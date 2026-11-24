# Project Overview — TBO InventoryIQ

## 1. Executive Summary
TBO InventoryIQ is an enterprise AI decision support and mathematical profit optimization platform designed for travel wholesalers, consolidators, and Online Travel Agencies (OTAs). 

In traditional travel procurement, businesses make procurement commitments using simple historical averages or unadjusted gross margin markups $(p - c)/c$. This approach regularly results in severe financial losses because it ignores:
1. Customer booking cancellations and refund liabilities.
2. Unsold flight seat spoilage (perishable zero-salvage inventory).
3. Real-time market demand ceilings and price elasticity.
4. Supplier concentration risks and Minimum Order Quantity (MOQ) boundaries.

TBO InventoryIQ solves this by combining machine learning risk forecasting with Google OR-Tools Mixed Integer Linear Programming (MILP) to formulate procurement decisions that maximize expected net contribution while guaranteeing that capital, capacity, demand, and risk constraints are never violated.

---

## 2. Platform Objectives & Core Questions Answered
The platform answers 7 core commercial questions for travel procurement managers:
1. **What inventory should be purchased?** (Specific hotel room-nights and flight seats).
2. **How much inventory should be purchased?** (Exact integer quantities satisfying MOQs and capacity bounds).
3. **Which supplier should be selected?** (Selecting optimal offers across competing suppliers).
4. **How should the procurement budget be distributed?** (Optimal allocation across destinations and product categories).
5. **What is the expected net profit?** (Expected profit calculated using audited outcome-based economics).
6. **What is the financial risk?** (Portfolio exposure limits per supplier and destination).
7. **Why was each decision made?** (Evidence-backed explanations for selected and rejected offers).

---

## 3. Five-Phase Implementation Roadmap
- **Phase 1: Data Ingestion & Quality:** Cleaned 5.8M flights, 119k hotel bookings, 300k prices, searches, and inventory.
- **Phase 2: Exploratory Data Analysis:** Comprehensive statistical profiling, KPI calculations, and 8 analytical notebooks.
- **Phase 3: Production Feature Store:** Leak-free temporal splits, cohort features, demand velocity, and supplier metrics.
- **Phase 4: Machine Learning Pipelines:** 5 cross-validated champion models (LightGBM cancellation classifier, price regressor, demand forecaster, inventory depletion, supplier lead time).
- **Phase 5: MILP Optimization & Recommendation Engine:** OR-Tools SCIP solver, audited 4-outcome hotel economics, flight spoilage/salvage economics, +41.04% profit lift over heuristics, and automated recommendation/rejection generation.
