# TBO InventoryIQ — Phase 5 Stage 1.3: Final Numerical Consistency & Unit Validation Report

**Project:** TBO InventoryIQ – AI-Powered Travel Inventory & Profit Optimization Platform  
**Team:** Team Sabuj Sangha (*Abhranil Pal & Arka Dyuti Bose*)  
**Role:** Senior Operations Research Engineer, Mathematical Auditor & ML Engineer  
**Audit Date:** November 23, 2026  
**Document Path:** `reports/optimization/phase5_stage1_3_validation_report.md`  

---

## 1. Executive Summary & Audit Scorecard

In accordance with Phase 5 Stage 1.3 requirements, this audit resolves all remaining numerical discrepancies, unit mismatches, currency validation semantics, and reproducibility requirements across the optimization architecture.

```
+------------------------------------------------------------------------------------------------------------------+
|                                    STAGE 1.3 AUDIT RESOLUTION SCORECARD                                         |
+---+-----------------------------+--------------------------------------------------------------------------------+
| # | Audit Item                  | Empirical Audit Finding & Applied Resolution                                   |
+---+-----------------------------+--------------------------------------------------------------------------------+
| 1 | Flight Salvage Consistency  | Resolved discrepancy between 10% sensitivity and 0% register default. Reconciled|
|   |                             | baseline ($s=0.00, \theta^*=76.36\%$) and scenario ($s=0.10, \theta^*=74.41\%$).|
| 2 | Hotel ADR Unit Mismatch     | Detected 91-sigma blowout when passing raw INR (~₹4,485) into EUR model.       |
|   |                             | Implemented prototype scaling (90 INR/EUR -> ~49.8 EUR). Added unit guard.     |
| 3 | Currency Semantics          | Formalized 3-tier model (Verified, Prototype Assumed, Mixed/Prohibited).       |
|   |                             | Mandatory prototype override flag enforced; mixed currencies strictly blocked. |
| 4 | TC-06 Reproducibility       | Hand-calculated and asserted all 4 state probabilities, inflows, and exact     |
|   |                             | negative contribution: $e_i^H = -₹363.20$.                                     |
| 5 | Demand Conversion Units     | Verified search-to-booking conversions strictly prior to $T_{\text{opt}}$.     |
|   |                             | Implemented zero-denominator protection; documented repeated search limits.    |
| 6 | Automated Test Suite        | Implemented 6 new automated tests in `tests/optimization/`. 166 of 166 tests   |
|   |                             | passing across the repository (100% pass rate).                                |
+---+-----------------------------+--------------------------------------------------------------------------------+
```

---

## 2. Flight Economics: Numerical Consistency & Break-Even Analysis

### A. Resolution of the Salvage Rate Discrepancy
In the Stage 1.2 report, the numerical example used an optional contractual salvage recovery rate of $s_j = 0.10$, whereas the assumptions register declared the baseline default as $s_j = 0.00$. 

To eliminate confusion, both branches are now fully specified, mathematically reconciled, and verified by automated unit tests:

#### 1. Baseline Default Branch ($s_j = 0.00$, Strict Perishability / Spoilage)
- Wholesale Purchase Cost: $c_j = ₹4,200$
- Contractual Selling Price: $p_j = ₹5,500$
- Unsold Penalty: $\psi_j = ₹0$
- Salvage Recovery: $s_j = 0.00$

**Formula:**
$$e_j^F = \theta_j \cdot p_j - c_j$$

**Break-Even Derivation:**
$$e_j^F = 0 \implies \theta^* \cdot 5500 - 4200 = 0 \implies \theta^* = \frac{4200}{5500} = \frac{42}{55} \approx \mathbf{0.763636 \quad (76.36\%)}$$

**Sensitivity Scenarios:**
- $\theta = 0.50$: $e_j^F = (0.50 \times 5500) - 4200 = 2750 - 4200 = \mathbf{-₹1,450.00}$ (Margin: -34.52%)
- $\theta = 0.85$: $e_j^F = (0.85 \times 5500) - 4200 = 4675 - 4200 = \mathbf{+₹475.00}$ (Margin: +11.31%)
- $\theta = 0.95$: $e_j^F = (0.95 \times 5500) - 4200 = 5225 - 4200 = \mathbf{+₹1,025.00}$ (Margin: +24.40%)

