# TBO InventoryIQ — Optimization Assumptions & Data Provenance Register (Stage 1.3 Final Audit)

**Project:** TBO InventoryIQ – AI-Powered Travel Inventory & Profit Optimization Platform  
**Team:** Team Sabuj Sangha (*Abhranil Pal & Arka Dyuti Bose*)  
**Role:** Senior Operations Research Engineer, Data Scientist & Mathematical Auditor  
**Audit Date:** November 23, 2026  
**Document Path:** `reports/optimization/optimization_assumptions.md`  

---

## 1. Provenance Classification Framework

Every input, feature, constraint coefficient, and financial parameter utilized in the Phase 5 Mixed-Integer Linear Programming (MILP) optimization engine is strictly classified into one of five mutually exclusive provenance categories:

1. **`[OBSERVED]`**: Directly extracted from cleaned source datasets (`cleaned_supplier_offers.parquet`, `cleaned_inventory_availability.parquet`, `cleaned_customer_search_events.parquet`).
2. **`[MODEL_PREDICTED]`**: Inferred by serialized Phase 4 champion models loaded from `data/models/`.
3. **`[DERIVED]`**: Mathematically calculated from observed historical relationships without exogenous commercial assumptions.
4. **`[MANUALLY_ASSUMED]`**: Unobserved business policy parameters or risk tolerances. Must remain fully configurable in `OptimizationConfig` and never hardcoded.
5. **`[UNAVAILABLE]`**: Variables, relationships, or features that **do not exist** in the existing datasets and cannot be empirically measured without future data ingestion.

---

## 2. Currency Validation Semantics

To prevent accidental contamination across different monetary standards, the optimization engine enforces three distinct currency tiers:

1. **`VERIFIED_COMMERCIAL`**: Corporate currencies verified against real TBO production ERP/bank settlements. (None exists in the current prototype).
2. **`PROTOTYPE_ASSUMED`**: Unverified prototype denominations (e.g. synthetic INR offers, and synthetic EUR-to-INR prototype conversion). **Requires explicit `allow_prototype_currency_override = True` in `OptimizationConfig`. If disabled (production mode default), the optimizer aborts with `UnverifiedCurrencyError`.**
3. **`MIXED_OR_UNKNOWN`**: Prohibited. The optimizer strictly rejects datasets containing multiple currencies or missing currency declarations (`CurrencyMismatchError`).

---

## 3. Complete Data Provenance & Parameter Register

### A. Procurement Opportunity Inputs (Offer Level)

| Field / Parameter Name | Provenance Type | Source Dataset / Entity | Units | Description & Empirical Verification Status |
| :--- | :---: | :--- | :---: | :--- |
| `offer_id` | **`[OBSERVED]`** | `cleaned_supplier_offers.parquet` | String ID | Unique primary key for wholesale supplier offer (5,000 records). |
| `supplier_id` | **`[OBSERVED]`** | `cleaned_supplier_offers.parquet` | String ID | Supplier identifier. Verified disjoint: 12 Hotel (`SUP001`–`SUP012`) and 8 Flight (`SUP013`–`SUP020`). |
| `inventory_type` | **`[OBSERVED]`** | `cleaned_supplier_offers.parquet` | Category | `HOTEL` (2,750) or `FLIGHT` (2,250). Strictly segregated in optimization. |
| `inventory_id` | **`[OBSERVED]`** | `cleaned_supplier_offers.parquet` | String ID | Unique asset identifier (157 distinct items). Verified 1-to-1 with `supplier_id`. |
| `origin_id` | **`[OBSERVED]`** | `cleaned_supplier_offers.parquet` | String ID | Origin airport for flights; None for hotels. |
| `destination_id` | **`[OBSERVED]`** | `cleaned_supplier_offers.parquet` | String ID | Destination hub identifier (10 distinct destinations). |
| `travel_date` | **`[OBSERVED]`** | `cleaned_supplier_offers.parquet` | Date | Service date of inventory (`2026-01-01` to `2027-05-15`). |
| `purchase_cost` ($c_i$) | **`[OBSERVED]`** | `cleaned_supplier_offers.parquet` | Currency / Unit | Unit wholesale purchase cost payable to supplier. Range: ₹1,978 to ₹34,046. |
| `selling_price` ($p_i$) | **`[OBSERVED]`** | `cleaned_supplier_offers.parquet` | Currency / Unit | Base contractual retail price suggested in offer. Range: ₹2,380 to ₹46,375. |
| `available_quantity` ($u_i$) | **`[OBSERVED]`** | `cleaned_supplier_offers.parquet` | Integer Units | Maximum allotment available under this specific offer (10 to 212 units). |
| `minimum_purchase_qty` ($m_i$) | **`[OBSERVED]`** | `cleaned_supplier_offers.parquet` | Integer Units | Minimum contractual order quantity (MOQ: 5 to 25 units). |
| `refundable` | **`[OBSERVED]`** | `cleaned_supplier_offers.parquet` | Boolean | True if supplier offer allows cancellation/refund (2,086 True, 2,914 False). |
| `offer_valid_until` | **`[OBSERVED]`** | `cleaned_supplier_offers.parquet` | Timestamp | Expiration timestamp. Offers where `offer_valid_until < T_opt` are filtered. |
| `currency` | **`[PROTOTYPE_ASSUMED]`** | `cleaned_supplier_offers.parquet` | ISO Code | Denominated as `INR` across all 5,000 synthetic records, but **unverified against real TBO production financials**. Requires prototype override flag. |

