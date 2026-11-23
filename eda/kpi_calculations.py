"""
TBO InventoryIQ - Core Business KPI Calculation Engine (Phase 2)
Implements all travel technology KPIs with safe zero-denominator handling,
cardinality constraints, and domain-specific financial calculations.
"""

from typing import Dict, Any, Optional
import pandas as pd
import numpy as np


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division preventing ZeroDivisionError and NaN outputs."""
    if denominator == 0 or pd.isna(denominator) or pd.isna(numerator):
        return default
    return float(numerator / denominator)


def compute_search_kpis(searches_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Computes Customer Demand & Funnel Conversion KPIs from search events.
    """
    total_searches = len(searches_df)
    if total_searches == 0:
        return {"total_searches": 0, "status": "empty_dataset"}

    total_clicks = int(searches_df["clicked"].sum())
    total_bookings = int(searches_df["booking_completed"].sum())

    search_to_click_pct = safe_divide(total_clicks, total_searches) * 100
    click_to_book_pct = safe_divide(total_bookings, total_clicks) * 100
    search_to_book_pct = safe_divide(total_bookings, total_searches) * 100

    prices = searches_df["search_price"].dropna()
    lead_days = (
        searches_df["search_lead_days"].dropna()
        if "search_lead_days" in searches_df.columns
        else pd.Series(dtype=float)
    )

    by_destination = searches_df.groupby("destination_id").agg(
        searches=("search_id", "count"),
        clicks=("clicked", "sum"),
        bookings=("booking_completed", "sum"),
        avg_price=("search_price", "mean"),
    ).reset_index()
    by_destination["conversion_pct"] = by_destination.apply(
        lambda r: safe_divide(r["bookings"], r["searches"]) * 100, axis=1
    )

    return {
        "total_searches": total_searches,
        "total_clicks": total_clicks,
        "total_bookings": total_bookings,
        "search_to_click_pct": round(search_to_click_pct, 2),
        "click_to_book_pct": round(click_to_book_pct, 2),
        "search_to_book_pct": round(search_to_book_pct, 2),
        "avg_search_price_inr": round(float(prices.mean()), 2) if not prices.empty else 0.0,
        "median_search_price_inr": round(float(prices.median()), 2) if not prices.empty else 0.0,
        "avg_lead_days": round(float(lead_days.mean()), 2) if not lead_days.empty else 0.0,
        "median_lead_days": round(float(lead_days.median()), 2) if not lead_days.empty else 0.0,
        "top_destinations_by_demand": by_destination.sort_values(by="searches", ascending=False).to_dict(orient="records"),
    }


def compute_inventory_kpis(
    inventory_df: pd.DataFrame,
    deduplicate_snapshots: bool = True,
) -> Dict[str, Any]:
    """
    Computes Inventory Utilization, Availability, and Stockout KPIs.
    Strictly handles multi-snapshot cardinality by aggregating over the latest snapshot date.
    """
    total_records = len(inventory_df)
    if total_records == 0:
        return {"total_inventory_records": 0, "status": "empty_dataset"}

    work_df = inventory_df.copy()
    if deduplicate_snapshots and "snapshot_date" in work_df.columns:
        # Sort by snapshot_date and take the latest snapshot per (inventory_id, travel_date)
        work_df = work_df.sort_values("snapshot_date").groupby(
            ["inventory_id", "travel_date"], as_index=False
        ).last()

    distinct_inventory_items = int(work_df["inventory_id"].nunique())
    total_capacity = float(work_df["total_capacity"].sum())
    total_booked = float(work_df["booked_quantity"].sum())
    total_available = float(work_df["available_quantity"].sum())

    overall_utilization_pct = safe_divide(total_booked, total_capacity) * 100
    sold_out_count = int(work_df["sold_out"].sum()) if "sold_out" in work_df.columns else int((work_df["available_quantity"] == 0).sum())
    stockout_frequency_pct = safe_divide(sold_out_count, len(work_df)) * 100

    by_type = work_df.groupby("inventory_type").agg(
        items=("inventory_id", "count"),
        capacity=("total_capacity", "sum"),
        booked=("booked_quantity", "sum"),
        available=("available_quantity", "sum"),
    ).reset_index()
    by_type["utilization_pct"] = by_type.apply(
        lambda r: round(safe_divide(r["booked"], r["capacity"]) * 100, 2), axis=1
    )

    return {
        "snapshot_handling": "latest_snapshot_deduplicated" if deduplicate_snapshots else "all_raw_snapshots",
        "distinct_inventory_items": distinct_inventory_items,
        "analyzed_inventory_rows": len(work_df),
        "total_capacity": total_capacity,
        "total_booked_units": total_booked,
        "total_available_units": total_available,
        "overall_utilization_rate_pct": round(overall_utilization_pct, 2),
        "stockout_frequency_pct": round(stockout_frequency_pct, 2),
        "sold_out_units_count": sold_out_count,
        "utilization_by_type": by_type.to_dict(orient="records"),
    }


