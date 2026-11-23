"""
optimization/data/currency.py

Currency validation service enforcing three-tier semantics:
- VERIFIED_COMMERCIAL
- PROTOTYPE_ASSUMED
- MIXED_OR_UNKNOWN
"""

from typing import List, Set, Tuple
import pandas as pd
from optimization.exceptions import CurrencyMismatchError, UnverifiedCurrencyError
from optimization.config import CurrencyTier, OptimizationConfig


class CurrencyValidator:
    """Enforces strict currency consistency and prototype override controls."""

    # Set of currencies recognized as verified corporate bank settlements in production
    VERIFIED_PRODUCTION_CURRENCIES: Set[str] = {"EUR", "USD", "GBP"}

    def __init__(self, config: OptimizationConfig):
        self.config = config

    def validate_offers_currency(self, offers_df: pd.DataFrame) -> Tuple[str, CurrencyTier]:
        """
        Validates the currency across all supplier offers.
        
        Returns:
            Tuple of (validated_currency_code, CurrencyTier)
            
        Raises:
            CurrencyMismatchError if multiple/mixed currencies are found.
            UnverifiedCurrencyError if an unverified currency is used without prototype override.
        """
        if "currency" not in offers_df.columns:
            raise CurrencyMismatchError("Supplier offers dataset is missing mandatory 'currency' column.")

        unique_currencies = offers_df["currency"].dropna().unique().tolist()
        if not unique_currencies:
            raise CurrencyMismatchError("Supplier offers dataset contains no valid currency declarations.")

        if len(unique_currencies) > 1:
            raise CurrencyMismatchError(
                f"Mixed currencies detected in procurement offers: {unique_currencies}. "
                "The optimizer requires a single uniform currency."
            )

        currency = str(unique_currencies[0]).strip().upper()

        if self.config.target_currency and currency != self.config.target_currency.upper():
            raise CurrencyMismatchError(
                f"Offer currency '{currency}' does not match target configured currency '{self.config.target_currency}'."
            )

        if currency in self.VERIFIED_PRODUCTION_CURRENCIES:
            tier = CurrencyTier.VERIFIED_COMMERCIAL
        else:
            if not self.config.allow_prototype_currency_override:
                raise UnverifiedCurrencyError(
                    f"Currency '{currency}' is unverified in production. Production mode rejects unverified currencies. "
                    "Set allow_prototype_currency_override=True in OptimizationConfig to allow prototype testing."
                )
            tier = CurrencyTier.PROTOTYPE_ASSUMED

        return currency, tier
