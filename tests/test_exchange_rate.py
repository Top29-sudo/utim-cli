import os
from unittest.mock import patch, MagicMock
import pytest

from utim_cli.server.exchange_rate import ExchangeRateStore, start_exchange_rate_scheduler

def test_exchange_rate_store_get_rate():
    # Test fallback
    ExchangeRateStore.USD_TO_INR = 95.70
    assert ExchangeRateStore.get_rate() == 95.70

    # Test environment variable override
    with patch.dict(os.environ, {"USD_TO_INR_RATE": "101.50"}):
        assert ExchangeRateStore.get_rate() == 101.50

    # Test invalid env var fallback
    with patch.dict(os.environ, {"USD_TO_INR_RATE": "invalid_float"}):
        assert ExchangeRateStore.get_rate() == 95.70


def test_fetch_live_rate_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "rates": {
            "INR": 98.25
        }
    }

    with patch('requests.get', return_value=mock_response):
        rate = ExchangeRateStore.fetch_live_rate()
        assert rate == 98.25
        assert ExchangeRateStore.USD_TO_INR == 98.25


def test_fetch_live_rate_fallback():
    mock_response_fail = MagicMock()
    mock_response_fail.status_code = 500

    mock_response_success = MagicMock()
    mock_response_success.status_code = 200
    mock_response_success.json.return_value = {
        "rates": {
            "INR": 97.50
        }
    }

    # First requests.get fails, second succeeds
    with patch('requests.get', side_effect=[Exception("Frankfurter Down"), mock_response_success]):
        rate = ExchangeRateStore.fetch_live_rate()
        assert rate == 97.50
        assert ExchangeRateStore.USD_TO_INR == 97.50


def test_fetch_live_rate_all_fail():
    ExchangeRateStore.USD_TO_INR = 95.70
    with patch('requests.get', side_effect=Exception("API Down")):
        rate = ExchangeRateStore.fetch_live_rate()
        assert rate == 95.70  # Should retain previous rate