---

#### 2. Optional Contractual Salvage Branch ($s_j = 0.10$, 10% Partial Airline Recovery)
- Wholesale Purchase Cost: $c_j = ₹4,200$
- Contractual Selling Price: $p_j = ₹5,500$
- Unsold Penalty: $\psi_j = ₹0$
- Salvage Recovery: $s_j = 0.10$ ($s_j \cdot c_j = ₹420$)

**Formula:**
$$e_j^F = \theta_j \cdot p_j + (1 - \theta_j) \cdot s_j \cdot c_j - c_j$$
$$e_j^F = \theta_j (p_j - s_j c_j) - c_j (1 - s_j) = \theta_j (5500 - 420) - 4200(0.90) = 5080 \cdot \theta_j - 3780$$

**Break-Even Derivation:**
$$e_j^F = 0 \implies \theta^* = \frac{3780}{5080} = \frac{189}{254} \approx \mathbf{0.744094 \quad (74.41\%)}$$

**Sensitivity Scenarios:**
- $\theta = 0.50$: $e_j^F = (5080 \times 0.50) - 3780 = 2540 - 3780 = \mathbf{-₹1,240.00}$ (Margin: -29.52%)
- $\theta = 0.85$: $e_j^F = (5080 \times 0.85) - 3780 = 4318 - 3780 = \mathbf{+₹538.00}$ (Margin: +12.81%)
- $\theta = 0.95$: $e_j^F = (5080 \times 0.95) - 3780 = 4826 - 3780 = \mathbf{+₹1,046.00}$ (Margin: +24.90%)

---

## 3. Hotel ADR Currency & Unit Mismatch Audit

### A. Empirical Verification of Training vs. Offer Units
We executed an empirical distribution comparison between training data and offer data:
- **Training Dataset (`cleaned_hotel_bookings.parquet`):**
  - Currency: **EUR**
  - Count: 119,208 records
  - Min: 0.0 EUR, Median: **94.95 EUR**, Mean: **101.93 EUR**, Std: **48.04 EUR**, Max: **510.0 EUR**
- **Supplier Offers (`cleaned_supplier_offers.parquet`):**
  - Currency: **INR**
  - Count: 2,750 hotel offers
  - Median selling price: ₹8,971.68 INR
  - If divided by assumed 2-night stay: $\text{Unscaled ADR} = \mathbf{₹4,485.84}$

### B. The 91-Sigma Anomaly Proof
Passing unscaled ₹4,485.84 directly into the model results in:
$$Z = \frac{4485.84 - 101.93}{48.04} = \mathbf{+91.25 \text{ standard deviations}}$$
This catastrophic blowout invalidates the StandardScaler and forces decision trees into extreme edge branches.

### C. Prototype Scaling Solution
In prototype mode, the input is scaled using an explicit exchange rate parameter:
$$\text{ADR}_{\text{EUR}} = \frac{p_i / \bar{N}}{R_{\text{EUR}\to\text{INR}}}, \quad R_{\text{EUR}\to\text{INR}} = 90.0 \text{ INR/EUR}$$
$$\text{ADR}_{\text{EUR}} = \frac{8971.68 / 2}{90.0} = \mathbf{49.84 \text{ EUR}}$$
This places the input in the 25th–50th percentile of the training distribution (range: 0 to 510 EUR).
*Automated Guard: `test_hotel_adr_currency_mismatch_detection()` asserts that passing unscaled INR ADR raises an explicit `ValueError`, while scaled prototype ADR passes within [10.0, 500.0] EUR.*

---

## 4. Currency Validation Semantics

The optimizer enforces three strict currency classifications:

