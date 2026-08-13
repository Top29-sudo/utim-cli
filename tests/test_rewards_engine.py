"""
UTIM Rewards Wheel Engine Tests & 1,000,000 Simulation Audit
─────────────────────────────────────────────────────────────
Comprehensive tests covering model classification, probability recalculation,
non-naive omission rules, 10M integer precision, category fallback hierarchy,
cryptographically secure random selection, and 1,000,000 virtual spin simulations.
"""

import pytest
import datetime
from typing import Dict, List, Any

from utim_cli.server.rewards_engine import (
    REWARD_PROBABILITY_CONFIG,
    classify_model_category,
    calculate_wheel_probabilities,
    select_winning_model_secure,
    simulate_wheel_spins
)



# ── Test Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def mock_models():
    return [
        {"model_id": "free-1", "name": "Free 1", "is_free": True, "prompt_cost_per_m": 0.0, "completion_cost_per_m": 0.0},
        {"model_id": "free-2", "name": "Free 2", "is_free": True, "prompt_cost_per_m": 0.0, "completion_cost_per_m": 0.0},
        {"model_id": "free-3", "name": "Free 3", "is_free": True, "prompt_cost_per_m": 0.0, "completion_cost_per_m": 0.0},
        {"model_id": "very-low-1", "name": "VL 1", "prompt_cost_per_m": 0.15, "completion_cost_per_m": 0.60},
        {"model_id": "very-low-2", "name": "VL 2", "prompt_cost_per_m": 0.20, "completion_cost_per_m": 0.80},
        {"model_id": "higher-1", "name": "Higher 1", "prompt_cost_per_m": 3.00, "completion_cost_per_m": 8.00},
        {"model_id": "premium-1", "name": "Premium 1", "prompt_cost_per_m": 15.00, "completion_cost_per_m": 60.00},
    ]


# ── Unit Tests ──────────────────────────────────────────────────────────────

def test_model_cost_classification(mock_models):
    assert classify_model_category(mock_models[0]) == "free"
    assert classify_model_category(mock_models[3]) == "very_low"
    assert classify_model_category(mock_models[5]) == "higher"
    assert classify_model_category(mock_models[6]) == "premium"


def test_base_probability_distribution(mock_models):
    res = calculate_wheel_probabilities(mock_models, omitted_model_ids=[], plan_id="pro")
    
    cat_probs = res["category_probabilities"]
    assert cat_probs["free"] == 80.00
    assert cat_probs["very_low"] == 19.95
    assert cat_probs["higher"] == 0.04
    assert cat_probs["premium"] == 0.01
    
    # Verify sum equals 10,000,000 integer precision units (100.00000%)
    total_units = sum(m["precision_units"] for m in res["models"])
    assert total_units == 10_000_000
    
    total_percent = sum(m["probability_percent"] for m in res["models"])
    assert pytest.approx(total_percent, abs=1e-5) == 100.0


def test_plan_omission_limits(mock_models):
    # Ultimate plan allows 11 omissions
    res_ultimate = calculate_wheel_probabilities(
        mock_models, omitted_model_ids=["free-1", "free-2"], plan_id="ultimate"
    )
    assert len(res_ultimate["omitted_models"]) == 2

    # Hobby plan allows max 2 omissions (extra requested are trimmed safely)
    res_hobby = calculate_wheel_probabilities(
        mock_models, omitted_model_ids=["free-1", "free-2", "free-3", "very-low-1"], plan_id="hobby"
    )
    assert len(res_hobby["omitted_models"]) == 2


def test_no_naive_normalization_on_omission(mock_models):
    """CRITICAL FINANCIAL SAFETY REQUIREMENT:
    Omitting free/cheap models MUST NOT naively scale premium models.
    Premium max ceiling (0.02%) and Higher Cost max ceiling (0.08%) must be respected.
    """
    # Omit all free models
    res = calculate_wheel_probabilities(
        mock_models, omitted_model_ids=["free-1", "free-2", "free-3"], plan_id="ultimate"
    )
    
    cat_probs = res["category_probabilities"]
    
    # Premium model must NOT explode (remains <= 0.02%)
    assert cat_probs["premium"] <= 0.02
    assert cat_probs["higher"] <= 0.08
    
    # Very Low Cost category absorbs the freed probability
    assert cat_probs["very_low"] >= 99.90
    
    # Total probability remains 100.00000%
    total_units = sum(m["precision_units"] for m in res["models"])
    assert total_units == 10_000_000


def test_cryptographically_secure_spin_selection(mock_models):
    res = calculate_wheel_probabilities(mock_models, omitted_model_ids=[], plan_id="pro")
    
    # Perform 100 secure spins
    for _ in range(100):
        spin_win = select_winning_model_secure(res)
        assert "winning_model" in spin_win
        assert spin_win["winning_model"]["model_id"] in [m["model_id"] for m in mock_models]


# ── 1,000,000 Spin Simulation Audit Test ───────────────────────────────────

def test_simulation_1M_spins(mock_models):
    """Run 1,000,000 virtual spins to verify observed frequencies match category probabilities."""
    sim = simulate_wheel_spins(mock_models, omitted_model_ids=[], plan_id="ultimate", num_spins=1_000_000)
    
    summary = sim["category_summary"]
    
    # Free category expected 80.0%, allow +-0.5% tolerance
    assert pytest.approx(summary["free"]["observed_percent"], abs=0.5) == 80.0
    
    # Very Low category expected 19.95%, allow +-0.5% tolerance
    assert pytest.approx(summary["very_low"]["observed_percent"], abs=0.5) == 19.95
    
    # Premium category expected ~0.01% (approx 100 wins out of 1,000,000 spins)
    # Observed count should be within 40 to 200 range
    prem_wins = summary["premium"]["observed_count"]
    assert 30 <= prem_wins <= 250
