# TBO InventoryIQ — Phase 5 Stage 1.3 Final Mathematical Optimization Design

**Project:** TBO InventoryIQ – AI-Powered Travel Inventory & Profit Optimization Platform  
**Team:** Team Sabuj Sangha (*Abhranil Pal & Arka Dyuti Bose*)  
**Role:** Senior Operations Research Engineer, Data Scientist & Mathematical Auditor  
**Audit Date:** November 23, 2026  
**Document Path:** `reports/optimization/phase5_stage1_design.md`  
**Status:** **Stage 1.3 Audited & Mathematically Consistent — Awaiting Final Approval**  

---

## 1. Executive Summary & Stage 1.3 Consistency Resolutions

This design incorporates the complete mathematical audit and consistency checks established in Stage 1.3:

1. **Flight Economics Discrepancy Resolved:** Reconciled the flight salvage rate between the assumptions register and sensitivity tables. Evaluated the baseline model under **$s_j = 0.00$ (0% salvage, strict spoilage)** with break-even sell-through $\theta^* = \mathbf{76.36\%}$, and side-by-side presented the optional contractual scenario with **$s_j = 0.10$ (10% salvage)** with break-even $\theta^* = \mathbf{74.41\%}$. Automated unit tests verify both mathematical branches.
2. **Hotel ADR Currency Unit Mismatch Resolved:** Discovered that passing raw INR selling price divided by stay duration (~₹4,485) into the European-trained hotel model produces a **91.25 standard-deviation unit blowout** relative to training EUR ADR (mean: 101.93 EUR, max: 510 EUR). Implemented prototype-only scaling: $\text{ADR}_{\text{EUR}} = (p_i / \bar{N}) / 90.0$ (~49.8 EUR), and documented this as a **`PROTOTYPE_ASSUMED`** scenario.
3. **Currency Validation Semantics:** Defined strict three-tier semantics (`VERIFIED_COMMERCIAL`, `PROTOTYPE_ASSUMED`, `MIXED_OR_UNKNOWN`). The optimizer strictly rejects mixed currencies and requires an explicit `allow_prototype_currency_override=True` flag to proceed with prototype INR data.
4. **Reproducible TC-06 Calculation:** Documented every single intermediate probability, inflow, and cash term. Formally verified that expected net contribution is $\mathbf{-₹363.20}$, mathematically guaranteeing rejection.
5. **Demand Conversion Unit Integrity:** Enforced strictly historical calculations before $T_{\text{opt}}$, protected against zero denominators ($\max(1, \text{searches})$), and explicitly documented that stay duration is **`UNAVAILABLE`** in search events and is an assumed multiplier ($\bar{N} = 2.0$ nights).

---

## 2. Hotel Cancellation Economics (Outcome-Based Scenario Model)

### A. Discrete Outcome State Space ($\Omega_H$)
For each procured room-night $i \in \mathcal{H}$ with wholesale cost $c_i$ and selling price $p_i$, upfront expenditure is $-c_i$. The outcome space is strictly partitioned into four mutually exclusive, collectively exhaustive states:

```
                                  [ Procured Room-Night (-c_i) ]
                                                 |
                       +-------------------------+-------------------------+
                       |                                                   |
              State 1: Unsold                                      State: Booked
          P(S_1) = 1 - theta_i                                  P(Booked) = theta_i
           Inflow: r^supp,unsold * c_i                                     |
                                                 +-------------------------+-------------------------+
                                                 |                                                   |
                                       State 2: Completed                                   State 3: Cancelled
                                    P(S_2) = theta_i * (1 - p^cancel)                     P = theta_i * p^cancel
                                         Inflow: p_i                                                 |
                                                                           +-------------------------+-------------------------+
                                                                           |                                                   |
                                                                State 3a: Cancelled & Resold              State 3b: Cancelled & Unresold
                                                                   P = theta_i * p^cancel * f^resale         P = theta_i * p^cancel * (1 - f^resale)
                                                               Inflow: (1-r^cust)*p_i + delta*p_i        Inflow: (1-r^cust)*p_i + r^supp,cancel * c_i
```

