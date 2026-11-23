# Phase 5 — Stage 4: Optimization Evaluation, Baselines & Sensitivity Report

**Project:** TBO InventoryIQ — AI-Powered Travel Inventory & Profit Optimization Platform  
**Team:** Team Sabuj Sangha (Abhranil Pal & Arka Dyuti Bose)  
**Run ID:** `PROD_VERIFY_RUN`  
**Budget Level:** ₹250,000.00  
**Status:** VALIDATED & COMPLETED  

---

## 1. Commercial & Operational Scorecard

| Metric | Result | Commercial Interpretation |
|---|---|---|
| **Total Procurement Budget** | ₹250,000.00 | Authorized capital allocation |
| **Total Spend** | ₹249,194.16 | Total cost committed to selected inventory |
| **Budget Utilization %** | **99.68%** | Highly efficient capital deployment |
| **Remaining Budget** | ₹805.84 | Residual unallocated cash |
| **Expected Net Contribution (Profit)** | **+₹27,984.68** | Expected net profit after cancellations and spoilage |
| **Return on Spend (RoS)** | **11.23%** | Net return per rupee of procurement capital |
| **Hotel Category Spend** | ₹203,459.68 (81.65%) | Room-nights allocated |
| **Flight Category Spend** | ₹45,734.48 (18.35%) | Seat inventory allocated |
| **Units Procured (Hotels)** | 90 Room-Nights | Physical hotel room-nights |
| **Units Procured (Flights)** | 11 Seats | Physical flight seats |
| **Selected Opportunities Count** | 6 offers | Diversified portfolio allocations |
| **Max Supplier Concentration %** | **19.82%** | Complies strictly with 20.0% risk cap |
| **Max Destination Exposure %** | **23.11%** | Complies strictly with 25.0% risk cap |

---

## 2. Comparative Benchmark Analysis

The MILP optimizer was benchmarked against standard procurement heuristics on the identical candidate offer pool:

| Strategy | Total Spend (INR) | Expected Net Profit (INR) | Return on Spend | Units Procured | Selected Offers | Profit Lift vs Margin |
|---|---|---|---|---|---|---|
| **No Procurement** | ₹0.00 | ₹0.00 | 0.00% | 0 | 0 | — |
| **Greedy Gross Margin** | ₹248,820.00 | ₹19,842.10 | 7.97% | 88 | 7 | Baseline (0.0%) |
| **Greedy Expected Contribution** | ₹249,050.00 | ₹24,115.30 | 9.68% | 94 | 6 | +21.54% |
| **MILP Optimal (OR-Tools)** | **₹249,194.16** | **₹27,984.68** | **11.23%** | **101** | **6** | **+41.04%** |

### Key Benchmark Insights
1. **Gross Margin Failure:** Simple gross margin ranking $((p - c)/c)$ selects items with seemingly high markups but high cancellation or unsold risk, leading to suboptimal actual cash yield.
2. **Mathematical Lift:** The MILP mathematical engine delivers a **+41.04% profit lift** over the standard commercial gross margin heuristic and a **+16.05% lift** over risk-adjusted greedy knapsack ranking by simultaneously resolving interacting MOQ, capacity, destination demand, and supplier concentration constraints.

---

## 3. Parametric Sensitivity Analysis

### 3.1 Budget Scaling
| Budget Level | Spend (INR) | Utilization % | Expected Net Profit (INR) | Return on Spend | Hotel Units | Flight Units |
|---|---|---|---|---|---|---|
| **₹50,000** | ₹48,912.00 | 97.82% | ₹6,412.50 | 13.11% | 20 | 0 |
| **₹100,000** | ₹99,230.00 | 99.23% | ₹12,840.10 | 12.94% | 40 | 0 |
| **₹250,000** | ₹249,194.16 | 99.68% | ₹27,984.68 | 11.23% | 90 | 11 |
| **₹500,000** | ₹499,727.44 | 99.95% | ₹57,636.92 | 11.53% | 185 | 32 |
| **₹1,000,000** | ₹998,450.00 | 99.85% | ₹112,410.80 | 11.26% | 370 | 65 |

### 3.2 Flight Salvage Sensitivity
- **0% Baseline Spoilage:** Flight expected contribution at $\theta=0.85, c=4200, p=5500$ is **+₹475.00**; break-even sell-through $\theta^* = \mathbf{76.36\%}$.
- **10% Contractual Salvage:** Flight expected contribution at $\theta=0.85, c=4200, p=5500$ is **+₹538.00**; break-even sell-through $\theta^* = \mathbf{74.41\%}$.
