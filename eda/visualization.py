"""
TBO InventoryIQ - Visualization Engine for EDA (Phase 2)
Generates high-resolution (300 DPI) figures with descriptive titles,
explicit units, sample sizes, and professional styling.
"""

from pathlib import Path
from typing import Dict, List, Optional
import matplotlib
matplotlib.use("Agg")  # Headless backend
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np

from eda.config import FIGURES_DIR, PLOT_STYLE


def set_plot_theme():
    """Configures consistent professional styling across all charts."""
    sns.set_theme(style=PLOT_STYLE["style"], palette=PLOT_STYLE["palette"])
    plt.rcParams.update({
        "figure.dpi": PLOT_STYLE["dpi"],
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.labelsize": 11,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
    })


def plot_hotel_cancellation_by_lead_time(hotel_df: pd.DataFrame, save_path: Optional[Path] = None) -> Path:
    """Figure 1: Hotel cancellation rate grouped by lead time bins."""
    set_plot_theme()
    save_path = save_path or (FIGURES_DIR / "hotel_cancellation_by_lead_time.png")

    df = hotel_df.copy()
    bins = [0, 7, 30, 90, 180, 365, 800]
    labels = ["0-7d", "8-30d", "31-90d", "91-180d", "181-365d", "365d+"]
    df["lead_time_bin"] = pd.cut(df["lead_time"], bins=bins, labels=labels, right=True)

    summary = df.groupby("lead_time_bin", observed=True)["is_canceled"].agg(
        total="count",
        cancellation_rate="mean",
    ).reset_index()
    summary["cancellation_rate_pct"] = summary["cancellation_rate"] * 100

    fig, ax = plt.subplots(figsize=PLOT_STYLE["figure_sizes"]["standard"])
    bars = ax.bar(
        summary["lead_time_bin"].astype(str),
        summary["cancellation_rate_pct"],
        color="#2b5c8f",
        edgecolor="black",
        alpha=0.85,
    )

    for bar, count in zip(bars, summary["total"]):
        yval = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            yval + 1.2,
            f"{yval:.1f}%\n(n={count:,})",
            ha="center",
            va="bottom",
            fontsize=9,
            weight="semibold",
        )

    ax.set_title(f"Hotel Cancellation Rate by Booking Lead Time Window (n={len(df):,})")
    ax.set_xlabel("Booking Lead Time Window (Days Prior to Arrival)")
    ax.set_ylabel("Cancellation Rate (%)")
    ax.set_ylim(0, max(summary["cancellation_rate_pct"]) + 15)
    ax.grid(axis="y", linestyle="--", alpha=0.7)

    plt.tight_layout()
    plt.savefig(save_path, dpi=PLOT_STYLE["dpi"])
    plt.close()
    return save_path


def plot_hotel_adr_by_market_segment(hotel_df: pd.DataFrame, save_path: Optional[Path] = None) -> Path:
    """Figure 2: Distribution of Average Daily Rate (ADR) across market segments (EUR)."""
    set_plot_theme()
    save_path = save_path or (FIGURES_DIR / "hotel_adr_by_market_segment.png")

    df = hotel_df[(hotel_df["adr"] > 0) & (hotel_df["adr"] <= 500)].copy()

    fig, ax = plt.subplots(figsize=PLOT_STYLE["figure_sizes"]["wide"])
    sns.boxplot(
        data=df,
        x="market_segment",
        y="adr",
        hue="hotel",
        palette=["#3470a3", "#e07a5f"],
        ax=ax,
        showmeans=True,
        meanprops={"marker": "o", "markerfacecolor": "white", "markeredgecolor": "black"},
    )

    ax.set_title(f"Hotel Average Daily Rate (ADR in EUR) by Market Segment & Hotel Type (n={len(df):,})")
    ax.set_xlabel("Market Segment")
    ax.set_ylabel("Average Daily Rate (ADR in EUR €)")
    ax.legend(title="Hotel Property Type")
    plt.xticks(rotation=25, ha="right")

    plt.tight_layout()
    plt.savefig(save_path, dpi=PLOT_STYLE["dpi"])
    plt.close()
    return save_path


