"""
Generates the 8 canonical Phase 2 Jupyter Notebooks for TBO InventoryIQ.
"""

import json
from pathlib import Path

notebooks_dir = Path("notebooks")
notebooks_dir.mkdir(parents=True, exist_ok=True)


def make_cell(cell_type, text):
    lines = [line + "\n" for line in text.split("\n")]
    if lines and lines[-1] == "\n":
        lines[-1] = ""
    cell = {
        "cell_type": cell_type,
        "metadata": {},
        "source": lines,
    }
    if cell_type == "code":
        cell["execution_count"] = None
        cell["outputs"] = []
    return cell


def save_notebook(filename, cells):
    nb = {
        "cells": cells,
        "metadata": {
            "language_info": {
                "name": "python",
                "version": "3.10.0",
            },
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    with open(notebooks_dir / filename, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=1)
    print(f"Generated {filename}")


# 1. 01_data_overview.ipynb
nb1_cells = [
    make_cell("markdown", """# 01. TBO InventoryIQ – Comprehensive Data Overview
**Phase 2: Exploratory Data Analysis & Statistical Profiling**  
**Team:** Team Sabuj Sangha (Abhranil Pal & Arka Dyuti Bose)

This notebook discovers, profiles, and audits all nine processed travel datasets, establishing the analytical baseline for inventory procurement and profit optimization."""),
    make_cell("code", """import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()))

import pandas as pd
import numpy as np
from eda.data_loader import load_all_datasets, get_dataset_metadata
from eda.profiling import profile_dataset, generate_missing_summary
from eda.config import CURRENCY_MAP"""),
    make_cell("markdown", "## 1. Load All 9 Processed Datasets & Inspect Metadata"),
    make_cell("code", """datasets = load_all_datasets(prefer_parquet=True)
metadata = [get_dataset_metadata(name, df) for name, df in datasets.items()]
meta_df = pd.DataFrame(metadata)
meta_df[["dataset_name", "row_count", "column_count", "memory_mb", "currency"]]"""),
    make_cell("markdown", "## 2. Multi-Currency Domain Separation & Safety Rules"),
    make_cell("code", """for name, curr in CURRENCY_MAP.items():
    print(f"Dataset '{name}': Currency/Domain = {curr}")"""),
    make_cell("markdown", "## 3. Data Missingness & Quality Profile"),
    make_cell("code", """missing_reports = []
for name, df in datasets.items():
    ms = generate_missing_summary(df, name)
    missing_reports.append(ms[ms["missing_count"] > 0])
all_missing = pd.concat(missing_reports, ignore_index=True) if missing_reports else pd.DataFrame()
all_missing"""),
]

# 2. 02_hotel_booking_analysis.ipynb
nb2_cells = [
    make_cell("markdown", """# 02. Hotel Booking & Hospitality Analytics
**Phase 2: Exploratory Data Analysis**  
**Dataset:** `cleaned_hotel_bookings` (119,208 records, Currency: EUR €)

Explores cancellation rates, booking lead time dynamics, Average Daily Rate (ADR) distributions, RevPAR proxy, and market segment risk profiles."""),
    make_cell("code", """import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()))

import pandas as pd
from IPython.display import Image, display
from eda.data_loader import load_dataset
from eda.kpi_calculations import compute_hotel_kpis
from eda.visualization import plot_hotel_cancellation_by_lead_time, plot_hotel_adr_by_market_segment, plot_correlation_heatmap
from eda.config import FIGURES_DIR"""),
    make_cell("markdown", "## 1. Hospitality Key Performance Indicators"),
    make_cell("code", """hotel_df = load_dataset("hotel_bookings")
hotel_kpis = compute_hotel_kpis(hotel_df)
print(f"Total Bookings: {hotel_kpis['total_bookings']:,}")
print(f"Cancellation Rate: {hotel_kpis['cancellation_rate_pct']:.2f}%")
print(f"Average Daily Rate (ADR): €{hotel_kpis['avg_adr_eur']:.2f}")
print(f"RevPAR Proxy Yield: €{hotel_kpis['revpar_proxy_eur']:.2f}")
print(f"Average Lead Time: {hotel_kpis['avg_lead_time_days']:.1f} days")"""),
    make_cell("markdown", "## 2. Cancellation by Booking Lead Time Window"),
    make_cell("code", """fig1_path = plot_hotel_cancellation_by_lead_time(hotel_df)
display(Image(filename=str(fig1_path)))"""),
    make_cell("markdown", "## 3. ADR Distribution by Market Segment & Hotel Type"),
    make_cell("code", """fig2_path = plot_hotel_adr_by_market_segment(hotel_df)
display(Image(filename=str(fig2_path)))"""),
    make_cell("markdown", "## 4. Feature Correlation Heatmap & Target Leakage Guardrails"),
    make_cell("code", """hotel_cols = ["lead_time", "stays_in_weekend_nights", "stays_in_week_nights", "adults", "children", "adr", "is_canceled", "total_stay_nights"]
fig13_path = plot_correlation_heatmap(hotel_df, hotel_cols, "Hotel Feature Correlation Heatmap", FIGURES_DIR / "correlation_heatmap_hotel.png")
display(Image(filename=str(fig13_path)))"""),
]

# 3. 03_flight_operations_analysis.ipynb
nb3_cells = [
    make_cell("markdown", """# 03. Flight Operations & Carrier Reliability Analysis
**Phase 2: Exploratory Data Analysis**  
**Dataset:** `cleaned_flights`, `cleaned_airlines`, `cleaned_airports`

Examines carrier operational reliability, delay causes, on-time performance (<=15 min delay), and airport hub dynamics."""),
    make_cell("code", """import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()))

import pandas as pd
from IPython.display import Image, display
from eda.data_loader import load_dataset
from eda.kpi_calculations import compute_flight_operations_kpis
from eda.visualization import plot_flight_delay_causes_breakdown, plot_flight_ontime_by_airline"""),
    make_cell("markdown", "## 1. Flight Operations Key Performance Indicators"),
    make_cell("code", """flights_df = load_dataset("flights")
airlines_df = load_dataset("airlines")
airports_df = load_dataset("airports")

flight_kpis = compute_flight_operations_kpis(flights_df)
print(f"Total Flights: {flight_kpis['total_flights']:,}")
print(f"On-Time Arrival Rate: {flight_kpis['ontime_arrival_rate_pct']:.2f}%")
print(f"Cancellation Rate: {flight_kpis['cancellation_rate_pct']:.2f}%")
print(f"Average Arrival Delay: {flight_kpis['avg_arrival_delay_min']:.2f} min")"""),
    make_cell("markdown", "## 2. Delay Cause Breakdown"),
    make_cell("code", """fig5_path = plot_flight_delay_causes_breakdown(flights_df)
display(Image(filename=str(fig5_path)))"""),
    make_cell("markdown", "## 3. Airline On-Time Performance Benchmarking"),
    make_cell("code", """fig6_path = plot_flight_ontime_by_airline(flights_df, airlines_df)
display(Image(filename=str(fig6_path)))"""),
]

# 4. 04_flight_price_analysis.ipynb
nb4_cells = [
    make_cell("markdown", """# 04. Dynamic Flight Pricing & Yield Analysis
**Phase 2: Exploratory Data Analysis**  
**Dataset:** `cleaned_flight_prices` (300,153 records, Currency: INR ₹)

Analyzes airline dynamic yield curves, the days-left departure surge, cabin class multipliers, and stopover pricing effects."""),
    make_cell("code", """import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()))

import pandas as pd
from IPython.display import Image, display
from eda.data_loader import load_dataset
from eda.kpi_calculations import compute_flight_price_kpis
from eda.visualization import plot_flight_price_by_days_left, plot_flight_price_economy_vs_business, plot_correlation_heatmap
from eda.config import FIGURES_DIR"""),
    make_cell("markdown", "## 1. Flight Fare Key Metrics"),
    make_cell("code", """prices_df = load_dataset("flight_prices")
price_kpis = compute_flight_price_kpis(prices_df)
print(f"Total Price Quotes: {price_kpis['total_price_quotes']:,}")
print(f"Mean Price: ₹{price_kpis['avg_price_inr']:,.2f}")
print(f"Median Price: ₹{price_kpis['median_price_inr']:,.2f}")
print(f"Business-to-Economy Ratio: {price_kpis['business_to_economy_price_ratio']:.2f}x")
print(f"Days-Left Price Correlation: {price_kpis['days_left_price_correlation']:.4f}")"""),
    make_cell("markdown", "## 2. Dynamic Price Surge by Days Left"),
    make_cell("code", """fig3_path = plot_flight_price_by_days_left(prices_df)
display(Image(filename=str(fig3_path)))"""),
    make_cell("markdown", "## 3. Economy vs Business Class Comparison"),
    make_cell("code", """fig4_path = plot_flight_price_economy_vs_business(prices_df)
display(Image(filename=str(fig4_path)))"""),
    make_cell("markdown", "## 4. Correlation Heatmap"),
    make_cell("code", """price_cols = ["duration", "days_left", "price", "stops_count"]
fig14_path = plot_correlation_heatmap(prices_df, price_cols, "Flight Price Correlation Heatmap", FIGURES_DIR / "correlation_heatmap_flight_prices.png")
display(Image(filename=str(fig14_path)))"""),
]

# 5. 05_customer_search_analysis.ipynb
nb5_cells = [
    make_cell("markdown", """# 05. Customer Search Demand & Funnel Conversion Analysis
**Phase 2: Exploratory Data Analysis**  
**Dataset:** `cleaned_customer_search_events` (5,000 records, Currency: INR ₹)

Analyzes customer search intent, conversion funnel drop-off, search-to-book ratios, and destination popularity."""),
    make_cell("code", """import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()))

import pandas as pd
from IPython.display import Image, display
from eda.data_loader import load_dataset
from eda.kpi_calculations import compute_search_kpis
from eda.visualization import plot_customer_search_conversion_funnel, plot_search_demand_by_destination"""),
    make_cell("markdown", "## 1. Funnel Conversion KPIs"),
    make_cell("code", """searches_df = load_dataset("customer_search_events")
search_kpis = compute_search_kpis(searches_df)
print(f"Total Searches: {search_kpis['total_searches']:,}")
print(f"Search-to-Click Rate: {search_kpis['search_to_click_pct']:.2f}%")
print(f"Click-to-Book Rate: {search_kpis['click_to_book_pct']:.2f}%")
print(f"Search-to-Book Rate: {search_kpis['search_to_book_pct']:.2f}%")
print(f"Average Searched Price: ₹{search_kpis['avg_search_price_inr']:,.2f}")"""),
    make_cell("markdown", "## 2. Customer Conversion Funnel Drop-off"),
    make_cell("code", """fig7_path = plot_customer_search_conversion_funnel(searches_df)
display(Image(filename=str(fig7_path)))"""),
    make_cell("markdown", "## 3. Top Destinations by Search Demand"),
    make_cell("code", """fig8_path = plot_search_demand_by_destination(searches_df)
display(Image(filename=str(fig8_path)))"""),
]

# 6. 06_supplier_inventory_analysis.ipynb
nb6_cells = [
    make_cell("markdown", """# 06. Supplier Offers, Margins & Inventory Tracking
**Phase 2: Exploratory Data Analysis**  
**Datasets:** `cleaned_supplier_offers`, `cleaned_inventory_availability` (Currency: INR ₹)

Evaluates supplier procurement costs, gross profit margins, inventory capacity utilization, and snapshot cardinality guardrails."""),
    make_cell("code", """import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()))

import pandas as pd
from IPython.display import Image, display
from eda.data_loader import load_dataset
from eda.kpi_calculations import compute_supplier_kpis, compute_inventory_kpis
from eda.snapshot_analysis import validate_snapshot_cardinality, get_latest_inventory_snapshots
from eda.visualization import plot_inventory_utilization_distribution, plot_supplier_markup_and_margin_by_supplier"""),
    make_cell("markdown", "## 1. Supplier Procurement KPIs & Margins"),
    make_cell("code", """supplier_df = load_dataset("supplier_offers")
supplier_kpis = compute_supplier_kpis(supplier_df)
print(f"Total Offers: {supplier_kpis['total_offers']:,}")
print(f"Average Wholesale Cost: ₹{supplier_kpis['avg_purchase_cost_inr']:,.2f}")
print(f"Average Retail Selling: ₹{supplier_kpis['avg_selling_price_inr']:,.2f}")
print(f"Average Margin: {supplier_kpis['avg_margin_pct']:.2f}%")
print(f"Negative Margin Offers: {supplier_kpis['negative_margin_offers']} ({supplier_kpis['negative_margin_pct']:.2f}%)")"""),
    make_cell("markdown", "## 2. Inventory Utilization & Snapshot Deduplication"),
    make_cell("code", """inventory_df = load_dataset("inventory_availability")
card = validate_snapshot_cardinality(inventory_df)
print("Snapshot Validation:", card["cardinality_guideline"])

inv_kpis = compute_inventory_kpis(inventory_df, deduplicate_snapshots=True)
print(f"Unique Inventory Units: {inv_kpis['distinct_inventory_items']:,}")
print(f"Total Physical Capacity: {inv_kpis['total_capacity']:,.0f}")
print(f"Total Booked Units: {inv_kpis['total_booked_units']:,.0f}")
print(f"Capacity Utilization Rate: {inv_kpis['overall_utilization_rate_pct']:.2f}%")
print(f"Stockout Frequency: {inv_kpis['stockout_frequency_pct']:.2f}%")"""),
    make_cell("markdown", "## 3. Inventory Utilization & Supplier Margin Figures"),
    make_cell("code", """fig9_path = plot_inventory_utilization_distribution(inventory_df)
display(Image(filename=str(fig9_path)))

fig10_path = plot_supplier_markup_and_margin_by_supplier(supplier_df)
display(Image(filename=str(fig10_path)))"""),
]

# 7. 07_market_seasonality_analysis.ipynb
nb7_cells = [
    make_cell("markdown", """# 07. Market Seasonality & Macro Signals Analysis
**Phase 2: Exploratory Data Analysis**  
**Dataset:** `cleaned_market_seasonal_signals` (5,000 records)

Assesses seasonal travel index fluctuations across calendar months, holiday/festival uplifts, and environmental influences."""),
    make_cell("code", """import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()))

import pandas as pd
from IPython.display import Image, display
from eda.data_loader import load_dataset
from eda.visualization import plot_market_seasonality_index_monthly"""),
    make_cell("markdown", "## 1. Monthly Seasonality Profile"),
    make_cell("code", """signals_df = load_dataset("market_seasonal_signals")
monthly_summary = signals_df.groupby("month").agg(
    avg_demand_index=("demand_index", "mean"),
    avg_temp=("temperature", "mean"),
    avg_rainfall=("rainfall_mm", "mean"),
    holidays=("holiday_indicator", "sum"),
).reset_index()
monthly_summary"""),
    make_cell("markdown", "## 2. Market Seasonality Trajectory"),
    make_cell("code", """fig11_path = plot_market_seasonality_index_monthly(signals_df)
display(Image(filename=str(fig11_path)))"""),
]

# 8. 08_combined_business_insights.ipynb
nb8_cells = [
    make_cell("markdown", """# 08. Unified Business Intelligence & Procurement Synthesis
**Phase 2: Exploratory Data Analysis & Decision Intelligence**  
**Team:** Team Sabuj Sangha (Abhranil Pal & Arka Dyuti Bose)

Cross-domain synthesis combining customer demand, supplier offerings, inventory availability, and cancellation buffers to formulate actionable procurement rules."""),
    make_cell("code", """import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()))

import pandas as pd
from IPython.display import Image, display
from eda.data_loader import load_all_datasets
from eda.kpi_calculations import compute_hotel_kpis, compute_supplier_kpis, compute_inventory_kpis, compute_flight_price_kpis
from eda.relationship_analysis import analyze_demand_vs_supply
from eda.business_insights import generate_executive_business_insights
from eda.visualization import plot_cross_domain_demand_vs_supply_gap"""),
    make_cell("markdown", "## 1. Cross-Domain Demand vs Supply Alignment"),
    make_cell("code", """datasets = load_all_datasets(prefer_parquet=True)
demand_supply_df = analyze_demand_vs_supply(
    datasets["customer_search_events"],
    datasets["inventory_availability"],
    datasets["supplier_offers"],
)
demand_supply_df.head(10)"""),
    make_cell("markdown", "## 2. Demand vs Supply Gap Visualization"),
    make_cell("code", """fig12_path = plot_cross_domain_demand_vs_supply_gap(demand_supply_df)
display(Image(filename=str(fig12_path)))"""),
    make_cell("markdown", "## 3. Executive Procurement Intelligence & Rules"),
    make_cell("code", """hotel_kpis = compute_hotel_kpis(datasets["hotel_bookings"])
supplier_kpis = compute_supplier_kpis(datasets["supplier_offers"])
inv_kpis = compute_inventory_kpis(datasets["inventory_availability"])
price_kpis = compute_flight_price_kpis(datasets["flight_prices"])

insights = generate_executive_business_insights(
    demand_supply_df, supplier_kpis, hotel_kpis, price_kpis, inv_kpis
)
print("Top Procurement Priority Destinations:", insights["top_procurement_destinations"])
print("Over-Supplied Risk Destinations:", insights["over_supplied_destinations"])
print("Recommended Overbooking Buffer:", f"{insights['cancellation_and_overbooking']['recommended_overbooking_buffer_pct']}%")
print("Supplier Strategy:", insights["supplier_intelligence"]["recommended_supplier_strategy"])"""),
]

save_notebook("01_data_overview.ipynb", nb1_cells)
save_notebook("02_hotel_booking_analysis.ipynb", nb2_cells)
save_notebook("03_flight_operations_analysis.ipynb", nb3_cells)
save_notebook("04_flight_price_analysis.ipynb", nb4_cells)
save_notebook("05_customer_search_analysis.ipynb", nb5_cells)
save_notebook("06_supplier_inventory_analysis.ipynb", nb6_cells)
save_notebook("07_market_seasonality_analysis.ipynb", nb7_cells)
save_notebook("08_combined_business_insights.ipynb", nb8_cells)

print("All 8 notebooks generated successfully.")