```
                                [ Input Offers / Datasets ]
                                             |
                         +-------------------+-------------------+
                         |                                       |
               Mixed Currencies?                            Single Currency
              (e.g., ['INR', 'EUR'])                             |
                         |                         +-------------+-------------+
                         v                         |                           |
             [ REJECTED IMMEDIATELY ]         Verified Currency?      Unverified Prototype?
             (CurrencyMismatchError)          (e.g., 'EUR' in ERP)          (e.g., 'INR')
                                                   |                           |
                                                   v                           v
                                        [ VERIFIED_COMMERCIAL ]      allow_prototype_override?
                                        (Permitted for Prod)                   |
                                                                   +-----------+-----------+
                                                                   |                       |
                                                                 True                    False
                                                                   |                       |
                                                                   v                       v
                                                         [ PROTOTYPE_ASSUMED ]   [ REJECTED: PROD GUARD ]
                                                         (Logged in Audit)       (UnverifiedCurrencyError)
```

- **Production Mode:** `allow_prototype_currency_override = False` (default). Rejects unverified synthetic prototype INR data.
- **Prototype Mode:** Requires explicit `allow_prototype_currency_override = True` in `OptimizationConfig`. Records `currency_mode = "PROTOTYPE_ASSUMED"` and `currency_disclaimer = "Unverified synthetic prototype currencies"` in the audit metadata.

---

## 5. TC-06 Step-by-Step Numerical Verification

**Instance Definition:** High cancellation probability ($p^{\text{cancel}} = 0.60$) with zero supplier refund ($r^{\text{supp, cancel}} = 0.0$).

- **Input Parameters:**
  - Wholesale purchase cost: $c_i = ₹5,000$
  - Retail selling price: $p_i = ₹7,000$
  - Sell-through probability: $\theta_i = 0.90$
  - Cancellation probability: $p_i^{\text{cancel}} = 0.60$
  - Customer refund rate: $r_i^{\text{cust}} = 0.80$ (Retained fee: $1 - 0.80 = 0.20 \implies ₹1,400$)
  - Resale probability: $f_i^{\text{resale}} = 0.40$
  - Resale price realization: $\delta_i^{\text{resale}} = 0.90 \implies p_i^{\text{resale}} = ₹6,300$
  - Supplier refund (unsold): $r_i^{\text{supp, unsold}} = 0.0$
  - Supplier refund (cancelled): $r_i^{\text{supp, cancel}} = 0.0$ (Zero recovery)

### Step 1: Discrete Outcome Probabilities
- $P(S_1) = 1 - 0.90 = \mathbf{0.100}$
- $P(S_2) = 0.90 \times (1 - 0.60) = 0.90 \times 0.40 = \mathbf{0.360}$
- $P(S_{3a}) = 0.90 \times 0.60 \times 0.40 = \mathbf{0.216}$
- $P(S_{3b}) = 0.90 \times 0.60 \times (1 - 0.40) = 0.90 \times 0.60 \times 0.60 = \mathbf{0.324}$
- **Sum of Probabilities:** $0.100 + 0.360 + 0.216 + 0.324 = \mathbf{1.000}$ $\checkmark$

### Step 2: State Cash Inflows
- $S_1$ (Unsold): Inflow = ₹0.00
- $S_2$ (Completed): Inflow = $+p = \mathbf{₹7,000.00}$
- $S_{3a}$ (Cancelled & Resold): Retained fee + Resale = $(0.20 \times 7000) + (0.90 \times 7000) = 1400 + 6300 = \mathbf{₹7,700.00}$
- $S_{3b}$ (Cancelled & Unresold): Retained fee + Supplier refund = $(0.20 \times 7000) + (0.00 \times 5000) = 1400 + 0 = \mathbf{₹1,400.00}$

### Step 3: Expected Gross Cash Inflow
$$\mathbb{E}[\text{Inflow}] = (0.100 \times 0) + (0.360 \times 7000) + (0.216 \times 7700) + (0.324 \times 1400)$$
$$\mathbb{E}[\text{Inflow}] = 0 + 2520.00 + 1663.20 + 453.60 = \mathbf{₹4,636.80}$$

### Step 4: Expected Net Contribution
$$e_i^H = \mathbb{E}[\text{Inflow}] - c_i = ₹4,636.80 - ₹5,000.00 = \mathbf{-₹363.20}$$
*Conclusion:* The expected net contribution is strictly negative ($-₹363.20$). Procuring any quantity $q_i > 0$ reduces objective value. The solver sets $y_i = 0, q_i = 0$. Fully verified in `test_tc06_reproducible_calculation()`.

---

## 6. Demand Conversion: Units, Historical Windows & Limitations

