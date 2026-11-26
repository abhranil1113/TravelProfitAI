"""
ml_engine/risk_prediction/flight_risk_model.py

Flight cancellation, spoilage, and salvage risk evaluation models.
Provides heuristic business-rule estimates for inventory salvage and seat spoilage.
Note: This is an analytical heuristic calculator, not a trained machine learning model.
"""

from typing import Dict, Any, Optional


class FlightRiskModel:
    """Evaluates flight seat spoilage risk and salvage contribution via calibrated business rules."""

    PREDICTION_TYPE = "HEURISTIC_RULE"

    def __init__(self, baseline_spoilage_rate: float = 0.15, optional_salvage_rate: float = 0.10):
        self.baseline_spoilage_rate = baseline_spoilage_rate
        self.optional_salvage_rate = optional_salvage_rate

    def calculate_spoilage_risk(self, available_qty: int, days_left: float) -> Dict[str, Any]:
        """
        Estimates spoilage probability based on departure lead time.
        Returns heuristic risk estimate.
        """
        risk_multiplier = 1.5 if days_left <= 3 else (1.2 if days_left <= 7 else 1.0)
        p_spoil = min(1.0, self.baseline_spoilage_rate * risk_multiplier)

        return {
            "prediction_type": self.PREDICTION_TYPE,
            "spoilage_probability": float(round(p_spoil, 4)),
            "salvage_recovery_rate": self.optional_salvage_rate,
            "estimated_spoilage_units": float(round(available_qty * p_spoil, 1)),
            "is_machine_learning_model": False,
        }