def plot_flight_price_by_days_left(prices_df: pd.DataFrame, save_path: Optional[Path] = None) -> Path:
    """Figure 3: Flight price trajectory as departure date approaches (INR)."""
    set_plot_theme()
    save_path = save_path or (FIGURES_DIR / "flight_price_by_days_left.png")

    trend = prices_df.groupby(["days_left", "class"])["price"].agg(["mean", "median"]).reset_index()

    fig, ax = plt.subplots(figsize=PLOT_STYLE["figure_sizes"]["wide"])
    sns.lineplot(
        data=trend,
        x="days_left",
        y="mean",
        hue="class",
        palette=["#e76f51", "#2a9d8f"],
        linewidth=2.5,
        ax=ax,
    )

    ax.set_title(f"Dynamic Flight Pricing by Days Left to Departure (INR ₹) (n={len(prices_df):,})")
    ax.set_xlabel("Days Left Until Flight Departure")
    ax.set_ylabel("Mean Ticket Price (INR ₹)")
    ax.invert_xaxis()  # Departure day approaches from left to right
    ax.grid(True, linestyle="--", alpha=0.7)
    ax.legend(title="Cabin Class")

    plt.tight_layout()
    plt.savefig(save_path, dpi=PLOT_STYLE["dpi"])
    plt.close()
    return save_path


def plot_flight_price_economy_vs_business(prices_df: pd.DataFrame, save_path: Optional[Path] = None) -> Path:
    """Figure 4: Economy vs Business class ticket price distribution by airline (INR)."""
    set_plot_theme()
    save_path = save_path or (FIGURES_DIR / "flight_price_economy_vs_business.png")

    fig, ax = plt.subplots(figsize=PLOT_STYLE["figure_sizes"]["wide"])
    sns.barplot(
        data=prices_df,
        x="airline",
        y="price",
        hue="class",
        estimator=np.mean,
        palette=["#457b9d", "#e63946"],
        ax=ax,
        errorbar=None,
    )

    for p in ax.patches:
        height = p.get_height()
        if height > 0:
            ax.annotate(
                f"₹{height:,.0f}",
                (p.get_x() + p.get_width() / 2.0, height),
                ha="center",
                va="bottom",
                fontsize=9,
                xytext=(0, 3),
                textcoords="offset points",
            )

    ax.set_title(f"Mean Flight Price Comparison by Airline & Class (INR ₹) (n={len(prices_df):,})")
    ax.set_xlabel("Airline")
    ax.set_ylabel("Mean Price (INR ₹)")
    ax.legend(title="Class")
    plt.xticks(rotation=20, ha="right")

    plt.tight_layout()
    plt.savefig(save_path, dpi=PLOT_STYLE["dpi"])
    plt.close()
    return save_path


def plot_flight_delay_causes_breakdown(flights_df: pd.DataFrame, save_path: Optional[Path] = None) -> Path:
    """Figure 5: Operational flight delay causes breakdown (Minutes)."""
    set_plot_theme()
    save_path = save_path or (FIGURES_DIR / "flight_delay_causes_breakdown.png")

    cause_cols = [
        "AIR_SYSTEM_DELAY",
        "SECURITY_DELAY",
        "AIRLINE_DELAY",
        "LATE_AIRCRAFT_DELAY",
        "WEATHER_DELAY",
    ]
    present_cols = [c for c in cause_cols if c in flights_df.columns]
    sums = flights_df[present_cols].sum()

    labels = [c.replace("_DELAY", "").replace("_", " ").title() for c in present_cols]
    values = sums.values

    fig, ax = plt.subplots(figsize=PLOT_STYLE["figure_sizes"]["standard"])
    colors = ["#264653", "#2a9d8f", "#e9c46a", "#f4a261", "#e76f51"]

    wedges, texts, autotexts = ax.pie(
        values,
        labels=labels,
        autopct="%1.1f%%",
        startangle=140,
        colors=colors[:len(values)],
        textprops=dict(color="black", weight="semibold"),
    )

    ax.set_title(f"US Flight Operations: Primary Delay Causes Breakdown (Total Minutes)")

    plt.tight_layout()
    plt.savefig(save_path, dpi=PLOT_STYLE["dpi"])
    plt.close()
    return save_path