---

### B. Machine Learning Model Predictions & Unit Transformations

| Model Task | Provenance Type | Model Artifact & Algorithm | Input Feature Requirements | Currency & Unit Audit Reality |
| :--- | :---: | :--- | :--- | :--- |
| **Hotel Cancellation Model** ($\hat{p}_i^{\text{cancel}}$) | **`[MODEL_PREDICTED]` (Experimental)** | `hotel_cancellation` (Tuned LightGBM) | **47 booking-level features** | **Trained on EUR ADR (median: 94.95 EUR, max: 510 EUR).** Passing raw INR prices (~₹4,500/night) produces a 91 standard-deviation unit blowout! Scaled via prototype exchange rate: $\text{ADR}_{\text{EUR}} = (p_i / \bar{N}) / 90.0$ (~49.8 EUR). Classified as **`EXPERIMENTAL`**. |
| **Flight Price Model** ($p_j^{\text{ML}}$) | **`[MODEL_PREDICTED]`** | `flight_price` (Tuned LightGBM) | **17 flight features** | Predicts consumer market price ceiling ($R^2=0.97$). **Never used as supplier acquisition cost.** |
| **Demand Forecasting Model** ($\hat{S}_{d, \tau}$) | **`[MODEL_PREDICTED]`** | `demand_forecasting` (Naive Persistence) | **15 panel features** | Predicts 7-day future search volume. Observed 67.08% zero rate. |
| **Inventory Depletion Model** ($\hat{A}_{i, \tau}$) | **`[MODEL_PREDICTED]`** | `inventory_forecasting` (LightGBM) | **25 features** | Predicts future available quantity for replenishment urgency. |

---

### C. Derived Commercial & Funnel Parameters

| Parameter Name | Provenance Type | Derivation Formula | Range | Business Meaning & Limitations |
| :--- | :---: | :--- | :---: | :--- |
| **Lead Time Days** ($L_i$) | **`[DERIVED]`** | $L_i = \max(0, \; (\text{travel\_date}_i - T_{\text{opt}}).\text{days})$ | 0 to 180 | Days remaining until service date. |
| **Flight Search Conversion** ($\kappa_d^F$) | **`[DERIVED]`** | $\kappa_d^F = \frac{\sum_{t < T_{\text{opt}}} \text{booking\_completed}}{\max(1, \sum_{t < T_{\text{opt}}} \text{searches})}$ | ~20.4% | Flight conversion rate before $T_{\text{opt}}$. Protected against zero denominators. Excludes repeated query bias. |
| **Hotel Search Conversion** ($\kappa_d^H$) | **`[DERIVED]`** | $\kappa_d^H = \frac{\sum_{t < T_{\text{opt}}} \text{booking\_completed}}{\max(1, \sum_{t < T_{\text{opt}}} \text{searches})}$ | ~20.1% | Hotel conversion rate before $T_{\text{opt}}$. Protected against zero denominators. Excludes repeated query bias. |
| **Flight Party Size** ($\mu_d^F$) | **`[DERIVED]`** | Mean `travellers_count` before $T_{\text{opt}}$ | 1.8 to 2.4 | Average seats booked per completed flight reservation. |
| **Hotel Room Count** ($\bar{R}_d$) | **`[DERIVED]`** | Mean `rooms_count` before $T_{\text{opt}}$ | 1.1 to 1.3 | Average rooms requested per completed hotel reservation. |
| **Hotel Stay Duration** ($\bar{N}$) | **`[UNAVAILABLE]`** | N/A | Nights | **Stay duration is NOT observed in search events.** Treated as assumed multiplier ($\bar{N} = 2.0$ nights). |
| **Aggregate Demand** ($D(d, \tau)$) | **`[DERIVED]`** | $\lfloor \hat{S}_{d, \tau} \cdot \kappa_d \cdot \mu_d \rfloor$ | 0 to 120 units | Market demand bound at destination. **No artificial supplier shares, no artificial MOQ floors.** |

