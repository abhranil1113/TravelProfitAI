"""
optimization/data/candidate_builder.py

Candidate opportunity builder orchestrating Stage 2 data preparation:
- Active offer loading & expiration filtering
- Point-in-time capacity resolution
- Currency validation
- Demand funnel calculations
- Machine learning inference
- Financial contribution calculation
"""

from typing import List, Dict, Any, Tuple, Optional
import pandas as pd
from optimization.config import OptimizationConfig
from optimization.schemas import ProcurementOpportunity, CandidateOffer
from optimization.data.loader import DatasetLoader
from optimization.data.point_in_time import PointInTimeResolver
from optimization.data.currency import CurrencyValidator
from optimization.data.demand import DemandService
from optimization.predictions.model_registry import ModelRegistry
from optimization.predictions.hotel_cancellation import HotelCancellationService
from optimization.predictions.flight_price import FlightPriceService
from optimization.predictions.demand_forecasting import DemandForecastingService
from optimization.economics.hotel_economics import HotelEconomicsCalculator
from optimization.economics.flight_economics import FlightEconomicsCalculator


class CandidateOpportunityBuilder:
    """End-to-end data preparation service producing candidate procurement opportunities."""

    _CANDIDATE_CACHE: Dict[Tuple[str, str, bool], Tuple[List[ProcurementOpportunity], List[CandidateOffer], Dict[str, Any]]] = {}

    def __init__(self, config: OptimizationConfig, loader: Optional[DatasetLoader] = None):
        self.config = config
        self.loader = loader or DatasetLoader()
        self.registry = ModelRegistry()

    def build_candidate_opportunities(self) -> Tuple[List[ProcurementOpportunity], List[CandidateOffer], Dict[str, Any]]:
        """
        Executes complete Stage 2 data preparation pipeline.
        Returns:
            Tuple of (opportunities, candidate_offers, audit_metadata)
        """
        cache_key = (
            str(self.config.optimization_timestamp),
            str(self.config.target_currency),
            bool(self.config.allow_prototype_currency_override),
        )
        if cache_key in self._CANDIDATE_CACHE:
            cached_opps, cached_cands, cached_meta = self._CANDIDATE_CACHE[cache_key]
            return list(cached_opps), [c.model_copy() for c in cached_cands], dict(cached_meta)
        # 1. Load raw datasets
        raw_offers = self.loader.load_supplier_offers()
        raw_inventory = self.loader.load_inventory_availability()
        raw_searches = self.loader.load_customer_searches()

        # 2. Currency Validation
        curr_validator = CurrencyValidator(self.config)
        validated_currency, currency_tier = curr_validator.validate_offers_currency(raw_offers)

        # 3. Point-in-Time Resolution
        pit_resolver = PointInTimeResolver(self.config.optimization_timestamp)
        active_offers, offer_audit = pit_resolver.filter_active_supplier_offers(raw_offers)
        resolved_inventory, inv_audit = pit_resolver.resolve_inventory_snapshots(raw_inventory)
        prior_searches = pit_resolver.filter_prior_search_events(raw_searches)

        # Build capacity lookup: (inventory_id, travel_date) -> point_in_time_capacity
        capacity_lookup = {}
        if not resolved_inventory.empty:
            for _, row in resolved_inventory.iterrows():
                key = (str(row["inventory_id"]), str(row["travel_date"]))
                capacity_lookup[key] = int(row.get("available_quantity", 0))

        # 4. Demand Preparation
        demand_service = DemandService(
            searches_prior_df=prior_searches,
            assumed_stay_duration=self.config.financial.hotel_assumed_stay_duration,
            demand_scenario_multiplier=self.config.financial.demand_scenario_multiplier,
            default_conversion_rate=self.config.financial.default_search_conversion_rate,
            default_travellers=self.config.financial.default_travellers_per_booking,
            default_rooms=self.config.financial.default_rooms_per_booking,
        )
        demand_forecast_service = DemandForecastingService(
            self.registry, self.config, raw_searches
        )

        # 5. Prediction & Economic Calculators
        hotel_cancel_service = HotelCancellationService(self.registry, self.config)
        flight_price_service = FlightPriceService(self.registry, self.config)
        
        hotel_econ_calc = HotelEconomicsCalculator(self.config.financial)
        flight_econ_calc = FlightEconomicsCalculator(
            self.config.financial,
            use_optional_salvage=self.config.use_flight_salvage_optional
        )

        opportunities: List[ProcurementOpportunity] = []
        candidates: List[CandidateOffer] = []
        
        # Track aggregate demand cache per (destination_id, inventory_type, travel_date)
        agg_demand_cache = {}

        for idx, (_, offer) in enumerate(active_offers.iterrows()):
            inv_type = str(offer["inventory_type"]).upper()
            inv_id = str(offer["inventory_id"])
            dest_id = str(offer["destination_id"])
            travel_date = str(offer["travel_date"])
            opp_id = f"OPP_{str(offer['offer_id'])}"

            # Point-in-time physical capacity
            pit_cap = capacity_lookup.get((inv_id, travel_date), int(offer["available_quantity"]))
            # Bounded capacity available to TBO under this offer
            effective_avail_qty = min(int(offer["available_quantity"]), pit_cap)

            # Demand bounds
            demand_key = (dest_id, inv_type, travel_date)
            if demand_key not in agg_demand_cache:
                pred_search_vol = demand_forecast_service.predict_future_search_volume(dest_id, inv_type)
                agg_demand = demand_service.get_aggregate_demand_bound(dest_id, inv_type, pred_search_vol)
                agg_demand_cache[demand_key] = (pred_search_vol, agg_demand)
            else:
                pred_search_vol, agg_demand = agg_demand_cache[demand_key]

            # Inferences & Economics
            offer_dict = offer.to_dict()
            if inv_type == "HOTEL":
                p_cancel = hotel_cancel_service.predict_cohort_cancellation_probability(offer_dict)
                econ = hotel_econ_calc.calculate_expected_contribution(
                    purchase_cost=float(offer["purchase_cost"]),
                    selling_price=float(offer["selling_price"]),
                    cancellation_prob=p_cancel,
                    is_supplier_refundable=bool(offer.get("refundable", False)),
                )
                sell_through = self.config.financial.hotel_base_sell_through
                pred_market_price = None
                unit_type = "ROOM_NIGHT"
            else:  # FLIGHT
                pred_market_price = flight_price_service.predict_market_ceiling_price(offer_dict)
                sell_through = flight_econ_calc.calculate_adjusted_sell_through(
                    contract_price=float(offer["selling_price"]),
                    market_ceiling_price=pred_market_price
                )
                econ = flight_econ_calc.calculate_expected_contribution(
                    purchase_cost=float(offer["purchase_cost"]),
                    contract_selling_price=float(offer["selling_price"]),
                    sell_through=sell_through
                )
                p_cancel = None
                unit_type = "SEAT"

            unit_contrib = float(econ["expected_net_contribution"])
            unit_revenue = float(econ["expected_gross_revenue"])

            opp = ProcurementOpportunity(
                opportunity_id=opp_id,
                offer_id=str(offer["offer_id"]),
                supplier_id=str(offer["supplier_id"]),
                inventory_type=inv_type,
                inventory_id=inv_id,
                origin_id=str(offer.get("origin_id")) if pd.notna(offer.get("origin_id")) else None,
                destination_id=dest_id,
                travel_date=travel_date,
                purchase_cost=float(offer["purchase_cost"]),
                selling_price=float(offer["selling_price"]),
                available_quantity=effective_avail_qty,
                minimum_purchase_qty=int(offer["minimum_purchase_qty"]),
                refundable=bool(offer.get("refundable", False)),
                offer_valid_until=str(offer["offer_valid_until"]),
                currency=validated_currency,
                unit_type=unit_type,
                point_in_time_capacity=pit_cap,
                predicted_cancellation_prob=p_cancel,
                predicted_market_price=pred_market_price,
                predicted_search_volume=pred_search_vol,
                sell_through_probability=sell_through,
                expected_unit_contribution=unit_contrib,
                expected_unit_revenue=unit_revenue,
                aggregate_demand_cap=agg_demand,
            )
            opportunities.append(opp)

            cand = CandidateOffer(
                index=idx,
                opportunity_id=opp_id,
                offer_id=str(offer["offer_id"]),
                supplier_id=str(offer["supplier_id"]),
                inventory_type=inv_type,
                inventory_id=inv_id,
                destination_id=dest_id,
                travel_date=travel_date,
                unit_cost=float(offer["purchase_cost"]),
                unit_selling_price=float(offer["selling_price"]),
                available_qty=effective_avail_qty,
                moq=int(offer["minimum_purchase_qty"]),
                unit_contribution=unit_contrib,
                unit_type=unit_type,
                aggregate_demand=agg_demand,
            )
            candidates.append(cand)

        audit_meta = {
            "run_id": self.config.run_id,
            "optimization_timestamp": self.config.optimization_timestamp,
            "currency": validated_currency,
            "currency_tier": currency_tier.value,
            "total_raw_offers": len(raw_offers),
            "active_offers_evaluated": len(active_offers),
            "expired_offers_filtered": offer_audit["expired_offers_dropped"],
            "resolved_inventory_count": inv_audit["unique_resolved_inventory_items"],
            "prior_searches_used": len(prior_searches),
            "opportunities_generated": len(opportunities),
            "flight_salvage_mode": "10% Optional" if self.config.use_flight_salvage_optional else "0% Baseline Spoilage",
        }
        self._CANDIDATE_CACHE[cache_key] = (list(opportunities), [c.model_copy() for c in candidates], dict(audit_meta))
        return opportunities, candidates, audit_meta
