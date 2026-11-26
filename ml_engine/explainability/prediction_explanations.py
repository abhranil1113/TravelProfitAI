"""
ml_engine/explainability/prediction_explanations.py

Local prediction driver explanation and attribution.
Translates domain observations into human-readable business factors.

Note: These explanations represent analytical business-rule summaries and
expert-curated factors, NOT mathematical model feature attributions (e.g. SHAP or TreeSHAP).
"""

from typing import Dict, Any, List, Optional


class PredictionExplainer:
    """
    Generates localized business factor explanations for individual inference results.
    Explicitly tags results as HEURISTIC_RULE to distinguish from ML attribution.
    """

    EXPLANATION_TYPE = "HEURISTIC_RULE"

    @staticmethod
    def explain_hotel_cancellation(
        probability: float,
        features: Dict[str, Any],
        threshold: float = 0.25
    ) -> Dict[str, Any]:
        """
        Identifies key risk factors driving hotel cancellation probability.
        """
        lead_time = float(features.get("lead_time_days", features.get("lead_time", 0)))
        deposit_type = str(features.get("deposit_type", "No Deposit"))
        prev_cancels = float(features.get("previous_cancellations", 0))

        drivers = []
        if lead_time > 90:
            drivers.append(f"Long booking lead time ({int(lead_time)} days) increases cancellation likelihood.")
        elif lead_time <= 7:
            drivers.append(f"Short booking lead time ({int(lead_time)} days) strongly reduces cancellation risk.")

        if deposit_type.lower() == "non refund":
            drivers.append("Non-refundable deposit historically exhibits high cancellation dispute rates.")

        if prev_cancels > 0:
            drivers.append(f"Guest profile has {int(prev_cancels)} prior cancellations on record.")

        verdict = "HIGH_RISK" if probability >= threshold else "LOW_RISK"
        return {
            "explanation_type": PredictionExplainer.EXPLANATION_TYPE,
            "is_model_attribution": False,
            "prediction_probability": round(probability, 4),
            "risk_verdict": verdict,
            "threshold_applied": threshold,
            "primary_drivers": drivers,
        }

    @staticmethod
    def explain_flight_price(
        predicted_price: float,
        features: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Explains flight market ceiling price drivers.
        """
        days_left = float(features.get("days_left", 30))
        cabin_class = str(features.get("class", "Economy"))
        route = str(features.get("route", "Delhi-Mumbai"))

        drivers = []
        if days_left <= 2:
            drivers.append(f"Immediate departure urgency ({int(days_left)} days left) inflates market price.")
        elif days_left >= 30:
            drivers.append(f"Early purchase horizon ({int(days_left)} days left) benefits from advance pricing.")

        if cabin_class.lower() in ("business", "first"):
            drivers.append(f"Premium cabin tier ({cabin_class}) contributes to high contract ceiling.")

        return {
            "explanation_type": PredictionExplainer.EXPLANATION_TYPE,
            "is_model_attribution": False,
            "predicted_price_inr": round(predicted_price, 2),
            "route": route,
            "cabin_class": cabin_class,
            "pricing_drivers": drivers,
        }