def compute_supplier_kpis(supplier_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Computes Supplier Procurement Cost, Selling Price, and Margin KPIs in INR.
    """
    total_offers = len(supplier_df)
    if total_offers == 0:
        return {"total_offers": 0, "status": "empty_dataset"}

    cost = supplier_df["purchase_cost"].dropna()
    selling = supplier_df["selling_price"].dropna()
    margins = supplier_df["margin_percentage"].dropna() if "margin_percentage" in supplier_df.columns else ((selling - cost) / selling) * 100
    unit_margins = supplier_df["unit_margin"].dropna() if "unit_margin" in supplier_df.columns else (selling - cost)

    negative_margins = int((margins < 0).sum())
    negative_margin_pct = safe_divide(negative_margins, total_offers) * 100

    refundable_count = int((supplier_df["refundable"] == 1).sum()) if "refundable" in supplier_df.columns else 0
    refundable_pct = safe_divide(refundable_count, total_offers) * 100

    by_supplier = supplier_df.groupby("supplier_id").agg(
        offer_count=("offer_id", "count"),
        avg_cost=("purchase_cost", "mean"),
        avg_selling=("selling_price", "mean"),
        avg_margin_pct=("margin_percentage" if "margin_percentage" in supplier_df.columns else "purchase_cost", "mean"),
    ).reset_index()

    return {
        "currency": "INR",
        "total_offers": total_offers,
        "distinct_suppliers": int(supplier_df["supplier_id"].nunique()),
        "avg_purchase_cost_inr": round(float(cost.mean()), 2),
        "median_purchase_cost_inr": round(float(cost.median()), 2),
        "avg_selling_price_inr": round(float(selling.mean()), 2),
        "median_selling_price_inr": round(float(selling.median()), 2),
        "avg_unit_margin_inr": round(float(unit_margins.mean()), 2),
        "avg_margin_pct": round(float(margins.mean()), 2),
        "median_margin_pct": round(float(margins.median()), 2),
        "negative_margin_offers": negative_margins,
        "negative_margin_pct": round(negative_margin_pct, 2),
        "refundable_offers_pct": round(refundable_pct, 2),
        "supplier_breakdown": by_supplier.to_dict(orient="records"),
    }


def compute_hotel_kpis(hotel_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Computes Hotel Hospitality KPIs in EUR (cancellation rate, ADR, RevPAR proxy, lead times).
    """
    total_bookings = len(hotel_df)
    if total_bookings == 0:
        return {"total_bookings": 0, "status": "empty_dataset"}

    canceled_count = int(hotel_df["is_canceled"].sum())
    cancellation_rate_pct = safe_divide(canceled_count, total_bookings) * 100

    adr = hotel_df["adr"].dropna()
    avg_adr = float(adr.mean()) if not adr.empty else 0.0
    median_adr = float(adr.median()) if not adr.empty else 0.0

    # RevPAR proxy = ADR * Occupancy proxy. Using (1 - cancellation_rate) as the realized stay occupancy factor.
    revpar_proxy = avg_adr * (1.0 - (cancellation_rate_pct / 100.0))

    lead_time = hotel_df["lead_time"].dropna()
    repeat_guests = int((hotel_df["is_repeated_guest"] == 1).sum()) if "is_repeated_guest" in hotel_df.columns else 0
    repeat_guest_pct = safe_divide(repeat_guests, total_bookings) * 100

    stay_nights = hotel_df["total_stay_nights"].dropna() if "total_stay_nights" in hotel_df.columns else (hotel_df["stays_in_weekend_nights"] + hotel_df["stays_in_week_nights"])

    by_segment = hotel_df.groupby("market_segment").agg(
        bookings=("hotel", "count"),
        cancellations=("is_canceled", "sum"),
        avg_adr=("adr", "mean"),
    ).reset_index()
    by_segment["cancellation_rate_pct"] = by_segment.apply(
        lambda r: round(safe_divide(r["cancellations"], r["bookings"]) * 100, 2), axis=1
    )

    by_deposit = hotel_df.groupby("deposit_type").agg(
        bookings=("hotel", "count"),
        cancellations=("is_canceled", "sum"),
        avg_adr=("adr", "mean"),
    ).reset_index()
    by_deposit["cancellation_rate_pct"] = by_deposit.apply(
        lambda r: round(safe_divide(r["cancellations"], r["bookings"]) * 100, 2), axis=1
    )

    return {
        "currency": "EUR",
        "total_bookings": total_bookings,
        "canceled_bookings": canceled_count,
        "cancellation_rate_pct": round(cancellation_rate_pct, 2),
        "avg_adr_eur": round(avg_adr, 2),
        "median_adr_eur": round(median_adr, 2),
        "revpar_proxy_eur": round(revpar_proxy, 2),
        "avg_lead_time_days": round(float(lead_time.mean()), 2),
        "median_lead_time_days": round(float(lead_time.median()), 2),
        "avg_stay_nights": round(float(stay_nights.mean()), 2),
        "repeat_guest_pct": round(repeat_guest_pct, 2),
        "cancellation_by_market_segment": by_segment.to_dict(orient="records"),
        "cancellation_by_deposit_type": by_deposit.to_dict(orient="records"),
    }


def compute_flight_operations_kpis(flights_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Computes Airline & Airport Operational Reliability KPIs.
    """
    total_flights = len(flights_df)
    if total_flights == 0:
        return {"total_flights": 0, "status": "empty_dataset"}

    cancelled = int(flights_df["CANCELLED"].sum()) if "CANCELLED" in flights_df.columns else 0
    diverted = int(flights_df["DIVERTED"].sum()) if "DIVERTED" in flights_df.columns else 0
    cancellation_rate_pct = safe_divide(cancelled, total_flights) * 100
    diversion_rate_pct = safe_divide(diverted, total_flights) * 100

    arr_delay = flights_df["ARRIVAL_DELAY"].dropna()
    dep_delay = flights_df["DEPARTURE_DELAY"].dropna()

    # On-time is standard DOT definition: arrival delay <= 15 minutes among non-cancelled flights
    completed_flights = flights_df[flights_df["CANCELLED"] == 0] if "CANCELLED" in flights_df.columns else flights_df
    ontime_flights = (completed_flights["ARRIVAL_DELAY"] <= 15).sum()
    ontime_rate_pct = safe_divide(ontime_flights, len(completed_flights)) * 100

    delay_causes = {}
    for cause_col in ["AIR_SYSTEM_DELAY", "SECURITY_DELAY", "AIRLINE_DELAY", "LATE_AIRCRAFT_DELAY", "WEATHER_DELAY"]:
        if cause_col in flights_df.columns:
            delay_causes[cause_col] = round(float(flights_df[cause_col].fillna(0).mean()), 2)

    return {
        "unit": "Operational (Minutes / Miles)",
        "total_flights": total_flights,
        "cancelled_flights": cancelled,
        "cancellation_rate_pct": round(cancellation_rate_pct, 2),
        "diverted_flights": diverted,
        "diversion_rate_pct": round(diversion_rate_pct, 2),
        "ontime_arrival_rate_pct": round(ontime_rate_pct, 2),
        "avg_departure_delay_min": round(float(dep_delay.mean()), 2) if not dep_delay.empty else 0.0,
        "median_departure_delay_min": round(float(dep_delay.median()), 2) if not dep_delay.empty else 0.0,
        "avg_arrival_delay_min": round(float(arr_delay.mean()), 2) if not arr_delay.empty else 0.0,
        "median_arrival_delay_min": round(float(arr_delay.median()), 2) if not arr_delay.empty else 0.0,
        "delay_causes_avg_minutes": delay_causes,
    }


def compute_flight_price_kpis(prices_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Computes Flight Pricing and Dynamic Fare Yield KPIs in INR.
    """
    total_quotes = len(prices_df)
    if total_quotes == 0:
        return {"total_price_quotes": 0, "status": "empty_dataset"}

    prices = prices_df["price"].dropna()
    avg_price = float(prices.mean())
    median_price = float(prices.median())

    # Economy vs Business Class Comparison
    class_group = prices_df.groupby("class")["price"].agg(["count", "mean", "median"]).to_dict(orient="index")
    economy_avg = class_group.get("Economy", {}).get("mean", np.nan)
    business_avg = class_group.get("Business", {}).get("mean", np.nan)
    business_economy_ratio = safe_divide(business_avg, economy_avg)

    # Stops Comparison
    stops_group = prices_df.groupby("stops")["price"].agg(["count", "mean", "median"]).reset_index().to_dict(orient="records")

    # Correlation with days_left
    days_left_corr = float(prices_df["price"].corr(prices_df["days_left"])) if "days_left" in prices_df.columns else np.nan

    return {
        "currency": "INR",
        "total_price_quotes": total_quotes,
        "avg_price_inr": round(avg_price, 2),
        "median_price_inr": round(median_price, 2),
        "class_comparison": class_group,
        "business_to_economy_price_ratio": round(business_economy_ratio, 2),
        "stops_pricing": stops_group,
        "days_left_price_correlation": round(days_left_corr, 4),
    }