1. **State 1: Unsold ($S_1$)** — Room is never booked by any customer.
   - $P(S_1) = 1 - \theta_i$ (where $\theta_i \in [0, 1]$ is the sell-through probability).
   - Inflow: $r_i^{\text{supp, unsold}} \cdot c_i$ (default = 0 for firm wholesale allotments).
   - Net Cash Flow: $R(S_1) = r_i^{\text{supp, unsold}} \cdot c_i - c_i$.
2. **State 2: Completed Stay ($S_2$)** — Guest stays; booking fulfilled.
   - $P(S_2) = \theta_i \cdot (1 - p_i^{\text{cancel}})$.
   - Inflow: $+p_i$ (full contractual selling price).
   - Net Cash Flow: $R(S_2) = p_i - c_i$.
3. **State 3a: Cancelled & Resold ($S_{3a}$)** — Customer cancels; room is re-marketed to a new guest.
   - $P(S_{3a}) = \theta_i \cdot p_i^{\text{cancel}} \cdot f_i^{\text{resale}}$ (where $f_i^{\text{resale}} \in [0, 1]$ is resale probability).
   - Inflow: Retained fee $\phi_i^{\text{fee}} = (1 - r_i^{\text{cust}}) \cdot p_i$ plus resale revenue $p_i^{\text{resale}} = \delta_i^{\text{resale}} \cdot p_i$.
   - Net Cash Flow: $R(S_{3a}) = (1 - r_i^{\text{cust}}) \cdot p_i + \delta_i^{\text{resale}} \cdot p_i - c_i$.
4. **State 3b: Cancelled & Unresold ($S_{3b}$)** — Customer cancels; room remains unoccupied.
   - $P(S_{3b}) = \theta_i \cdot p_i^{\text{cancel}} \cdot (1 - f_i^{\text{resale}})$.
   - Inflow: Retained fee $\phi_i^{\text{fee}} = (1 - r_i^{\text{cust}}) \cdot p_i$ plus supplier refund recovery $r_i^{\text{supp, cancel}} \cdot c_i$.
   - Net Cash Flow: $R(S_{3b}) = (1 - r_i^{\text{cust}}) \cdot p_i + r_i^{\text{supp, cancel}} \cdot c_i - c_i$.

### B. Expected Net Contribution Formulation ($e_i^H$)
$$\begin{aligned}
e_i^H = &\underbrace{\theta_i (1 - p_i^{\text{cancel}}) p_i}_{\text{Expected Fulfilled Revenue}} 
       + \underbrace{\theta_i p_i^{\text{cancel}} (1 - r_i^{\text{cust}}) p_i}_{\text{Expected Retained Cancellation Fees}} 
       + \underbrace{\theta_i p_i^{\text{cancel}} f_i^{\text{resale}} \delta_i^{\text{resale}} p_i}_{\text{Expected Resale Revenue}} \\
       &+ \underbrace{\left[ (1 - \theta_i) r_i^{\text{supp, unsold}} + \theta_i p_i^{\text{cancel}} (1 - f_i^{\text{resale}}) r_i^{\text{supp, cancel}} \right] c_i}_{\text{Expected Supplier Refund Recovery}} 
       - c_i
\end{aligned}$$

---

## 3. Hotel Model Integration & ADR Currency Scaling

### A. The 91-Sigma ADR Scale Anomaly
- **Training Data:** Persisted LightGBM model was trained on `cleaned_hotel_bookings.parquet` where ADR is denominated in **EUR** (mean: 101.93 EUR, median: 94.95 EUR, max: 510.0 EUR).
- **Offer Data:** In `cleaned_supplier_offers.parquet`, median hotel selling price is ₹8,971.68 INR. Dividing by an assumed 2-night stay gives an unscaled ADR of **₹4,485.84**.
- **The Defect:** Passing ₹4,485.84 directly into the model inputs produces a **Z-score of +91.25 standard deviations above the mean**, severely breaking the StandardScaler and tree thresholds!

