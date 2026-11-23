# TBO InventoryIQ – AI-Powered Travel Inventory & Profit Optimization Platform

TBO InventoryIQ is an enterprise-grade AI decision support and profit optimization platform built for travel businesses, tour operators, and wholesalers (B2B/B2C). It analyzes historical bookings, real-time customer search demands, airline routes, dynamic flight prices, hotel inventory availability, supplier wholesale offers, and seasonal macroeconomic signals to optimize inventory procurement and maximize gross margins.

---

## 1. Project Directory & Pipeline Architecture

```text
TBO-InventoryIQ/
│
├── data/
│   ├── raw/                           # Raw immutable public datasets
│   │   ├── flights/                   # flights.csv, airports.csv, airlines.csv
│   │   ├── flight_prices/             # Flight Price Prediction.csv
│   │   └── hotel_bookings/            # hotel_bookings.csv
│   ├── synthetic/                     # Generated market, supply, inventory, and search logs
│   │   ├── customer_search_events.csv
│   │   ├── inventory_availability.csv
│   │   ├── market_seasonal_signals.csv
│   │   └── supplier_offers.csv
│   └── processed/                     # Production-cleaned Parquet and CSV files
│       ├── flights/
│       ├── flight_prices/
│       ├── hotel_bookings/
│       ├── searches/
│       ├── inventory/
│       ├── supplier_offers/
│       └── market_signals/
│
├── data_pipeline/                     # Reusable data cleaning and validation framework
│   ├── config.py                      # Centralized path, schema, and threshold configurations
│   ├── ingestion/
│   │   └── dataset_loader.py          # Optimized typed loading with memory safety
│   ├── validation/
│   │   ├── schema_validation.py       # Pandera schema models
│   │   ├── missing_values.py          # Missing value analysis and legitimacy classification
│   │   ├── duplicate_detection.py     # Exact row and primary key collision detection
│   │   ├── datatype_validation.py     # Type checking and malformed value detection
│   │   ├── id_consistency.py          # Cross-dataset referential integrity
│   │   ├── business_rules.py          # Domain travel business rules enforcement
│   │   ├── outlier_detection.py       # IQR and domain boundary outlier analysis
│   │   └── validation_report.py       # JSON, CSV, and Markdown audit generator
│   └── cleaning/
│       ├── clean_flights.py           # Flights, airlines, and airports cleaning
│       ├── clean_flight_prices.py     # Flight pricing data hygiene and route engineering
│       ├── clean_hotel_bookings.py    # Hotel booking hygiene and error removal
│       ├── clean_search_events.py     # Customer search funnels and lead days
│       ├── clean_inventory.py         # Inventory capacity equation enforcement
│       ├── clean_supplier_offers.py   # Margin calculations and wholesale offer curation
│       ├── clean_market_signals.py    # Macroeconomic climate and demand index bounds
│       └── cleaning_pipeline.py       # End-to-end cleaning orchestrator
│
├── reports/
│   └── data_quality/                  # Generated audit files
│       ├── dataset_profile.json
│       ├── missing_values.csv
│       ├── duplicates.csv
│       ├── datatype_issues.csv
│       ├── id_consistency.csv
│       ├── business_rule_violations.csv
│       ├── outliers.csv
│       ├── cleaning_summary.json
│       └── final_validation_report.md
│
├── scripts/
│   └── validate_all_datasets.py       # CLI master runner
│
├── tests/
│   └── data_quality/                  # Automated pytest quality suite
│       ├── conftest.py
│       ├── test_dataset_loading.py
│       ├── test_validation_rules.py
│       └── test_cleaning_pipeline.py
│
├── requirements.txt                   # Dependency definitions
└── pyproject.toml                     # Pytest and packaging configuration
```

---

## 2. Dataset Overview & Cleaning Summary

| Dataset Name | Source Location | Raw Rows | Cleaned Rows | Rows Filtered | Primary Key / Identifier | Cleaning Highlights |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `market_seasonal_signals` | `data/synthetic/` | 5,000 | 5,000 | 0 (100% retention) | `signal_id` | Enforced `demand_index` within [0, 1], normalized Gregorian months, ISO dates. |
| `inventory_availability` | `data/synthetic/` | 5,000 | 5,000 | 0 (100% retention) | `snapshot_id` | Preserved legitimate null `origin_id` for stationary hotels; enforced capacity balance (`avail = total - booked`). |
| `supplier_offers` | `data/synthetic/` | 5,000 | 5,000 | 0 (100% retention) | `offer_id` | Engineered `unit_margin` and `margin_percentage`; flagged negative margins without discarding valid loss-leaders. |
| `customer_search_events` | `data/synthetic/` | 5,000 | 5,000 | 0 (100% retention) | `search_id` | Engineered `search_lead_days`; synchronized funnel where `booking_completed` entails `clicked`. |
| `airlines` | `data/raw/flights/` | 14 | 14 | 0 (100% retention) | `IATA_CODE` | 100% match with carriers in flight records. |
| `airports` | `data/raw/flights/` | 322 | 322 | 0 (100% retention) | `IATA_CODE` | Cleaned coordinates and airport names. |
| `flights` | `data/raw/flights/` | 5,819,079 | 5,819,079 | 0 (100% retention) | Composite Flight Key | Synthesized `FLIGHT_DATE` and `ROUTE`; cataloged US DOT 5-digit FAA airport transition; preserved cancelled flights. |
| `flight_prices` | `data/raw/flight_prices/` | 300,153 | 197,516 | 102,637 (65.8% retention) | `price_record_id` | Removed 102,637 identical scraped price quotes; extracted numeric `stops_count`; synthesized route features. |
| `hotel_bookings` | `data/raw/hotel_bookings/` | 119,390 | 87,228 | 32,162 (73.1% retention) | Composite Reservation | Removed 31,994 exact duplicate rows, 1 negative ADR (-6.38), 1 extreme outlier (5400.0), 166 phantom zero-occupancy bookings; preserved 27.52% cancellation rate. |

---

## 3. Quick Start & Execution

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Run Automated Data Quality Tests
```bash
python -m pytest tests/data_quality -v --cov=data_pipeline
```

### Execute Validation & Cleaning Pipeline via CLI
```bash
# Run on sample of high-volume flights dataset
python scripts/validate_all_datasets.py --flight-sample 50000

# Run on all 5.8 million flights
python scripts/validate_all_datasets.py
```

### Outputs
- Cleaned datasets are written to `data/processed/<domain>/` in both **Parquet** (columnar, fast) and **CSV** formats.
- Quality audit reports are generated in `reports/data_quality/`.
