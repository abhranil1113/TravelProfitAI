# Phase 5 — Stage 2: Data Preparation & Point-in-Time Model Integration Report

**Project:** TBO InventoryIQ — AI-Powered Travel Inventory & Profit Optimization Platform  
**Team:** Team Sabuj Sangha (Abhranil Pal & Arka Dyuti Bose)  
**Timestamp:** 2026-06-01 (Point-in-Time Cutoff)  
**Status:** VALIDATED & COMPLETED  

---

## 1. Executive Summary

Stage 2 transforms raw supplier offers, inventory availability snapshots, and customer search event streams into normalized, point-in-time consistent procurement candidate opportunities. Every candidate offer is scored with risk-adjusted predictions from Phase 4 machine learning pipelines and evaluated against audited commercial economic formulas.

---

## 2. Ingestion & Point-in-Time Temporal Filtering

- **Total Ingested Raw Offers:** 5,000 (`data/processed/supplier_offers/cleaned_supplier_offers.parquet`)
- **Optimization Cutoff Date ($T_{\text{opt}}$):** `2026-06-01`
- **Expired Offers Filtered:** 1,743 offers had `offer_valid_until < 2026-06-01` and were strictly excluded.
- **Active Offers Retained:** 3,257 offers.
- **Temporal Integrity Rule:** Zero future-dated searches or inventory snapshots are visible to the candidate builder at $T_{\text{opt}}$, guaranteeing zero look-ahead data leakage.

---

## 3. Inventory Capacity Resolution

- **Physical Inventory Snapshots:** 460 unique physical inventory assets resolved.
- **Deduplication Logic:** For each `(inventory_id, travel_date)`, only the latest snapshot where `snapshot_date <= 2026-06-01` is selected. Repeated snapshots are never summed as phantom capacity.
- **Capacity Linking:** Effective available procurement quantity for offer $i$ is capped at $\min(Q_i^{\text{offer}}, Q_i^{\text{inventory}})$.

---

## 4. Machine Learning Model Integration & Risk Scoring

### 4.1 Hotel Cancellation Predictor (`hotel_cancellation`)
- **Model Pipeline:** LightGBM classifier with preprocessing pipeline (`data/models/hotel_cancellation/`).
- **Input Featurization:** Synthesizes representative booking cohorts (2 adults, 2-night stay, Transient, Online TA channel) based on travel date and lead time.
- **ADR Prototype Currency Scale Correction:**
  - Training dataset median ADR: €94.95 (historical European hotel dataset).
  - Raw offer selling prices: ~₹4,500/night (INR). Passing raw INR directly would cause a **91.25-sigma blowout**.
  - Audited prototype scaling: $\text{ADR}_{\text{EUR}} = \frac{p_i / 2.0}{90.0} \approx 25.0 \text{ EUR}$.
  - Calibration: Bayesian shrinkage applied against destination baseline prior ($\lambda = 0.70$).
  - Mean predicted cancellation probability: **18.4%**.

### 4.2 Flight Price Elasticity & Market Ceiling (`flight_price_prediction`)
- **Model Pipeline:** Gradient boosted regression pipeline predicting consumer market clearing prices.
- **Sell-Through Adjustment:**
  $$\theta_{\text{adj}} = \theta_0 \cdot \left(\frac{p_{\text{market}}}{p_{\text{contract}}}\right)^\eta \quad (\text{if } p_{\text{contract}} > p_{\text{market}})$$
  where $\eta = 1.5$ (price elasticity) and $\theta_0 = 0.85$ (baseline sell-through).

### 4.3 Market Demand Ceilings (`demand_features`)
- **Historical Search Volume:** Aggregated per `(destination_id, inventory_type)` strictly prior to $T_{\text{opt}}$.
- **Absorption Cap:** Destination demand ceilings prevent over-purchasing inventory beyond the market's historical conversion capacity.

---

## 5. Candidate Opportunity Output

- **Total Active Candidates Formulated:** 3,257
  - Hotel Room-Night Candidates: 1,600
  - Flight Seat Candidates: 1,657
- **Viable Positive-Contribution Candidates:** 934
- **Negative-Contribution Candidates:** 2,323 (correctly tagged for rejection)
