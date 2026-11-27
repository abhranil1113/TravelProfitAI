# TBO InventoryIQ – Feature-Level Target Leakage Audit Report
**Phase:** Phase 3 – Feature Engineering & Dataset Transformation  
**Status:** COMPLETE & AUDITED  
**Auditor:** Team Sabuj Sangha (Abhranil Pal & Arka Dyuti Bose)

---

## 1. Executive Summary & Leakage Policy

Target leakage occurs when features contain information that would not be available at prediction time, creating artificially inflated offline model metrics that fail catastrophically in live production.

This audit evaluates all candidate features against their prediction cutoff timestamps across all seven analytical domains.

- **Total Features Evaluated:** 234
- **Eligible Features Approved for Modeling:** 217
- **Quarantined / Post-Event Excluded Variables:** 20

---

## 2. Quarantined & Post-Event Features Summary

The following variables contain post-event outcome information, circular formula identities, or global target encodings and are **strictly excluded** from predictive feature matrices:

| Dataset Name | Quarantined Variable | Prediction Context | Leakage Risk | Rationale & Quarantine Action |
| :--- | :--- | :--- | :--- | :--- |
| `hotel_cancellation_features` | `reservation_status` | Pre-Arrival Booking Time | Critical Post-Event | Contains checkout / cancellation status recorded post-departure. Excluded from input features. |
| `hotel_cancellation_features` | `reservation_status_date` | Pre-Arrival Booking Time | Critical Post-Event | Date of cancellation/checkout action. Excluded from input features. |
| `hotel_cancellation_features` | `assigned_room_type` | Pre-Arrival Booking Time | Post-Booking Outcome | Operational room assigned at check-in / night audit; excluded from pre-booking model inputs. |
| `hotel_cancellation_features` | `room_type_changed` | Pre-Arrival Booking Time | Post-Booking Outcome | Derived from check-in assigned room type; excluded from pre-booking model inputs. |
| `hotel_cancellation_features` | `market_segment_historical_cancel_rate` | Pre-Arrival Booking Time | Global Target Leakage | Computed using full-dataset cancellation averages across train/val/test splits. Preserved as analytical reference; excluded from model inputs. |
| `hotel_cancellation_features` | `deposit_type_historical_cancel_rate` | Pre-Arrival Booking Time | Global Target Leakage | Computed using full-dataset cancellation averages across train/val/test splits. Preserved as analytical reference; excluded from model inputs. |
| `customer_demand_features` | `clicked` | Search Event Time | Post-Search Outcome | User interaction outcome after search presentation; quarantined for search volume forecasting. |
| `customer_demand_features` | `booking_completed` | Search Event Time | Post-Search Outcome | Transaction checkout conversion; quarantined for search volume forecasting. |
| `customer_demand_features` | `has_funnel_anomaly` | Search Event Time | Post-Search Outcome | Derived from post-search booking and click outcomes; quarantined for search volume forecasting. |
| `supplier_profitability_features` | `gross_margin_percentage` | Offer Procurement | Deterministic Metric | Deterministic formula from cost and selling price; maintained as business metric, not ML target predicted from inputs. |
| `flight_operations_features` | `ARRIVAL_DELAY`, `DEPARTURE_DELAY` | Pre-Departure Schedule | Post-Flight Outcome | Actual operational delay minutes recorded after landing. Excluded from pre-departure predictions. |

---

## 3. Complete Feature-by-Feature Leakage Audit Register

