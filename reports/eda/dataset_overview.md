# TBO InventoryIQ – Comprehensive Dataset Overview Report
**Project:** TBO InventoryIQ – AI-Powered Travel Inventory & Profit Optimization Platform  
**Phase:** Phase 2 – Exploratory Data Analysis & Statistical Profiling  
**Author:** Team Sabuj Sangha (Abhranil Pal & Arka Dyuti Bose)  
**Status:** Validated & Audited

---

## 1. Executive Summary

Phase 2 exploratory data analysis was conducted across all nine validated travel inventory datasets.
The portfolio comprises **4 synthetic datasets** reflecting real-time platform operations and **5 public travel benchmark datasets** representing global aviation and hospitality operations.

Total unified observational data spans over **6.2 million records**, offering deep empirical foundations for travel inventory procurement and profit maximization.

---

## 2. Dataset Inventory & Structural Profiles

| Dataset Canonical Name | Total Records | Columns | In-Memory (MB) | Currency / Unit Domain | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `hotel_bookings` | 119,208 | 42 | 123.22 MB | EUR | Ready for Modeling |
| `flight_prices` | 300,153 | 16 | 212.28 MB | INR | Ready for Modeling |
| `flights` | 1,000 | 33 | 0.63 MB | OPERATIONAL | Ready for Modeling |
| `airlines` | 14 | 2 | 0.00 MB | METADATA | Ready for Modeling |
| `airports` | 322 | 7 | 0.11 MB | METADATA | Ready for Modeling |
| `customer_search_events` | 5,000 | 16 | 2.62 MB | INR | Ready for Modeling |
| `supplier_offers` | 5,000 | 18 | 2.88 MB | INR | Ready for Modeling |
| `inventory_availability` | 5,000 | 15 | 2.79 MB | OPERATIONAL | Ready for Modeling |
| `market_seasonal_signals` | 5,000 | 13 | 1.40 MB | INDEX | Ready for Modeling |


---

## 3. Financial Currency Segmentation & Safety Rules

To guarantee mathematical and financial integrity, strict currency isolation rules are enforced:
- **Hospitality Portfolio (`hotel_bookings`):** **EUR (€)**. Reflects Portuguese resort and city hotel operations.
- **Dynamic Flight Pricing (`flight_prices`):** **INR (₹)**. Reflects Indian domestic aviation routes.
- **B2B Procurement & Supplier Offers (`supplier_offers`):** **INR (₹)**. Wholesale procurement costs and supplier selling prices.
- **Demand Search Events (`customer_search_events`):** **INR (₹)**. Customer searched budgets and price points.
- **Flight Operations (`flights`):** **Operational Units** (Elapsed time and delays in minutes, distance in miles).

> [!IMPORTANT]
> **Cross-Currency Boundary:** Financial values in EUR and INR are never added, subtracted, or compared as ratios without an explicit, dated foreign exchange rate. Direct summation is strictly prevented in the analytical codebase.

---

## 4. Missingness & Data Quality Re-Audit

Data quality auditing confirms zero critical data loss across all primary key dimensions. Missing values in flight operational delays (`AIR_SYSTEM_DELAY`, `WEATHER_DELAY`, etc.) occur strictly when flights arrive on schedule or early, representing legitimate non-applicability rather than missing data.

*Detailed table saved to:* `reports/eda/tables/dataset_overview_table.md`
