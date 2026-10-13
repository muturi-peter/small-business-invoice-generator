from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import os

import requests

from invoice_generator import SUPPORTED_CURRENCIES


class ExchangeRateError(Exception):
    """Raised when the exchange-rate provider cannot return usable rates."""


def fetch_exchange_rates(base_currency):
    """Fetch the provider's latest published rates for a supported base currency."""
    if base_currency not in SUPPORTED_CURRENCIES:
        raise ValueError(f"Unsupported currency: {base_currency}")

    params = {
        "base": base_currency,
        "currencies": ",".join(SUPPORTED_CURRENCIES),
    }
    api_key = os.environ.get("FXRATES_API_KEY")
    if api_key:
        params["api_key"] = api_key

    try:
        response = requests.get("https://api.fxratesapi.com/latest", params=params, timeout=10)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as error:
        raise ExchangeRateError("Exchange rates are temporarily unavailable.") from error

    if not isinstance(payload, dict):
        raise ExchangeRateError("The exchange-rate provider returned an invalid response.")
    rates = payload.get("rates")
    if payload.get("success") is not True or not isinstance(rates, dict):
        raise ExchangeRateError("The exchange-rate provider returned an invalid response.")

    return {
        "rates": rates,
        "updated_at": payload.get("date", "Unknown"),
    }


def convert_amount(amount, rate):
    """Convert an amount and round the result to two decimal places."""
    try:
        decimal_amount = Decimal(str(amount))
        decimal_rate = Decimal(str(rate))
    except InvalidOperation as error:
        raise ValueError("Amount and rate must be valid numbers.") from error

    if not decimal_amount.is_finite() or decimal_amount < 0:
        raise ValueError("Amount must be a finite, non-negative number.")
    if not decimal_rate.is_finite() or decimal_rate <= 0:
        raise ValueError("Exchange rate must be a finite, positive number.")

    return (decimal_amount * decimal_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)