---

## 4. Register of Manually Assumed Parameters (Audited Values & Sensitivities)

| Parameter Name | Symbol | Default Value | Unit | Sensitivity Range | Baseline Economic Effect | Prototype Status | Real Business Validation Required? |
| :--- | :---: | :---: | :---: | :---: | :--- | :---: | :---: |
| **Flight Salvage Rate (Default)** | $s_j$ | **0.00** | Ratio | 0.00 to 0.25 | **Baseline assumes strict spoilage (0% recovery).** Break-even sell-through = $\mathbf{76.36\%}$. | Safe (Conservative) | **Yes** (Airline charter agreements) |
| **Flight Salvage Rate (Optional)** | $s_j^{\text{opt}}$ | **0.10** | Ratio | 0.00 to 0.25 | Optional partial recovery scenario. Break-even sell-through = $\mathbf{74.41\%}$. | Safe (Scenario) | **Yes** (Airline cancellation terms) |
| **Base Flight Sell-Through** | $\theta_F^0$ | 0.85 | Probability | 0.50 to 0.95 | Baseline probability of selling seat at market price. | Scenario-based | **Yes** (Historical block-space sales) |
| **Flight Price Elasticity** | $\eta$ | 1.5 | Dimensionless | 0.5 to 3.0 | Penalizes sell-through if supplier price exceeds ML ceiling. | Scenario-based | **Yes** (Econometric pricing studies) |
| **Hotel Stay Duration** | $\bar{N}$ | 2.0 | Nights | 1.0 to 4.0 | Multiplier converting room bookings to room-nights. | Assumed Default | **Yes** (Hotel PMS booking data) |
| **Prototype EUR/INR Rate** | $R_{\text{EUR}\to\text{INR}}$ | 90.0 | INR / EUR | 85.0 to 95.0 | Scales INR selling price to EUR ADR for ML model compatibility. | Prototype Only | **Yes** (Treasury FX spot rates) |
| **Customer Refund Rate** | $r^{\text{cust}}$ | 0.80 | Ratio | 0.00 to 1.00 | Fraction of selling price refunded on flexible customer cancellation. | Policy Choice | **Yes** (TBO consumer terms) |
| **Supplier Refund Recovery** | $r^{\text{supp, cancel}}$ | 0.85 | Ratio | 0.50 to 1.00 | Cost recovered from supplier when `refundable=True`. | Policy Choice | **Yes** (Wholesale MSAs) |
| **Room Resale Probability** | $f^{\text{resale}}$ | 0.40 | Probability | 0.10 to 0.70 | Probability a cancelled room is re-marketed before check-in. | Scenario-based | **Yes** (Last-minute engine logs) |
| **Resale Price Discount** | $\delta$ | 0.90 | Ratio | 0.70 to 1.00 | Price realization on resold rooms ($p^{\text{resale}} = \delta \cdot p$). | Scenario-based | **Yes** (Yield management rules) |
| **Destination Exposure Cap** | $L_d^{\text{dest}}$ | 0.25 | Ratio | 0.10 to 0.50 | Maximum budget fraction per destination hub. | Risk Policy | **Yes** (Treasury Risk Committee) |
| **Supplier Concentration Cap** | $L_s^{\text{supp}}$ | 0.20 | Ratio | 0.05 to 0.40 | Maximum budget fraction per supplier counterparty. | Risk Policy | **Yes** (Counterparty Risk Limits) |
| **Bayesian Shrinkage Weight** | $\lambda$ | 0.70 | Weight | 0.00 to 1.00 | Balances European ML model against destination prior. | Experimental | **Yes** (Model Risk Validation) |
