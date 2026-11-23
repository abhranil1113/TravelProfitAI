"""
TBO InventoryIQ - Full EDA Pipeline Runner (Phase 2)
Executes end-to-end data loading, profiling, statistical testing, KPI computation,
cross-dataset synthesis, visualization generation, and report compilation.
"""

import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import logging
from typing import Dict, Any
import pandas as pd

from eda.data_loader import load_all_datasets, get_dataset_metadata
from eda.profiling import profile_dataset, generate_missing_summary
from eda.kpi_calculations import (
    compute_hotel_kpis,
    compute_flight_price_kpis,
    compute_flight_operations_kpis,
    compute_search_kpis,
    compute_supplier_kpis,
    compute_inventory_kpis,
)
from eda.relationship_analysis import analyze_demand_vs_supply, analyze_seasonality_vs_demand
from eda.business_insights import generate_executive_business_insights
from eda.visualization import generate_all_visualizations
from eda.report_generator import (
    generate_dataset_overview_report,
    generate_hotel_booking_report,
    generate_flight_operations_report,
    generate_flight_price_report,
    generate_customer_search_report,
    generate_supplier_inventory_report,
    generate_market_seasonality_report,
    generate_combined_business_insights_report,
    generate_modeling_readiness_report,
    generate_eda_summary_json,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_full_eda_pipeline() -> Dict[str, Any]:
    """
    Executes the complete Phase 2 Exploratory Data Analysis & Business Intelligence workflow.
    """
    logger.info("==================================================================")
    logger.info("Starting TBO InventoryIQ Phase 2: Exploratory Data Analysis Engine")
    logger.info("==================================================================")

    # 1. Load Datasets
    logger.info("Step 1: Loading all 9 validated processed datasets...")
    datasets = load_all_datasets(prefer_parquet=True)
    metadata_list = [get_dataset_metadata(name, df) for name, df in datasets.items()]

    # 2. Compute Domain KPIs
    logger.info("Step 2: Computing domain KPIs across all business verticals...")
    hotel_kpis = compute_hotel_kpis(datasets["hotel_bookings"])
    price_kpis = compute_flight_price_kpis(datasets["flight_prices"])
    flight_kpis = compute_flight_operations_kpis(datasets["flights"])
    search_kpis = compute_search_kpis(datasets["customer_search_events"])
    supplier_kpis = compute_supplier_kpis(datasets["supplier_offers"])
    inventory_kpis = compute_inventory_kpis(datasets["inventory_availability"])

    # 3. Cross-Domain Relationships
    logger.info("Step 3: Analyzing cross-domain relationships & demand-supply balance...")
    demand_supply_df = analyze_demand_vs_supply(
        datasets["customer_search_events"],
        datasets["inventory_availability"],
        datasets["supplier_offers"],
    )
    seasonality_df = analyze_seasonality_vs_demand(
        datasets["market_seasonal_signals"],
        datasets["customer_search_events"],
    )

    # 4. Synthesize Business Insights
    logger.info("Step 4: Synthesizing procurement intelligence & executive insights...")
    insights = generate_executive_business_insights(
        demand_supply_df=demand_supply_df,
        supplier_kpis=supplier_kpis,
        hotel_kpis=hotel_kpis,
        flight_price_kpis=price_kpis,
        inventory_kpis=inventory_kpis,
    )

    # 5. Generate Visualizations
    logger.info("Step 5: Rendering 14 high-resolution analytical visualizations...")
    figures = generate_all_visualizations(datasets, demand_supply_df)
    logger.info(f"Rendered {len(figures)} figures to reports/eda/figures/")

    # 6. Generate All 10 Reports
    logger.info("Step 6: Compiling all 10 analytical reports and summary JSON...")
    all_missing_df = pd.concat(
        [generate_missing_summary(df, name) for name, df in datasets.items()],
        ignore_index=True,
    )

    generate_dataset_overview_report(metadata_list, all_missing_df)
    generate_hotel_booking_report(hotel_kpis, datasets["hotel_bookings"])
    generate_flight_operations_report(flight_kpis)
    generate_flight_price_report(price_kpis)
    generate_customer_search_report(search_kpis)
    generate_supplier_inventory_report(supplier_kpis, inventory_kpis)
    generate_market_seasonality_report(datasets["market_seasonal_signals"])
    generate_combined_business_insights_report(demand_supply_df, insights)
    generate_modeling_readiness_report()
    generate_eda_summary_json(
        metadata_list=metadata_list,
        hotel_kpis=hotel_kpis,
        price_kpis=price_kpis,
        flight_kpis=flight_kpis,
        search_kpis=search_kpis,
        supplier_kpis=supplier_kpis,
        inventory_kpis=inventory_kpis,
        business_insights=insights,
    )

    logger.info("==================================================================")
    logger.info("Phase 2 EDA Pipeline Execution Complete - All 10 Reports Ready")
    logger.info("==================================================================")

    return {
        "status": "success",
        "datasets_profiled": len(datasets),
        "figures_generated": len(figures),
        "reports_generated": 10,
    }


if __name__ == "__main__":
    run_full_eda_pipeline()

