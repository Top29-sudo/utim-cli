"""
UTIM Rewards Wheel Engine
─────────────────────────
Probability calculation, model classification, plan omission rules,
controlled non-naive redistribution, cryptographically secure weighted selection,
snapshot persistence, and spin simulation.
"""

import math
import re
import secrets
import time
import json
from typing import Dict, List, Tuple, Any, Optional

# ── Central Configuration ───────────────────────────────────────────────────

REWARD_PROBABILITY_CONFIG: Dict[str, Any] = {
    "categories": {
        "free": {
            "name": "Free Models",
            "base_prob": 80.00,
            "max_cost_per_m": 0.0,
            "max_ceiling": 99.90,
            "order": 1
        },
        "very_low": {
            "name": "Very Low Cost Models",
            "base_prob": 19.95,
            "max_cost_per_m": 1.00,  # < $1.00 per 1M tokens
            "max_ceiling": 99.90,
            "order": 2
        },
        "higher": {
            "name": "Higher Cost Models",
            "base_prob": 0.04,
            "max_cost_per_m": 10.00, # < $10.00 per 1M tokens
            "max_ceiling": 0.08,     # Strict safety ceiling
            "order": 3
        },
        "premium": {
            "name": "Premium / Jackpot Models",
            "base_prob": 0.01,
            "max_cost_per_m": float("inf"), # >= $10.00 per 1M tokens
            "max_ceiling": 0.02,    # Strict safety ceiling
            "order": 4
        }
    },
    "plan_omission_limits": {
        "free": 0,
        "hobby": 2,      # ₹700 / $7 -> remove up to 2 models
        "pro": 5,        # ₹2,500 / $25 -> remove up to 5 models
        "max": 8,        # ₹5,500 / $55 -> remove up to 8 models
        "ultimate": 11   # ₹11,000 / $110 -> remove up to 11 models
    },
    "total_precision_units": 10_000_000, # 10M integer units = 100.00000%
    "spins_per_cycle": 4,
    "reward_duration_seconds": 86400    # 24 hours
}


MODEL_CATEGORY_MAP: Dict[str, str] = {
    # --- FREE ---
    "cohere/north-mini-code:free": "free",
    "poolside/laguna-s-2.1:free": "free",
    "google/gemma-4-26b-a4b-it:free": "free",
    "google/gemma-4-31b-it:free": "free",
    "openai/gpt-oss-20b:free": "free",
    # --- VERY_LOW ---
    "deepseek/deepseek-v4-flash-0731": "very_low",
    "deepseek/deepseek-v4-flash": "very_low",
    "inclusionai/ling-2.6-flash:free": "very_low",
    "kwaipilot/kat-coder-air-v2.5": "very_low",
    "minimax/minimax-m2.5": "very_low",
    "nex-agi/nex-n2-mini": "very_low",
    "xiaomi/mimo-v2.5": "very_low",
    "deepseek/deepseek-v4-pro": "very_low",
    "inclusionai/ling-2.6-1t": "very_low",
    "deepseek/deepseek-r1": "very_low",
    "xiaomi/mimo-v2.5-pro": "very_low",
    "openai/gpt-5.6-luna": "very_low",
    "openai/gpt-5.6-luna-pro": "very_low",
    "qwen/qwen3-next-80b-a3b-instruct": "very_low",
    "xiaomi/mimo-v2-pro": "very_low",
    # --- HIGHER ---
    "muses/muse-spark-1.1:free": "higher",
    "thinkingmachines/inkling-small:free": "higher",
    "kwaipilot/kat-coder-pro-v2": "higher",
    "kwaipilot/kat-coder-pro-v2.5": "higher",
    "minimax/minimax-m3": "higher",
    "moonshot/kimi-k2.5": "higher",
    "openai/gpt-5.4-mini": "higher",
    "qwen/qwen3.6-plus": "higher",
    "qwen/qwen3.7-plus": "higher",
    "stepfun/step-3.7-flash": "higher",
    "z-ai/glm-4.7": "higher",
    "z-ai/glm-5": "higher",
    "z-ai/glm-5.2": "higher",
    "google/gemini-3.6-flash": "higher",
    "minimax/minimax-m2.7": "higher",
    "moonshot/kimi-k2.6": "higher",
    "moonshot/kimi-k2.7-code": "higher",
    "nex-agi/nex-n2-pro:free": "higher",
    "x-ai/grok-4.20": "higher",
    "x-ai/grok-4.3": "higher",
    "x-ai/grok-build-0.1": "higher",
    "z-ai/glm-5-turbo": "higher",
    "z-ai/glm-5.1": "higher",
    "google/gemini-3.5-flash": "higher",
    "qwen/qwen3.7-max": "higher",
    "openai/gpt-5.6-terra": "higher",
    "openai/gpt-5.6-terra-pro": "higher",
    "qwen/qwen3.8-max": "higher",
    "x-ai/grok-4.5": "higher",
    # --- PREMIUM ---
    "moonshot/kimi-k3": "premium",
    "anthropic/claude-sonnet-5": "premium",
    "google/gemini-3.1-pro-preview": "premium",
    "anthropic/claude-opus-4.5": "premium",
    "anthropic/claude-opus-4.6": "premium",
    "anthropic/claude-opus-4.7": "premium",
    "anthropic/claude-opus-4.8": "premium",
    "anthropic/claude-sonnet-4.5": "premium",
    "anthropic/claude-sonnet-4.6": "premium",
    "openai/gpt-5.4": "premium",
    "anthropic/claude-fable-5": "premium",
    "openai/gpt-5.3-codex": "premium",
    "openai/gpt-5.5": "premium",
    "anthropic/claude-opus-5": "premium",
    "google/gemini-3.1-pro-preview-customtools": "premium",
    "openai/gpt-5.6-sol": "premium",
    "openai/gpt-5.6-sol-pro": "premium",
}