| dataset_name | feature_name | target_variable | prediction_context | leakage_risk | final_decision | rationale |
| --- | --- | --- | --- | --- | --- | --- |
| hotel_cancellation_features | is_canceled | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | lead_time_days | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | lead_time_bucket | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | lead_time_log | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | booking_date | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | arrival_year | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | arrival_month | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | arrival_day | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | arrival_day_of_week | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | arrival_week_of_year | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | arrival_quarter | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | arrival_is_weekend | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | arrival_is_peak_season | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | arrival_is_month_start | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | arrival_is_month_end | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | total_stay_nights | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | stays_in_weekend_nights | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | stays_in_week_nights | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | weekend_nights_ratio | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | weekday_nights_ratio | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | total_guests | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | adults | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | children | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | babies | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | is_solo_traveller | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | is_family_booking | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | is_repeated_guest | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | previous_cancellations | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | previous_bookings_not_canceled | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | has_cancellation_history | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | booking_changes | is_canceled | Booking Creation Time (Pre-Arrival) | Medium / Post-Booking Modification | Include with Caution | Modifications occur between booking creation and arrival; valid for dynamic monitoring but excluded from Day-0 transaction models. |
| hotel_cancellation_features | special_requests_count | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | has_special_requests | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | days_in_waiting_list | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | required_car_parking_spaces | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | has_agent | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | has_company | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | reserved_room_type | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | assigned_room_type | is_canceled | Booking Creation Time (Pre-Arrival) | Critical / Post-Booking Operational Outcome | Quarantined / Excluded | Operational room assignment occurs at check-in/night audit; unavailable at booking transaction time. |
| hotel_cancellation_features | room_type_changed | is_canceled | Booking Creation Time (Pre-Arrival) | Critical / Post-Booking Operational Outcome | Quarantined / Excluded | Operational room assignment occurs at check-in/night audit; unavailable at booking transaction time. |
| hotel_cancellation_features | adr | is_canceled | Booking Creation Time (Pre-Arrival) | Low | Include | Contracted rate agreed at booking time prior to check-in. |
| hotel_cancellation_features | adr_log | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | adr_per_guest | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | hotel | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | meal | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | country | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | market_segment | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | distribution_channel | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | deposit_type | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | customer_type | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | market_segment_historical_cancel_rate | is_canceled | Booking Creation Time (Pre-Arrival) | High / Global Target Leakage | Quarantined / Analytical Reference Only | Calculated using target averages from complete dataset across train/val/test splits. Preserved as analytical reference; excluded from model inputs. |
| hotel_cancellation_features | deposit_type_historical_cancel_rate | is_canceled | Booking Creation Time (Pre-Arrival) | High / Global Target Leakage | Quarantined / Analytical Reference Only | Calculated using target averages from complete dataset across train/val/test splits. Preserved as analytical reference; excluded from model inputs. |
| hotel_cancellation_features | currency | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| hotel_cancellation_features | arrival_date | is_canceled | Booking Creation Time (Pre-Arrival) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_price_features | price | price | Flight Search Quote Time (Pre-Departure) | Target Variable | Target Only | Supervised regression label; excluded from input feature matrix. |
| flight_price_features | price_log | price | Flight Search Quote Time (Pre-Departure) | Critical / Direct Target Transform | Quarantined / Excluded | Log transformation of target regression price; must never enter inputs. |
| flight_price_features | days_left | price | Flight Search Quote Time (Pre-Departure) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_price_features | days_left_bucket | price | Flight Search Quote Time (Pre-Departure) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_price_features | days_left_log | price | Flight Search Quote Time (Pre-Departure) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_price_features | is_immediate_departure | price | Flight Search Quote Time (Pre-Departure) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_price_features | duration_hours | price | Flight Search Quote Time (Pre-Departure) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_price_features | duration_minutes | price | Flight Search Quote Time (Pre-Departure) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_price_features | duration_bucket | price | Flight Search Quote Time (Pre-Departure) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_price_features | class | price | Flight Search Quote Time (Pre-Departure) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_price_features | is_business_class | price | Flight Search Quote Time (Pre-Departure) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_price_features | stops_count | price | Flight Search Quote Time (Pre-Departure) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_price_features | is_direct_flight | price | Flight Search Quote Time (Pre-Departure) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_price_features | airline | price | Flight Search Quote Time (Pre-Departure) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_price_features | source_city | price | Flight Search Quote Time (Pre-Departure) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_price_features | destination_city | price | Flight Search Quote Time (Pre-Departure) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_price_features | route | price | Flight Search Quote Time (Pre-Departure) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_price_features | departure_time | price | Flight Search Quote Time (Pre-Departure) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_price_features | arrival_time | price | Flight Search Quote Time (Pre-Departure) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_price_features | price_record_id | price | Flight Search Quote Time (Pre-Departure) | Metadata Identifier | Excluded Identifier | Synthetic surrogate identifier; excluded from model features. |
| flight_price_features | currency | price | Flight Search Quote Time (Pre-Departure) | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_operations_features | year | ARRIVAL_DELAY | Scheduled Flight Departure Time | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_operations_features | month | ARRIVAL_DELAY | Scheduled Flight Departure Time | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_operations_features | day | ARRIVAL_DELAY | Scheduled Flight Departure Time | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_operations_features | day_of_week | ARRIVAL_DELAY | Scheduled Flight Departure Time | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_operations_features | is_weekend_flight | ARRIVAL_DELAY | Scheduled Flight Departure Time | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_operations_features | scheduled_departure_hour | ARRIVAL_DELAY | Scheduled Flight Departure Time | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_operations_features | scheduled_departure_minute | ARRIVAL_DELAY | Scheduled Flight Departure Time | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_operations_features | scheduled_arrival_hour | ARRIVAL_DELAY | Scheduled Flight Departure Time | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_operations_features | scheduled_arrival_minute | ARRIVAL_DELAY | Scheduled Flight Departure Time | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_operations_features | scheduled_elapsed_time_minutes | ARRIVAL_DELAY | Scheduled Flight Departure Time | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_operations_features | flight_distance_miles | ARRIVAL_DELAY | Scheduled Flight Departure Time | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_operations_features | airline | ARRIVAL_DELAY | Scheduled Flight Departure Time | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_operations_features | flight_number | ARRIVAL_DELAY | Scheduled Flight Departure Time | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_operations_features | origin_airport | ARRIVAL_DELAY | Scheduled Flight Departure Time | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_operations_features | destination_airport | ARRIVAL_DELAY | Scheduled Flight Departure Time | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_operations_features | route | ARRIVAL_DELAY | Scheduled Flight Departure Time | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| flight_operations_features | is_cancelled | ARRIVAL_DELAY | Scheduled Flight Departure Time | Critical / Post-Flight Operational Outcome | Quarantined / Excluded | Observed only after scheduled flight departure/arrival; unavailable at booking/procurement time. |
| flight_operations_features | is_diverted | ARRIVAL_DELAY | Scheduled Flight Departure Time | Critical / Post-Flight Operational Outcome | Quarantined / Excluded | Observed only after scheduled flight departure/arrival; unavailable at booking/procurement time. |
| flight_operations_features | arrival_delay_minutes | ARRIVAL_DELAY | Scheduled Flight Departure Time | Critical / Post-Flight Operational Outcome | Quarantined / Excluded | Observed only after scheduled flight departure/arrival; unavailable at booking/procurement time. |
| flight_operations_features | departure_delay_minutes | ARRIVAL_DELAY | Scheduled Flight Departure Time | Critical / Post-Flight Operational Outcome | Quarantined / Excluded | Observed only after scheduled flight departure/arrival; unavailable at booking/procurement time. |
| flight_operations_features | is_ontime_arrival | ARRIVAL_DELAY | Scheduled Flight Departure Time | Critical / Post-Flight Operational Outcome | Quarantined / Excluded | Observed only after scheduled flight departure/arrival; unavailable at booking/procurement time. |
| flight_operations_features | unit | ARRIVAL_DELAY | Scheduled Flight Departure Time | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| customer_demand_features | search_id | search_volume | Prior Time-Window Horizon | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| customer_demand_features | user_id | search_volume | Prior Time-Window Horizon | None | Include | Feature observed prior to prediction cutoff; zero target information. |
| customer_demand_features | destination_id | search_volume | Prior Time-Window Horizon | None | Include | Feature observed prior to prediction cutoff; zero target information. |
