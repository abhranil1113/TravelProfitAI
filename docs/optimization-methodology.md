# Optimization Methodology & Mathematical Formulations

## 1. Problem Formulation
The procurement problem is formulated as a single-stage, multi-product Mixed Integer Linear Program (MILP).

### Decision Variables
For each candidate opportunity $k \in \mathcal{K}$:
- $q_k \in \mathbb{Z}_{\ge 0}$: Integer physical units procured (room-nights for hotels, seats for flights).
- $y_k \in \{0, 1\}$: Binary activation decision variable.

### Objective Function
Maximize expected net contribution across the entire procurement portfolio:
$$\max \sum_{i \in \mathcal{H}} e_i^H q_i^H + \sum_{j \in \mathcal{F}} e_j^F q_j^F$$

---

## 2. Audited Economic Contribution Equations

### 2.1 Hotel 4-Outcome Scenario Economics
The hotel outcome space is partitioned into four mutually exclusive states whose probabilities sum strictly to 1.0:
- **State 1 (Unsold):** Probability $1 - \theta$. Inflow: $r_{\text{supp}, u} c$.
- **State 2 (Completed):** Probability $\theta(1 - p_c)$. Inflow: $p$.
- **State 3a (Cancelled & Resold):** Probability $\theta p_c f$. Inflow: $(1 - r_{\text{cust}})p + \delta p$.
- **State 3b (Cancelled & Unresold):** Probability $\theta p_c (1 - f)$. Inflow: $(1 - r_{\text{cust}})p + r_{\text{supp}, c} c$.

Net Expected Contribution per room-night:
$$e_i^H = \theta(1-p_c)p + \theta p_c(1-r_c)p + \theta p_cf\delta p + \left[(1-\theta)r_{\text{supp},u} + \theta p_c(1-f)r_{\text{supp},c}\right]c - c$$

### 2.2 Flight Spoilage & Salvage Economics
Net Expected Contribution per flight seat:
$$e_j^F = \theta_j p_j + (1-\theta_j) s_j c_j - c_j - (1-\theta_j)\psi_j$$

Where:
- $\theta_j$: Market sell-through probability (adjusted for consumer price elasticity).
- $s_j$: Contractual salvage rate ($0.0$ for baseline strict spoilage, $0.10$ for optional contractual salvage).
- $\psi_j$: Penalty for unsold seats ($0.0$ baseline).
- **Break-Even Sell-Through Probability:**
  $$\theta^* = \frac{c_j(1 - s_j) + \psi_j}{p_j - s_j c_j + \psi_j}$$

---

## 3. Mathematical Constraints
1. **Master Shared Budget:** $\sum_{k \in \mathcal{K}} c_k q_k \le B_{\text{total}}$
2. **Category Bounds:** $B_H^{\min} \le \text{Spend}_H \le B_H^{\max}$ and $B_F^{\min} \le \text{Spend}_F \le B_F^{\max}$
3. **Linking Constraints (MOQ & Capacity):** $Q_k^{\min} y_k \le q_k \le Q_k^{\max} y_k \quad \forall k \in \mathcal{K}$
4. **Segregated Destination Demand Ceilings:** $\sum_{i \in \mathcal{H}_d} q_i^H \le D_{\text{hotel}, d}$ and $\sum_{j \in \mathcal{F}_d} q_j^F \le D_{\text{flight}, d}$
5. **Supplier Concentration Limit:** $\sum_{k \in \mathcal{S}_s} c_k q_k \le \gamma_{\sup} B_{\text{total}}$
6. **Destination Concentration Limit:** $\sum_{k \in \mathcal{D}_d} c_k q_k \le \gamma_{\text{dest}} B_{\text{total}}$

---

## 4. Solver Technology & Benchmarks
Implemented using **Google OR-Tools (`ortools.linear_solver.pywraplp`)** with **SCIP 9.15.6755**.
- Tested across problem slices: 10, 50, 100, 500, 1000, and full 3,257 active candidate pool.
- Full pool (6,514 variables, 6,553 constraints) solves to proven global optimality (`OPTIMAL`, 0.00% gap) in **1.92 seconds**.
