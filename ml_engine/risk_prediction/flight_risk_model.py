"""
ml_engine/risk_prediction/flight_risk_model.py

Flight cancellation, spoilage, and salvage risk evaluation models.
"""

from typing import Dict, Any, Optional


class FlightRiskModel:
    """Evaluates flight seat spoilage risk and salvage contribution."""

    def __init__(self, baseline_spoilage_rate: float = 0.15, optional_salvage_rate: float = 0.10):
        self.baseline_spoilage_rate = baseline_spoilage_rate
        self.optional_salvage_rate = optional_salvage_rate

    def calculate_spoilage_risk(self, available_qty: int, days_left: float) -> Dict[str, float]:
        """
        Estimates spoilage probability based on departure lead time.
        """
        risk_multiplier = 1.5 if days_left <= 3 else (1.2 if days_left <= 7 else 1.0)
        p_spoil = min(1.0, self.baseline_spoilage_rate * risk_multiplier)

        return {
            "spoilage_probability": float(round(p_spoil, 4)),
            "salvage_recovery_rate": self.optional_salvage_rate,
            "estimated_spoilage_units": float(round(available_qty * p_spoil, 1)),
        }