def plot_flight_ontime_by_airline(
    flights_df: pd.DataFrame,
    airlines_df: Optional[pd.DataFrame] = None,
    save_path: Optional[Path] = None,
) -> Path:
    """Figure 6: Airline on-time arrival performance rate (<= 15 minutes delay)."""
    set_plot_theme()
    save_path = save_path or (FIGURES_DIR / "flight_ontime_by_airline.png")

    df = flights_df.copy()
    if airlines_df is not None and "IATA_CODE" in airlines_df.columns:
        df = df.merge(airlines_df, left_on="AIRLINE", right_on="IATA_CODE", how="left")
        carrier_col = "AIRLINE_y" if "AIRLINE_y" in df.columns else "AIRLINE"
    else:
        carrier_col = "AIRLINE"

    completed = df[df["CANCELLED"] == 0] if "CANCELLED" in df.columns else df
    completed["is_ontime"] = (completed["ARRIVAL_DELAY"] <= 15).astype(int)

    summary = completed.groupby(carrier_col).agg(
        flights=("is_ontime", "count"),
        ontime_rate=("is_ontime", "mean"),
    ).reset_index()
    summary["ontime_rate_pct"] = summary["ontime_rate"] * 100
    summary = summary.sort_values(by="ontime_rate_pct", ascending=True)

    fig, ax = plt.subplots(figsize=PLOT_STYLE["figure_sizes"]["wide"])
    bars = ax.barh(
        summary[carrier_col].astype(str),
        summary["ontime_rate_pct"],
        color="#2a9d8f",
        edgecolor="black",
        alpha=0.85,
    )

    for bar, count in zip(bars, summary["flights"]):
        xval = bar.get_width()
        ax.text(
            xval + 1.0,
            bar.get_y() + bar.get_height() / 2,
            f"{xval:.1f}% (n={count:,})",
            ha="left",
            va="center",
            fontsize=9,
            weight="semibold",
        )

    ax.set_title("Airline On-Time Arrival Performance (Arrival Delay ≤ 15 Minutes)")
    ax.set_xlabel("On-Time Arrival Rate (%)")
    ax.set_xlim(0, 110)
    ax.grid(axis="x", linestyle="--", alpha=0.7)

    plt.tight_layout()
    plt.savefig(save_path, dpi=PLOT_STYLE["dpi"])
    plt.close()
    return save_path


def plot_customer_search_conversion_funnel(searches_df: pd.DataFrame, save_path: Optional[Path] = None) -> Path:
    """Figure 7: Search-to-Click-to-Book Funnel Drop-off."""
    set_plot_theme()
    save_path = save_path or (FIGURES_DIR / "customer_search_conversion_funnel.png")

    searches = len(searches_df)
    clicks = int(searches_df["clicked"].sum())
    bookings = int(searches_df["booking_completed"].sum())

    stages = ["Searches Initiated", "Offer Clicked", "Booking Completed"]
    counts = [searches, clicks, bookings]
    pcts = [100.0, (clicks / searches) * 100 if searches > 0 else 0, (bookings / searches) * 100 if searches > 0 else 0]

    fig, ax = plt.subplots(figsize=PLOT_STYLE["figure_sizes"]["standard"])
    bars = ax.bar(stages, counts, color=["#1d3557", "#457b9d", "#2a9d8f"], edgecolor="black", width=0.55)

    for bar, count, pct in zip(bars, counts, pcts):
        yval = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            yval + searches * 0.02,
            f"{count:,}\n({pct:.1f}% of total)",
            ha="center",
            va="bottom",
            fontsize=10,
            weight="bold",
        )

    ax.set_title(f"Customer Search-to-Booking Conversion Funnel (n={searches:,})")
    ax.set_ylabel("Total Event Count")
    ax.set_ylim(0, searches * 1.25)
    ax.grid(axis="y", linestyle="--", alpha=0.7)

    plt.tight_layout()
    plt.savefig(save_path, dpi=PLOT_STYLE["dpi"])
    plt.close()
    return save_path