### B. Prototype Conversion Scaling
To maintain numerical validity during prototype experimentation:
$$\text{ADR}_{\text{EUR}} = \frac{p_i / \bar{N}}{R_{\text{EUR}\to\text{INR}}}, \quad R_{\text{EUR}\to\text{INR}} = 90.0 \text{ INR/EUR}$$
$$\text{ADR}_{\text{EUR}} = \frac{8971.68 / 2}{90.0} = \mathbf{49.84 \text{ EUR}}$$
This places the input squarely in the 25th–50th percentile of the training distribution (valid range: 0 to 510 EUR).
*Production Rule: This scaling is an explicit prototype assumption. The optimizer strictly rejects raw unscaled INR when production currency enforcement is active.*

### C. Bayesian Shrinkage Sensitivity
To dampen domain-transfer bias from Portuguese vacation hotels:
$$p_i^{\text{cancel}} = \lambda \cdot \hat{p}_{\text{model}} + (1 - \lambda) \cdot \bar{p}_{\text{dest}}^{\text{prior}}, \quad \lambda = 0.70$$

---

## 4. Corrected Flight Economics (Reconciled Salvage & Break-Even Analysis)

### A. Objective Formulation
For each procured flight seat $j \in \mathcal{F}$ with cost $c_j$, contractual selling price $p_j$, sell-through $\theta_j$, salvage rate $s_j$, and penalty $\psi_j$:
$$e_j^F = \theta_j \cdot p_j + (1 - \theta_j) \cdot s_j \cdot c_j - c_j - (1 - \theta_j) \cdot \psi_j$$
*(Notice: Procurement cost $c_j$ is deducted exactly once; zero double-counting).*

### B. Break-Even Formula
Setting $e_j^F = 0$ yields the exact break-even sell-through probability $\theta^*$:
$$\theta^* \cdot \left( p_j - s_j c_j + \psi_j \right) = c_j - s_j c_j + \psi_j \implies \theta^* = \frac{c_j (1 - s_j) + \psi_j}{p_j - s_j c_j + \psi_j}$$

### C. Reconciled Baseline vs. Optional Salvage Scenarios
*(Test Instance: $c_j = ₹4,200$, $p_j = ₹5,500$, $\psi_j = 0$)*

#### Branch 1: Baseline Default ($s_j = 0.00$, Strict Spoilage)
- Break-Even Sell-Through:
  $$\theta^* = \frac{4200 (1 - 0)}{5500 - 0} = \frac{4200}{5500} = \frac{42}{55} \approx \mathbf{0.763636 \quad (76.36\%)}$$
- Sensitivity Scenarios:
  - $\theta = 0.50$: $e_j^F = (0.50 \times 5500) - 4200 = 2750 - 4200 = \mathbf{-₹1,450.00}$ (Margin: -34.52%).
  - $\theta = 0.85$: $e_j^F = (0.85 \times 5500) - 4200 = 4675 - 4200 = \mathbf{+₹475.00}$ (Margin: +11.31%).
  - $\theta = 0.95$: $e_j^F = (0.95 \times 5500) - 4200 = 5225 - 4200 = \mathbf{+₹1,025.00}$ (Margin: +24.40%).

#### Branch 2: Optional Salvage Scenario ($s_j = 0.10$, 10% Airline Recovery)
- Break-Even Sell-Through:
  $$\theta^* = \frac{4200 (1 - 0.10)}{5500 - (0.10 \times 4200)} = \frac{3780}{5080} \approx \mathbf{0.744094 \quad (74.41\%)}$$
- Sensitivity Scenarios:
  - $\theta = 0.50$: $e_j^F = (0.50 \times 5500) + (0.50 \times 420) - 4200 = 2750 + 210 - 4200 = \mathbf{-₹1,240.00}$.
  - $\theta = 0.85$: $e_j^F = (0.85 \times 5500) + (0.15 \times 420) - 4200 = 4675 + 63 - 4200 = \mathbf{+₹538.00}$.
  - $\theta = 0.95$: $e_j^F = (0.95 \times 5500) + (0.05 \times 420) - 4200 = 5225 + 21 - 4200 = \mathbf{+₹1,046.00}$.

*Conclusion:* Both branches are now documented, mathematically reconciled, and verified by automated unit tests in `tests/optimization/test_stage1_validation.py`.

---

## 5. Demand Conversion Integrity & Aggregate Bounds