### A. Temporal Filtering & Denominator Protection
Conversion rates are evaluated strictly before optimization timestamp $T_{\text{opt}}$:
$$\kappa_d(T_{\text{opt}}) = \frac{\sum_{t < T_{\text{opt}}} \text{booking\_completed}_k}{\max\left(1, \; \sum_{t < T_{\text{opt}}} \text{searches}_k\right)}$$
- If a destination has zero search history before $T_{\text{opt}}$, the denominator guard forces $\kappa = 0.0$ and $D = 0$ safely without `ZeroDivisionError`. Verified in `test_demand_conversion_zero_denominator_and_temporal_cutoff()`.

### B. Unit Conversions & Missing Duration
- **Flight Seat Demand:** $D_{\text{FLIGHT}}(d, \tau) = \lfloor \hat{S}_{d, \tau} \cdot \kappa_d^F \cdot \mu_d^F \rfloor$ (units: `SEAT`).
- **Hotel Room-Night Demand:** $D_{\text{HOTEL}}(d, \tau) = \lfloor \hat{S}_{d, \tau} \cdot \kappa_d^H \cdot \bar{R}_d \cdot \bar{N} \rfloor$ (units: `ROOM_NIGHT`).
- **Limitation:** Stay duration $\bar{N}$ is **`UNAVAILABLE`** in search events and is fixed at $\bar{N} = 2.0$ nights.
- **Repeated Search Bias:** Synthetic search events include repeat queries from identical `user_id`s without session cookies. This means $\kappa_d$ represents *query-to-booking* conversion (~20%), not *unique-visitor* conversion.

---

## 7. Automated Test Suite Execution Results

Automated unit tests were implemented in [tests/optimization/test_stage1_validation.py](file:///c:/Users/AbhranilPal/Programs/Projects/TBO-InventoryIQ/tests/optimization/test_stage1_validation.py):

```
tests/optimization/test_stage1_validation.py::test_flight_economics_zero_salvage PASSED
tests/optimization/test_stage1_validation.py::test_flight_economics_ten_percent_salvage PASSED
tests/optimization/test_stage1_validation.py::test_tc06_reproducible_calculation PASSED
tests/optimization/test_stage1_validation.py::test_hotel_adr_currency_mismatch_detection PASSED
tests/optimization/test_stage1_validation.py::test_currency_validation_semantics PASSED
tests/optimization/test_stage1_validation.py::test_demand_conversion_zero_denominator_and_temporal_cutoff PASSED
```

### Full Repository Regression Run
```
============================== test session starts ==============================
collected 166 items

tests/data_validation/          27 passed
tests/eda/                      41 passed
tests/feature_engineering/      33 passed
tests/modeling/                 59 passed
tests/optimization/              6 passed
---------------------------------------------------------------------------------
============================== 166 passed in 58.07s =============================
```
**166 of 166 tests passed with 100% success.**

---

## 8. Summary of Changed Files

| File Path | Nature of Update |
| :--- | :--- |
| `tests/optimization/__init__.py` | Created test package marker for optimization suite. |
| `tests/optimization/test_stage1_validation.py` | Created 6 automated mathematical and unit validation tests. |
| `reports/optimization/optimization_assumptions.md` | Updated assumptions register with currency semantics, dual salvage rates, and ADR scale findings. |
| `reports/optimization/phase5_stage1_design.md` | Updated MILP design with hand-calculated proofs, ADR scaling formulas, and break-even tables. |
| `reports/optimization/phase5_stage1_3_validation_report.md` | Authored comprehensive Stage 1.3 audit report. |

---

## 9. Final Readiness Assessment

- **Mathematical Consistency:** **VERIFIED & CONSISTENT.** All discrepancies between assumptions and sensitivity tables are reconciled.
- **Unit & Currency Integrity:** **VERIFIED & GUARDED.** EUR/INR ADR scale guards and prototype override flags prevent silent domain errors.
- **Test Integrity:** **166 of 166 passing tests.**
- **Status:** **CONDITIONALLY READY FOR PROTOTYPE IMPLEMENTATION** under the explicit prototype scenario flag.

No optimization solver implementation has been started. **Awaiting your formal review and approval to proceed to Stage 2.**
