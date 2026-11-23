| dataset_name | row_count | column_count | memory_mb | currency | columns |
| --- | --- | --- | --- | --- | --- |
| hotel_bookings | 119208 | 42 | 123.22 | EUR | 42 items [hotel, is_canceled, lead_time, ...] |
| flight_prices | 300153 | 16 | 212.28 | INR | 16 items [airline, flight, source_city, ...] |
| flights | 1000 | 33 | 0.63 | OPERATIONAL | 33 items [YEAR, MONTH, DAY, ...] |
| airlines | 14 | 2 | 0.0 | METADATA | [IATA_CODE, AIRLINE] |
| airports | 322 | 7 | 0.11 | METADATA | 7 items [IATA_CODE, AIRPORT, CITY, ...] |
| customer_search_events | 5000 | 16 | 2.62 | INR | 16 items [search_id, user_id, search_date, ...] |
| supplier_offers | 5000 | 18 | 2.88 | INR | 18 items [offer_id, supplier_id, inventory_type, ...] |
| inventory_availability | 5000 | 15 | 2.79 | OPERATIONAL | 15 items [snapshot_id, inventory_id, inventory_type, ...] |
| market_seasonal_signals | 5000 | 13 | 1.4 | INDEX | 13 items [signal_id, destination_id, travel_date, ...] |