### A. Strict Historical Funnel Calculation
To eliminate temporal leakage, conversion rates at optimization timestamp $T_{\text{opt}}$ are calculated using strictly prior records:
$$\kappa_d^H(T_{\text{opt}}) = \frac{\sum_{t < T_{\text{opt}}} \text{booking\_completed}_k}{\max\left(1, \; \sum_{t < T_{\text{opt}}} \text{searches}_k\right)}, \quad \kappa_d^F(T_{\text{opt}}) = \frac{\sum_{t < T_{\text{opt}}} \text{booking\_completed}_k}{\max\left(1, \; \sum_{t < T_{\text{opt}}} \text{searches}_k\right)}$$
The denominator guard $\max(1, \cdot)$ prevents `ZeroDivisionError` when a destination has zero prior search history.

### B. Aggregate Demand Ceilings (No Artificial Floors)
- Flight Demand (Seats): $D_{\text{FLIGHT}}(d, \tau) = \lfloor \hat{S}_{d, \tau} \cdot \kappa_d^F \cdot \mu_d^F \rfloor$.
- Hotel Demand (Room-Nights): $D_{\text{HOTEL}}(d, \tau) = \lfloor \hat{S}_{d, \tau} \cdot \kappa_d^H \cdot \bar{R}_d \cdot \bar{N} \rfloor$.
- **Constraints:**
  $$\sum_{i \in \text{Offers}(d, \text{HOTEL}, \tau)} q_i^H \le D_{\text{HOTEL}}(d, \tau), \quad \sum_{j \in \text{Offers}(d, \text{FLIGHT}, \tau)} q_j^F \le D_{\text{FLIGHT}}(d, \tau)$$
  *If $D < \text{MOQ}_i$, the solver naturally sets $y_i = 0, q_i = 0$.*

---

## 6. Joint MILP Formulation & Currency Semantics

### Decision Variables
- $q_i^H \in \mathbb{Z}_{\ge 0}, y_i^H \in \{0, 1\}$ (Hotel room-nights).
- $q_j^F \in \mathbb{Z}_{\ge 0}, y_j^F \in \{0, 1\}$ (Flight seats).

### Objective Function
$$\text{Maximize } \mathcal{Z} = \sum_{i \in \mathcal{H}} e_i^H \cdot q_i^H + \sum_{j \in \mathcal{F}} e_j^F \cdot q_j^F$$

### Constraints
1. **Shared Commercial Budget Guard:**
   $$\sum_{i \in \mathcal{H}} c_i^H \cdot q_i^H + \sum_{j \in \mathcal{F}} c_j^F \cdot q_j^F \le B_{\text{total}}$$
   *(Enforced only when all offer currencies are validated as identical or normalized).*
2. **Category Budget Limits (Configurable):**
   $$\underline{B}_H \le \sum_{i \in \mathcal{H}} c_i^H q_i^H \le \bar{B}_H, \quad \underline{B}_F \le \sum_{j \in \mathcal{F}} c_j^F q_j^F \le \bar{B}_F$$
3. **Supplier Allotment Capacity:**
   $$q_i^H \le u_i^H \cdot y_i^H, \quad q_j^F \le u_j^F \cdot y_j^F$$
4. **Minimum Order Quantity (MOQ):**
   $$q_i^H \ge m_i^H \cdot y_i^H, \quad q_j^F \ge m_j^F \cdot y_j^F$$
5. **Aggregate Destination Demand Caps:**
   $$\sum_{i \in \text{Offers}(d, \text{HOTEL}, \tau)} q_i^H \le D_{\text{HOTEL}}(d, \tau), \quad \sum_{j \in \text{Offers}(d, \text{FLIGHT}, \tau)} q_j^F \le D_{\text{FLIGHT}}(d, \tau)$$
6. **Destination Exposure Caps:**
   $$\sum_{i \in \mathcal{H}_d} c_i^H q_i^H + \sum_{j \in \mathcal{F}_d} c_j^F q_j^F \le L_d^{\text{dest}} \cdot B_{\text{total}}$$
7. **Supplier Concentration Caps (Disjoint Namespaces):**
   $$\sum_{i \in \mathcal{H}_s} c_i^H q_i^H \le L_s^{\text{supp}} \cdot B_{\text{total}}, \quad \forall s \in \mathcal{S}_H$$
   $$\sum_{j \in \mathcal{F}_s} c_j^F q_j^F \le L_s^{\text{supp}} \cdot B_{\text{total}}, \quad \forall s \in \mathcal{S}_F$$