def classify_model_category(model_data: Dict[str, Any]) -> str:
    """Classify model into free, very_low, higher, or premium category."""
    model_id = model_data.get("model_id", model_data.get("id", ""))
    if model_id in MODEL_CATEGORY_MAP:
        return MODEL_CATEGORY_MAP[model_id]
        
    cat = model_data.get("category")
    if cat in ("free", "very_low", "higher", "premium"):
        return cat
        
    is_free = model_data.get("is_free", False) or model_data.get("free", False)
    if is_free or model_id.endswith(":free"):
        return "free"
    
    prompt_cost = float(model_data.get("prompt_cost_per_m", model_data.get("input_cost_per_m", 0.0)))
    completion_cost = float(model_data.get("completion_cost_per_m", model_data.get("output_cost_per_m", 0.0)))
    if completion_cost <= 0.0:
        return "free"
    elif completion_cost < 1.00:
        return "very_low"
    elif completion_cost < 10.00:
        return "higher"
    else:
        return "premium"


# ── Probability Engine (Controlled Non-Naive Redistribution) ────────────────

def calculate_wheel_probabilities(
    all_models: List[Dict[str, Any]],
    omitted_model_ids: List[str],
    plan_id: str,
    config_override: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Calculate authoritative probability distribution after model omissions.
    
    CRITICAL FINANCIAL & SAFETY RULES:
    1. Omissions must NOT naively scale expensive models.
    2. Higher Cost and Premium categories are hard-capped by max_ceiling (0.08% and 0.02%).
    3. Any probability freed by omitting cheap/free models flows primarily to the next-cheapest
       surviving category (Very Low Cost if Free is empty).
    4. Probabilities sum to exactly 100.00000% using 10,000,000 integer precision units.
    """
    cfg = config_override or REWARD_PROBABILITY_CONFIG
    plan_limits = cfg["plan_omission_limits"]
    max_omits = plan_limits.get(plan_id.lower(), 0)
    
    # Clean & enforce omission limits
    # First filter to only model IDs that actually exist in the pool (prevents ghost entries counting toward quota)
    valid_model_ids = {m.get("model_id", m.get("id")) for m in all_models}
    valid_omitted = [mid for mid in omitted_model_ids if mid in valid_model_ids]
    # Then apply per-plan limit
    clean_omitted = set(valid_omitted[:max_omits])
    
    # Filter eligible models
    eligible_models = [m for m in all_models if m.get("model_id", m.get("id")) not in clean_omitted]
    
    if not eligible_models:
        # Fallback if literally everything was omitted
        eligible_models = all_models[:]
        clean_omitted = set()

    # Group eligible models by cost category
    category_models: Dict[str, List[Dict[str, Any]]] = {
        "free": [],
        "very_low": [],
        "higher": [],
        "premium": []
    }
    
    for m in eligible_models:
        cat = classify_model_category(m)
        category_models[cat].append(m)

    # Determine which categories have eligible models
    categories_cfg = cfg["categories"]
    base_probs = {c: categories_cfg[c]["base_prob"] for c in categories_cfg}
    max_ceilings = {c: categories_cfg[c]["max_ceiling"] for c in categories_cfg}

    # Step 1: Base category allocation
    allocated_probs: Dict[str, float] = {}
    
    # Start with base probabilities for non-empty categories
    for c in ["free", "very_low", "higher", "premium"]:
        if len(category_models[c]) > 0:
            allocated_probs[c] = base_probs[c]
        else:
            allocated_probs[c] = 0.0

    # Step 2: Handle empty categories (controlled downward/upward fallback)
    # Total missing probability from empty categories
    missing_prob = sum(base_probs[c] for c in categories_cfg if len(category_models[c]) == 0)

    if missing_prob > 0:
        # Priority order to absorb missing probability: free -> very_low -> higher -> premium
        for target_cat in ["free", "very_low", "higher", "premium"]:
            if len(category_models[target_cat]) > 0:
                # Target category absorbs the missing probability
                allocated_probs[target_cat] += missing_prob
                break

    # Step 3: Apply safety ceilings on expensive categories (Higher Cost & Premium)
    for c in ["higher", "premium"]:
        if allocated_probs[c] > max_ceilings[c]:
            excess = allocated_probs[c] - max_ceilings[c]
            allocated_probs[c] = max_ceilings[c]
            # Push excess to cheapest surviving category
            for cheap_cat in ["free", "very_low"]:
                if len(category_models[cheap_cat]) > 0:
                    allocated_probs[cheap_cat] += excess
                    break

    # Normalize category probabilities to 100.0% total
    total_cat_prob = sum(allocated_probs.values())
    if total_cat_prob > 0:
        for c in allocated_probs:
            allocated_probs[c] = (allocated_probs[c] / total_cat_prob) * 100.0

    # Step 4: Allocate category probability across individual models and convert to 10M integer units
    total_precision = cfg["total_precision_units"]
    model_probabilities: List[Dict[str, Any]] = []
    
    accumulated_units = 0
    
    for c in ["free", "very_low", "higher", "premium"]:
        models_in_cat = category_models[c]
        cat_prob = allocated_probs[c]
        
        if not models_in_cat or cat_prob <= 0:
            continue
            
        # Distribute category probability equally across models in this category
        per_model_prob = cat_prob / len(models_in_cat)
        
        for m in models_in_cat:
            m_id = m.get("model_id", m.get("id"))
            m_name = m.get("name", m_id)
            provider = m.get("provider", "OpenRouter")
            
            units = int(round((per_model_prob / 100.0) * total_precision))
            if units < 1:
                units = 1 # Guarantee non-zero range if model is eligible
            
            model_probabilities.append({
                "model_id": m_id,
                "name": m_name,
                "provider": provider,
                "category": c,
                "category_name": categories_cfg[c]["name"],
                "probability_percent": per_model_prob,
                "precision_units": units
            })
            accumulated_units += units

    # Step 5: Normalize integer units so sum equals exactly total_precision (10,000,000)
    if model_probabilities and accumulated_units != total_precision:
        diff = total_precision - accumulated_units
        # Adjust the model with the largest share (usually in free or very_low)
        model_probabilities.sort(key=lambda x: x["precision_units"], reverse=True)
        model_probabilities[0]["precision_units"] += diff

    # Recalculate exact float percent based on normalized integer units
    for mp in model_probabilities:
        mp["probability_percent"] = (mp["precision_units"] / total_precision) * 100.0

    # Sort output cleanly by category order then probability descending
    category_order = {"free": 1, "very_low": 2, "higher": 3, "premium": 4}
    model_probabilities.sort(key=lambda x: (category_order[x["category"]], -x["probability_percent"]))

    return {
        "plan_id": plan_id,
        "max_omissions": max_omits,
        "omitted_models": list(clean_omitted),
        "total_eligible_models": len(model_probabilities),
        "category_probabilities": {c: round(allocated_probs[c], 5) for c in allocated_probs},
        "models": model_probabilities,
        "total_precision_units": total_precision
    }


# ── Cryptographically Secure Weighted Selection ─────────────────────────────

def select_winning_model_secure(snapshot_distribution: Dict[str, Any]) -> Dict[str, Any]:
    """Perform cryptographically secure weighted random selection from snapshot distribution."""
    models = snapshot_distribution["models"]
    total_precision = snapshot_distribution.get("total_precision_units", 10_000_000)
    
    if not models:
        raise ValueError("Cannot perform wheel spin on empty model pool.")

    # Cryptographically secure random integer between 1 and total_precision
    winning_unit = secrets.SystemRandom().randint(1, total_precision)
    
    current_offset = 0
    for m in models:
        current_offset += m["precision_units"]
        if winning_unit <= current_offset:
            return {
                "winning_model": m,
                "winning_unit": winning_unit,
                "total_units": total_precision
            }
            
    # Fallback to last model if rounding edge case
    return {
        "winning_model": models[-1],
        "winning_unit": winning_unit,
        "total_units": total_precision
    }


# ── Simulation Engine for Automated Testing & Auditing ─────────────────────

def simulate_wheel_spins(
    all_models: List[Dict[str, Any]],
    omitted_model_ids: List[str],
    plan_id: str,
    num_spins: int = 100_000
) -> Dict[str, Any]:
    """Simulate N virtual spins to empirically verify probability distribution & safety bounds."""
    dist = calculate_wheel_probabilities(all_models, omitted_model_ids, plan_id)
    models = dist["models"]
    
    counts: Dict[str, int] = {m["model_id"]: 0 for m in models}
    cat_counts: Dict[str, int] = {"free": 0, "very_low": 0, "higher": 0, "premium": 0}
    
    start_time = time.time()
    
    for _ in range(num_spins):
        res = select_winning_model_secure(dist)
        won = res["winning_model"]
        counts[won["model_id"]] += 1
        cat_counts[won["category"]] += 1
        
    elapsed = time.time() - start_time
    
    observed_results = []
    for m in models:
        m_id = m["model_id"]
        obs_count = counts[m_id]
        obs_percent = (obs_count / num_spins) * 100.0
        exp_percent = m["probability_percent"]
        observed_results.append({
            "model_id": m_id,
            "name": m["name"],
            "category": m["category"],
            "expected_percent": round(exp_percent, 5),
            "observed_percent": round(obs_percent, 5),
            "observed_count": obs_count,
            "delta_percent": round(obs_percent - exp_percent, 5)
        })
        
    observed_categories = {
        cat: {
            "expected_percent": dist["category_probabilities"].get(cat, 0.0),
            "observed_percent": round((cat_counts[cat] / num_spins) * 100.0, 5),
            "observed_count": cat_counts[cat]
        }
        for cat in cat_counts
    }
    
    return {
        "num_spins": num_spins,
        "elapsed_seconds": round(elapsed, 3),
        "plan_id": plan_id,
        "category_summary": observed_categories,
        "model_summary": observed_results
    }