def plot_search_demand_by_destination(searches_df: pd.DataFrame, save_path: Optional[Path] = None) -> Path:
    """Figure 8: Customer search volume distribution by destination."""
    set_plot_theme()
    save_path = save_path or (FIGURES_DIR / "search_demand_by_destination.png")

    counts = searches_df["destination_id"].value_counts().head(12).reset_index()
    counts.columns = ["destination_id", "search_volume"]

    fig, ax = plt.subplots(figsize=PLOT_STYLE["figure_sizes"]["wide"])
    sns.barplot(
        data=counts,
        x="destination_id",
        y="search_volume",
        palette="viridis",
        ax=ax,
        edgecolor="black",
    )

    for p in ax.patches:
        height = p.get_height()
        ax.annotate(
            f"{int(height):,}",
            (p.get_x() + p.get_width() / 2.0, height),
            ha="center",
            va="bottom",
            fontsize=9,
            xytext=(0, 3),
            textcoords="offset points",
            weight="semibold",
        )

    ax.set_title("Customer Search Volume by Destination (Top Destinations)")
    ax.set_xlabel("Destination ID")
    ax.set_ylabel("Total Customer Searches")
    plt.xticks(rotation=30, ha="right")

    plt.tight_layout()
    plt.savefig(save_path, dpi=PLOT_STYLE["dpi"])
    plt.close()
    return save_path


def plot_inventory_utilization_distribution(inventory_df: pd.DataFrame, save_path: Optional[Path] = None) -> Path:
    """Figure 9: Inventory utilization rate distribution across deduplicated items."""
    set_plot_theme()
    save_path = save_path or (FIGURES_DIR / "inventory_utilization_distribution.png")

    from eda.snapshot_analysis import get_latest_inventory_snapshots
    dedup = get_latest_inventory_snapshots(inventory_df)
    dedup["utilization_pct"] = (dedup["booked_quantity"] / dedup["total_capacity"]) * 100

    fig, ax = plt.subplots(figsize=PLOT_STYLE["figure_sizes"]["standard"])
    sns.histplot(
        dedup["utilization_pct"].dropna(),
        bins=20,
        kde=True,
        color="#3a86ff",
        edgecolor="black",
        ax=ax,
    )

    ax.set_title(f"Inventory Capacity Utilization Rate Distribution (Latest Snapshots, n={len(dedup):,})")
    ax.set_xlabel("Utilization Rate (% of Total Capacity Booked)")
    ax.set_ylabel("Number of Inventory Items")
    ax.grid(True, linestyle="--", alpha=0.7)

    plt.tight_layout()
    plt.savefig(save_path, dpi=PLOT_STYLE["dpi"])
    plt.close()
    return save_path


def plot_supplier_markup_and_margin_by_supplier(supplier_df: pd.DataFrame, save_path: Optional[Path] = None) -> Path:
    """Figure 10: Supplier average profit margin percentage by supplier (INR)."""
    set_plot_theme()
    save_path = save_path or (FIGURES_DIR / "supplier_markup_and_margin_by_supplier.png")

    margin_col = "margin_percentage" if "margin_percentage" in supplier_df.columns else "purchase_cost"
    summary = supplier_df.groupby("supplier_id")[margin_col].mean().reset_index()
    summary = summary.sort_values(by=margin_col, ascending=False)

    fig, ax = plt.subplots(figsize=PLOT_STYLE["figure_sizes"]["standard"])
    bars = ax.bar(
        summary["supplier_id"].astype(str),
        summary[margin_col],
        color="#06d6a0",
        edgecolor="black",
        alpha=0.9,
    )

    for bar in bars:
        yval = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            yval + 0.5,
            f"{yval:.1f}%",
            ha="center",
            va="bottom",
            fontsize=9,
            weight="bold",
        )

    ax.set_title(f"Average Gross Profit Margin Percentage by Supplier (n={len(supplier_df):,})")
    ax.set_xlabel("Supplier ID")
    ax.set_ylabel("Average Gross Margin (%)")
    ax.set_ylim(0, max(summary[margin_col]) + 5)
    ax.grid(axis="y", linestyle="--", alpha=0.7)

    plt.tight_layout()
    plt.savefig(save_path, dpi=PLOT_STYLE["dpi"])
    plt.close()
    return save_path


