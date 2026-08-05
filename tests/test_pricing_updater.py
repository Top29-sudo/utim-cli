import os
from unittest.mock import patch, MagicMock
import pytest
from utim_cli.server.models import MODEL_REGISTRY, ModelEntry
from utim_cli.server.pricing_updater import fetch_and_update_pricing, start_pricing_scheduler

def test_fetch_and_update_pricing_success():
    # Store original values for cleanup
    original_grok = MODEL_REGISTRY.get("x-ai/grok-4.5")
    
    # Temporarily insert/override test models in MODEL_REGISTRY
    MODEL_REGISTRY["x-ai/grok-4.5"] = ModelEntry(
        model_id="x-ai/grok-4.5",
        provider="openrouter",
        cost_input_per_1k=2.0,
        cost_output_per_1k=10.0,
        context_window=128_000,
        capabilities=["chat"],
        tags=["premium"]
    )
    
    MODEL_REGISTRY["aion-labs/aion-3.0"] = ModelEntry(
        model_id="aion-labs/aion-3.0",
        provider="openrouter",
        cost_input_per_1k=1.0,
        cost_output_per_1k=2.0,
        context_window=200_000,
        capabilities=["chat"],
        tags=["premium"]
    )

    MODEL_REGISTRY["free-model"] = ModelEntry(
        model_id="free-model",
        provider="openrouter",
        cost_input_per_1k=0.0,
        cost_output_per_1k=0.0,
        context_window=128_000,
        capabilities=["chat"],
        tags=["free"]
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {
                "id": "x-ai/grok-4.5",
                "pricing": {
                    "prompt": "0.0000025",      # $2.50 per 1M tokens
                    "completion": "0.0000095",  # $9.50 per 1M tokens
                }
            },
            {
                "id": "aion-labs/aion-3.0",
                "pricing": {
                    "prompt": "0.0000015",      # $1.50 per 1M tokens
                    "completion": "0.0000035",  # $3.50 per 1M tokens
                }
            },
            {
                "id": "free-model",
                "pricing": {
                    "prompt": "0.0000010",
                    "completion": "0.0000020"
                }
            }
        ]
    }

    try:
        with patch("requests.get", return_value=mock_response):
            success = fetch_and_update_pricing()
            assert success is True
            
            # Expected values: base * 1,000,000 * 1.05
            # For grok-4.5 input: 0.0000025 * 1,000,000 * 1.05 = 2.5 * 1.05 = 2.625
            # For grok-4.5 output: 0.0000095 * 1,000,000 * 1.05 = 9.5 * 1.05 = 9.975
            assert MODEL_REGISTRY["x-ai/grok-4.5"].cost_input_per_1k == pytest.approx(2.625)
            assert MODEL_REGISTRY["x-ai/grok-4.5"].cost_output_per_1k == pytest.approx(9.975)
            
            # For aion-3.0 input: 0.0000015 * 1_000_000 * 1.05 = 1.575
            # For aion-3.0 output: 0.0000035 * 1_000_000 * 1.05 = 3.675
            assert MODEL_REGISTRY["aion-labs/aion-3.0"].cost_input_per_1k == pytest.approx(1.575)
            assert MODEL_REGISTRY["aion-labs/aion-3.0"].cost_output_per_1k == pytest.approx(3.675)

            # For free-model: must remain 0.0 since free models are excluded
            assert MODEL_REGISTRY["free-model"].cost_input_per_1k == 0.0
            assert MODEL_REGISTRY["free-model"].cost_output_per_1k == 0.0
    finally:
        # Cleanup / restore original registry
        if original_grok:
            MODEL_REGISTRY["x-ai/grok-4.5"] = original_grok
        else:
            MODEL_REGISTRY.pop("x-ai/grok-4.5", None)
        MODEL_REGISTRY.pop("aion-labs/aion-3.0", None)
        MODEL_REGISTRY.pop("free-model", None)

def test_fetch_and_update_pricing_fail_preserves_old_prices():
    MODEL_REGISTRY["x-ai/grok-4.5"] = ModelEntry(
        model_id="x-ai/grok-4.5",
        provider="openrouter",
        cost_input_per_1k=2.0,
        cost_output_per_1k=10.0,
        context_window=128_000,
        capabilities=["chat"],
        tags=["premium"]
    )
    
    mock_response = MagicMock()
    mock_response.status_code = 500
    
    try:
        with patch("requests.get", return_value=mock_response):
            success = fetch_and_update_pricing()
            assert success is False
            # Pricing should remain unchanged
            assert MODEL_REGISTRY["x-ai/grok-4.5"].cost_input_per_1k == 2.0
            assert MODEL_REGISTRY["x-ai/grok-4.5"].cost_output_per_1k == 10.0
            
        with patch("requests.get", side_effect=Exception("Connection Timeout")):
            success = fetch_and_update_pricing()
            assert success is False
            # Pricing should remain unchanged
            assert MODEL_REGISTRY["x-ai/grok-4.5"].cost_input_per_1k == 2.0
            assert MODEL_REGISTRY["x-ai/grok-4.5"].cost_output_per_1k == 10.0
    finally:
        MODEL_REGISTRY.pop("x-ai/grok-4.5", None)

def test_start_pricing_scheduler_starts_thread():
    with patch("threading.Thread") as mock_thread_class:
        mock_thread_instance = MagicMock()
        mock_thread_class.return_value = mock_thread_instance
        
        start_pricing_scheduler()
        
        mock_thread_class.assert_called_once()
        # Verify daemon thread was started
        kwargs = mock_thread_class.call_args[1]
        assert kwargs.get("daemon") is True
        mock_thread_instance.start.assert_called_once()