8. **Integrity:**
   $$q_i^H, q_j^F \in \mathbb{Z}_{\ge 0}, \quad y_i^H, y_j^F \in \{0, 1\}$$

---

## 7. Completely Specified TC-06 Step-by-Step Numerical Proof

**Objective:** Prove mathematically that an offer with high cancellation and zero supplier refund yields negative expected contribution and is rejected.

- **Parameters:** $c = ₹5,000$, $p = ₹7,000$, $\theta = 0.90$, $p^{\text{cancel}} = 0.60$, $r^{\text{cust}} = 0.80$ (20% retained fee), $f^{\text{resale}} = 0.40$, $\delta = 0.90$, $r^{\text{supp, unsold}} = 0.0$, $r^{\text{supp, cancel}} = 0.0$ (Zero supplier refund).
- **Step 1: State Probabilities:**
  - $P(S_1) = 1 - 0.90 = \mathbf{0.100}$
  - $P(S_2) = 0.90 \times (1 - 0.60) = \mathbf{0.360}$
  - $P(S_{3a}) = 0.90 \times 0.60 \times 0.40 = \mathbf{0.216}$
  - $P(S_{3b}) = 0.90 \times 0.60 \times (1 - 0.40) = \mathbf{0.324}$
  - Sum of probabilities: $0.100 + 0.360 + 0.216 + 0.324 = \mathbf{1.000}$ $\checkmark$
- **Step 2: State Inflows:**
  - Inflow($S_1$) = ₹0.00
  - Inflow($S_2$) = ₹7,000.00
  - Inflow($S_{3a}$) = $(0.20 \times 7000) + (0.90 \times 7000) = 1400 + 6300 = \mathbf{₹7,700.00}$
  - Inflow($S_{3b}$) = $(0.20 \times 7000) + (0.00 \times 5000) = 1400 + 0 = \mathbf{₹1,400.00}$
- **Step 3: Expected Gross Inflow:**
  $$\mathbb{E}[\text{Inflow}] = (0.100 \times 0) + (0.360 \times 7000) + (0.216 \times 7700) + (0.324 \times 1400)$$
  $$\mathbb{E}[\text{Inflow}] = 0 + 2520.00 + 1663.20 + 453.60 = \mathbf{₹4,636.80}$$
- **Step 4: Expected Net Contribution:**
  $$e_i^H = \mathbb{E}[\text{Inflow}] - c_i = ₹4,636.80 - ₹5,000.00 = \mathbf{-₹363.20}$$
- **Conclusion:** Because $e_i^H = -₹363.20 < 0$, any $q_i > 0$ reduces total profit. The solver sets $y_i = 0, q_i = 0$. Verified and asserted in `test_tc06_reproducible_calculation()`.

---

## 8. Test Suite Verification Summary (166 Passing Tests)

Automated tests in `tests/optimization/test_stage1_validation.py` verify all core mathematical assertions:
1. `test_flight_economics_zero_salvage`: Verifies $s=0.00$, $\theta^* = 76.36\%$, and contributions at $\theta \in \{0.50, 0.85, 0.95\}$ (-₹1450, +₹475, +₹1025).
2. `test_flight_economics_ten_percent_salvage`: Verifies $s=0.10$, $\theta^* = 74.41\%$, and contributions at $\theta \in \{0.50, 0.85, 0.95\}$ (-₹1240, +₹538, +₹1046).
3. `test_tc06_reproducible_calculation`: Verifies all intermediate steps and exact $e_i^H = -₹363.20$.
4. `test_hotel_adr_currency_mismatch_detection`: Verifies rejection of unscaled INR ADR and validation of prototype scaled ADR.
5. `test_currency_validation_semantics`: Verifies rejection of mixed currencies and enforcement of prototype override flag.
6. `test_demand_conversion_zero_denominator_and_temporal_cutoff`: Verifies zero-denominator protection and strict historical filtering.

**Overall Test Suite Status:** **166 of 166 tests passing** (Phases 1–4: 160 tests; Stage 1 Validation: 6 tests).