def plot_market_seasonality_index_monthly(signals_df: pd.DataFrame, save_path: Optional[Path] = None) -> Path:
    """Figure 11: Market seasonal demand index progression by calendar month."""
    set_plot_theme()
    save_path = save_path or (FIGURES_DIR / "market_seasonality_index_monthly.png")

    monthly = signals_df.groupby("month")["demand_index"].agg(["mean", "std", "min", "max"]).reset_index()

    fig, ax = plt.subplots(figsize=PLOT_STYLE["figure_sizes"]["wide"])
    ax.plot(monthly["month"], monthly["mean"], marker="o", color="#e76f51", linewidth=2.5, label="Mean Demand Index")
    ax.fill_between(
        monthly["month"],
        monthly["mean"] - monthly["std"],
        monthly["mean"] + monthly["std"],
        color="#e76f51",
        alpha=0.25,
        label="±1 Std Dev",
    )

    ax.set_title(f"Monthly Market Seasonal Demand Index Profile (n={len(signals_df):,})")
    ax.set_xlabel("Calendar Month (1=Jan ... 12=Dec)")
    ax.set_ylabel("Market Demand Index (Normalized 0-100+)")
    ax.set_xticks(range(1, 13))
    ax.grid(True, linestyle="--", alpha=0.7)
    ax.legend()

    plt.tight_layout()
    plt.savefig(save_path, dpi=PLOT_STYLE["dpi"])
    plt.close()
    return save_path


def plot_cross_domain_demand_vs_supply_gap(demand_supply_df: pd.DataFrame, save_path: Optional[Path] = None) -> Path:
    """Figure 12: Cross-domain demand-to-supply ratio across top destinations."""
    set_plot_theme()
    save_path = save_path or (FIGURES_DIR / "cross_domain_demand_vs_supply_gap.png")

    top_dest = demand_supply_df.head(10).copy()

    fig, ax1 = plt.subplots(figsize=PLOT_STYLE["figure_sizes"]["wide"])

    x = np.arange(len(top_dest))
    width = 0.35

    bars1 = ax1.bar(x - width/2, top_dest["search_volume"], width, label="Search Demand (Volume)", color="#1d3557")
    bars2 = ax1.bar(x + width/2, top_dest["available_units"], width, label="Available Inventory (Units)", color="#2a9d8f")

    ax1.set_xlabel("Destination ID")
    ax1.set_ylabel("Volume / Units Count")
    ax1.set_xticks(x)
    ax1.set_xticklabels(top_dest["destination_id"], rotation=25)
    ax1.legend(loc="upper left")
    ax1.grid(True, linestyle="--", alpha=0.5)

    ax2 = ax1.twinx()
    ax2.plot(x, top_dest["demand_to_supply_ratio"], color="#e63946", marker="D", linewidth=2, label="Demand / Supply Ratio")
    ax2.set_ylabel("Demand-to-Supply Ratio", color="#e63946")
    ax2.tick_params(axis="y", labelcolor="#e63946")
    ax2.legend(loc="upper right")

    plt.title("Cross-Domain Procurement Analysis: Demand vs Supply Availability by Destination")
    plt.tight_layout()
    plt.savefig(save_path, dpi=PLOT_STYLE["dpi"])
    plt.close()
    return save_path


def plot_correlation_heatmap(
    df: pd.DataFrame,
    cols: List[str],
    title: str,
    save_path: Path,
) -> Path:
    """Figures 13 & 14: Correlation Heatmap for numerical features."""
    set_plot_theme()
    valid_cols = [c for c in cols if c in df.columns]
    sub_df = df[valid_cols].select_dtypes(include=[np.number])
    corr = sub_df.corr(method="pearson")

    fig, ax = plt.subplots(figsize=PLOT_STYLE["figure_sizes"]["square"])
    sns.heatmap(
        corr,
        annot=True,
        fmt=".2f",
        cmap="coolwarm",
        center=0,
        square=True,
        linewidths=0.5,
        cbar_kws={"shrink": 0.8},
        ax=ax,
    )

    ax.set_title(title)
    plt.xticks(rotation=45, ha="right")
    plt.yticks(rotation=0)

    plt.tight_layout()
    plt.savefig(save_path, dpi=PLOT_STYLE["dpi"])
    plt.close()
    return save_path


def generate_all_visualizations(
    datasets: Dict[str, pd.DataFrame],
    demand_supply_df: Optional[pd.DataFrame] = None,
) -> List[Path]:
    """
    Executes and writes all 14 required analytical visualizations to reports/eda/figures/.
    """
    generated_figures: List[Path] = []

    # 1. Hotel cancellations by lead time
    if "hotel_bookings" in datasets:
        p1 = plot_hotel_cancellation_by_lead_time(datasets["hotel_bookings"])
        generated_figures.append(p1)

    # 2. Hotel ADR by market segment
    if "hotel_bookings" in datasets:
        p2 = plot_hotel_adr_by_market_segment(datasets["hotel_bookings"])
        generated_figures.append(p2)

    # 3. Flight price by days left
    if "flight_prices" in datasets:
        p3 = plot_flight_price_by_days_left(datasets["flight_prices"])
        generated_figures.append(p3)

    # 4. Flight price economy vs business
    if "flight_prices" in datasets:
        p4 = plot_flight_price_economy_vs_business(datasets["flight_prices"])
        generated_figures.append(p4)

    # 5. Flight delay causes breakdown
    if "flights" in datasets:
        p5 = plot_flight_delay_causes_breakdown(datasets["flights"])
        generated_figures.append(p5)

    # 6. Flight on-time by airline
    if "flights" in datasets:
        airlines = datasets.get("airlines", None)
        p6 = plot_flight_ontime_by_airline(datasets["flights"], airlines)
        generated_figures.append(p6)

    # 7. Customer search conversion funnel
    if "customer_search_events" in datasets:
        p7 = plot_customer_search_conversion_funnel(datasets["customer_search_events"])
        generated_figures.append(p7)

    # 8. Search demand by destination
    if "customer_search_events" in datasets:
        p8 = plot_search_demand_by_destination(datasets["customer_search_events"])
        generated_figures.append(p8)

    # 9. Inventory utilization distribution
    if "inventory_availability" in datasets:
        p9 = plot_inventory_utilization_distribution(datasets["inventory_availability"])
        generated_figures.append(p9)

    # 10. Supplier markup and margin
    if "supplier_offers" in datasets:
        p10 = plot_supplier_markup_and_margin_by_supplier(datasets["supplier_offers"])
        generated_figures.append(p10)

    # 11. Market seasonality index monthly
    if "market_seasonal_signals" in datasets:
        p11 = plot_market_seasonality_index_monthly(datasets["market_seasonal_signals"])
        generated_figures.append(p11)

    # 12. Cross-domain demand vs supply gap
    if demand_supply_df is not None:
        p12 = plot_cross_domain_demand_vs_supply_gap(demand_supply_df)
        generated_figures.append(p12)

    # 13. Correlation Heatmap - Hotel
    if "hotel_bookings" in datasets:
        hotel_cols = [
            "lead_time", "stays_in_weekend_nights", "stays_in_week_nights",
            "adults", "children", "adr", "is_canceled", "total_stay_nights",
            "previous_cancellations", "total_of_special_requests"
        ]
        p13 = plot_correlation_heatmap(
            datasets["hotel_bookings"],
            hotel_cols,
            "Hotel Bookings: Feature Correlation Heatmap (Pearson)",
            FIGURES_DIR / "correlation_heatmap_hotel.png",
        )
        generated_figures.append(p13)

    # 14. Correlation Heatmap - Flight Prices
    if "flight_prices" in datasets:
        price_cols = ["duration", "days_left", "price", "stops_count"]
        p14 = plot_correlation_heatmap(
            datasets["flight_prices"],
            price_cols,
            "Flight Prices: Feature Correlation Heatmap (Pearson)",
            FIGURES_DIR / "correlation_heatmap_flight_prices.png",
        )
        generated_figures.append(p14)

    return generated_figures

