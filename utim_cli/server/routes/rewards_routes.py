"""
UTIM Rewards Wheel API Routes
─────────────────────────────
FastAPI endpoints for Rewards Wheel status, omission preview, snapshot confirmation,
cryptographically secure server-authoritative spins, 24h reward activation,
and probability simulation.
"""

import datetime
import json
from typing import Dict, List, Tuple, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Body
from pydantic import BaseModel, Field

from ..auth import get_current_user, get_optional_firebase_user
from ..db import (
    SessionLocal, User, UserSubscription, Plan,
    RewardSnapshot, RewardSpin, RewardActivation, UserSpinCycle
)
from ..models import list_models
from ..rewards_engine import (
    REWARD_PROBABILITY_CONFIG,
    classify_model_category,
    calculate_wheel_probabilities,
    select_winning_model_secure,
    simulate_wheel_spins
)

def _format_model_name(model_id: str) -> str:
    parts = model_id.split("/")
    if len(parts) == 2:
        prov_raw, name_raw = parts[0], parts[1]
    else:
        prov_raw, name_raw = "UTIM", model_id
        
    prov_map = {
        "anthropic": "Anthropic",
        "openai": "OpenAI",
        "google": "Google",
        "deepseek": "DeepSeek",
        "meta-llama": "Meta Llama",
        "mistralai": "Mistral",
        "cohere": "Cohere",
        "qwen": "Qwen",
        "nvidia": "Nvidia",
        "amazon": "Amazon",
        "x-ai": "xAI",
        "inclusionai": "InclusionAI",
        "poolside": "Poolside",
        "nex-agi": "Nex-AGI"
    }
    prov = prov_map.get(prov_raw.lower(), prov_raw.replace("-", " ").title())
    
    clean_name = name_raw.replace(":free", " (Free)").replace("-", " ").replace("_", " ").title()
    clean_name = clean_name.replace("Gpt ", "GPT-").replace("Claude ", "Claude ")
    return f"{prov} {clean_name}"


AUTHORITATIVE_66_MODEL_IDS = [
    # --- FREE ---
    "cohere/north-mini-code:free",
    "poolside/laguna-s-2.1:free",
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
    "openai/gpt-oss-20b:free",
    # --- VERY_LOW ---
    "deepseek/deepseek-v4-flash-0731",
    "deepseek/deepseek-v4-flash",
    "inclusionai/ling-2.6-flash:free",
    "kwaipilot/kat-coder-air-v2.5",
    "minimax/minimax-m2.5",
    "nex-agi/nex-n2-mini",
    "xiaomi/mimo-v2.5",
    "deepseek/deepseek-v4-pro",
    "inclusionai/ling-2.6-1t",
    "deepseek/deepseek-r1",
    "xiaomi/mimo-v2.5-pro",
    "openai/gpt-5.6-luna",
    "openai/gpt-5.6-luna-pro",
    "qwen/qwen3-next-80b-a3b-instruct",
    "xiaomi/mimo-v2-pro",
    # --- HIGHER ---
    "muses/muse-spark-1.1:free",
    "thinkingmachines/inkling-small:free",
    "kwaipilot/kat-coder-pro-v2",
    "kwaipilot/kat-coder-pro-v2.5",
    "minimax/minimax-m3",
    "moonshot/kimi-k2.5",
    "openai/gpt-5.4-mini",
    "qwen/qwen3.6-plus",
    "qwen/qwen3.7-plus",
    "stepfun/step-3.7-flash",
    "z-ai/glm-4.7",
    "z-ai/glm-5",
    "z-ai/glm-5.2",
    "google/gemini-3.6-flash",
    "minimax/minimax-m2.7",
    "moonshot/kimi-k2.6",
    "moonshot/kimi-k2.7-code",
    "nex-agi/nex-n2-pro:free",
    "x-ai/grok-4.20",
    "x-ai/grok-4.3",
    "x-ai/grok-build-0.1",
    "z-ai/glm-5-turbo",
    "z-ai/glm-5.1",
    "google/gemini-3.5-flash",
    "qwen/qwen3.7-max",
    "openai/gpt-5.6-terra",
    "openai/gpt-5.6-terra-pro",
    "qwen/qwen3.8-max",
    "x-ai/grok-4.5",
    # --- PREMIUM ---
    "moonshot/kimi-k3",
    "anthropic/claude-sonnet-5",
    "google/gemini-3.1-pro-preview",
    "anthropic/claude-opus-4.5",
    "anthropic/claude-opus-4.6",
    "anthropic/claude-opus-4.7",
    "anthropic/claude-opus-4.8",
    "anthropic/claude-sonnet-4.5",
    "anthropic/claude-sonnet-4.6",
    "openai/gpt-5.4",
    "anthropic/claude-fable-5",
    "openai/gpt-5.3-codex",
    "openai/gpt-5.5",
    "anthropic/claude-opus-5",
    "google/gemini-3.1-pro-preview-customtools",
    "openai/gpt-5.6-sol",
    "openai/gpt-5.6-sol-pro",
]


def _get_models_list_dict(max_count: int = 66) -> List[Dict[str, Any]]:
    """Dynamically fetch the official 66 main agent models from utimmodel.txt and server model registry.
    Any new model added to utimmodel.txt will automatically be included!
    """
    all_models = list_models()
    models_by_id = {m.model_id: m for m in all_models}
    
    # Priority order starts with AUTHORITATIVE_66_MODEL_IDS, then appends any new models registered in DB
    model_ids = list(AUTHORITATIVE_66_MODEL_IDS)
    registered_ids = set(model_ids)
    
    image_keywords = ['image', 'imagine', 'dall-e', 'flux', 'midjourney', 'stable-diffusion']
    
    for m in all_models:
        mid = m.model_id
        if mid not in registered_ids:
            caps = getattr(m, 'capabilities', [])
            if 'image_generation' in caps and not ('chat' in caps or 'coding' in caps):
                continue
            if any(k in mid.lower() for k in image_keywords):
                continue
            model_ids.append(mid)
            registered_ids.add(mid)
            
    res = []
    for mid in model_ids[:max_count]:
        m = models_by_id.get(mid)
        provider = getattr(m, "provider", "OpenRouter") if m else "OpenRouter"
        p_cost = getattr(m, "cost_input_per_1k", 0.0) * 1000.0 if m else 0.0
        c_cost = getattr(m, "cost_output_per_1k", 0.0) * 1000.0 if m else 0.0
        is_free = mid.endswith(":free") or (m and "free" in getattr(m, "tags", []))
        
        res.append({
            "model_id": mid,
            "name": _format_model_name(mid),
            "provider": provider,
            "prompt_cost_per_m": p_cost,
            "completion_cost_per_m": c_cost,
            "is_free": is_free
        })
    return res

router = APIRouter(prefix="/api/rewards", tags=["Rewards Wheel"])


# ── Models / Schemas ────────────────────────────────────────────────────────

class PreviewOmissionsRequest(BaseModel):
    omitted_models: List[str] = Field(default_factory=list)

class ConfirmSnapshotRequest(BaseModel):
    omitted_models: List[str] = Field(default_factory=list)

class SimulateSpinsRequest(BaseModel):
    num_spins: int = Field(default=100000, ge=10, le=1000000)
    omitted_models: List[str] = Field(default_factory=list)


# ── Helper Utilities ────────────────────────────────────────────────────────

def _get_user_plan_id(db: Any, user_id: str) -> Tuple[str, str]:
    """Get active plan ID and plan name for a user."""
    sub = db.query(UserSubscription).filter(UserSubscription.user_id == user_id).first()
    if not sub or not sub.plan:
        return "free", "Free Plan"
    plan = db.query(Plan).filter(Plan.id == sub.plan_id).first() if hasattr(sub, "plan_id") else None
    plan_name = plan.name.lower() if plan else (sub.plan.name.lower() if hasattr(sub.plan, "name") else "free")
    return plan_name, getattr(sub.plan, "display_name", "Free Plan")


def _get_or_create_spin_cycle(db: Any, user_id: str) -> UserSpinCycle:
    """Get or initialize the current billing spin cycle for a user."""
    now = datetime.datetime.utcnow()
    cycle = db.query(UserSpinCycle).filter(
        UserSpinCycle.user_id == user_id,
        UserSpinCycle.cycle_start <= now,
        UserSpinCycle.cycle_end >= now
    ).order_by(UserSpinCycle.created_at.desc()).first()

    # Determine correct spins and duration based on plan
    plan_id, _ = _get_user_plan_id(db, user_id)
    if plan_id in ["hobby", "pro", "max", "ultimate"] or user_id == "guest":
        correct_spins = 4
        duration_days = 30
    else:
        correct_spins = 0
        duration_days = 30

    if not cycle:
        cycle_end = now + datetime.timedelta(days=duration_days)
        cycle = UserSpinCycle(
            user_id=user_id,
            cycle_start=now,
            cycle_end=cycle_end,
            spins_granted=correct_spins,
            spins_used=0
        )
        db.add(cycle)
        db.commit()
        db.refresh(cycle)
    else:
        # Dynamically grant correct spins to existing users if they are on a legacy cycle
        if cycle.spins_granted != correct_spins:
            cycle.spins_granted = correct_spins
            # If migrating from 7-day to 30-day (or upgrading from free), extend the cycle window
            if correct_spins in [4, 0] and (cycle.cycle_end - cycle.cycle_start).days < 15:
                cycle.cycle_end = cycle.cycle_start + datetime.timedelta(days=30)
            db.commit()
            db.refresh(cycle)

    return cycle


def _get_active_reward(db: Any, user_id: str) -> Optional[Dict[str, Any]]:
    """Check if the user currently has an active 24-hour reward."""
    now = datetime.datetime.utcnow()
    act = db.query(RewardActivation).filter(
        RewardActivation.user_id == user_id,
        RewardActivation.is_active == True,
        RewardActivation.reward_start <= now,
        RewardActivation.reward_end > now
    ).order_by(RewardActivation.reward_end.desc()).first()

    if not act:
        return None

    time_remaining = int((act.reward_end - now).total_seconds())
    all_models_dict = _get_models_list_dict()
    model_info = next((m for m in all_models_dict if m.get("model_id") == act.model_id or m.get("id") == act.model_id), None)
    model_name = model_info.get("name", act.model_id) if model_info else act.model_id

    return {
        "activation_id": act.id,
        "model_id": act.model_id,
        "model_name": model_name,
        "reward_start": act.reward_start.isoformat(),
        "reward_end": act.reward_end.isoformat(),
        "time_remaining_seconds": max(0, time_remaining),
        "is_active": True
    }


# ── API Endpoints ───────────────────────────────────────────────────────────

@router.get("/status")
def get_rewards_status(current_user: Optional[User] = Depends(get_optional_firebase_user)):
    """Retrieve full Rewards Wheel status, spin allowance, active 24h reward, and probabilities."""
    db = SessionLocal()
    snapshot = None
    try:
        user_id = current_user.id if current_user else "guest"
        user_email = current_user.email if current_user else "guest@utim.ai"

        plan_id, plan_display = _get_user_plan_id(db, user_id)
        is_paid = plan_id in ["hobby", "pro", "max", "ultimate"]
        max_omissions = REWARD_PROBABILITY_CONFIG["plan_omission_limits"].get(plan_id, 0)
        
        cycle = _get_or_create_spin_cycle(db, user_id)
        active_reward = _get_active_reward(db, user_id)
        
        # Get user's latest snapshot or default
        snapshot = db.query(RewardSnapshot).filter(
            RewardSnapshot.user_id == user_id,
            RewardSnapshot.status == "AVAILABLE"
        ).order_by(RewardSnapshot.created_at.desc()).first()

        omitted_ids = json.loads(snapshot.omitted_models_json) if snapshot else []
        user_id_str = user_id
        user_email_str = user_email
        spins_granted = cycle.spins_granted if is_paid else 0
        spins_used = cycle.spins_used if is_paid else 0
        spins_remaining = max(0, cycle.spins_granted - cycle.spins_used) if is_paid else 0
        cycle_end = cycle.cycle_end.isoformat() if is_paid else None
        
        all_models = _get_models_list_dict()
        # Calculate current probability table
        prob_dist = calculate_wheel_probabilities(all_models, omitted_ids, plan_id)

        # Build list of all available models with category labels for omission UI
        all_models_list = []
        for m in all_models:
            m_id = m.get("model_id", m.get("id"))
            m_name = m.get("name", m_id)
            cat = classify_model_category(m)
            cat_name = REWARD_PROBABILITY_CONFIG["categories"][cat]["name"]
            all_models_list.append({
                "model_id": m_id,
                "name": m_name,
                "provider": m.get("provider", "OpenRouter"),
                "category": cat,
                "category_name": cat_name,
                "is_omitted": m_id in prob_dist["omitted_models"]
            })

        return {
            "user_id": user_id_str,
            "email": user_email_str,
            "plan_id": plan_id,
            "plan_display_name": plan_display,
            "is_paid_plan": is_paid,
            "spins_granted": spins_granted,
            "spins_used": spins_used,
            "spins_remaining": spins_remaining,
            "cycle_end": cycle_end,
            "max_omissions_allowed": max_omissions,
            "active_reward": active_reward,
            "current_omissions": prob_dist["omitted_models"],
            "probabilities": prob_dist,
            "all_models": all_models_list,
            "snapshot_id": snapshot.id if snapshot else None
        }
    finally:
        db.close()


@router.post("/preview-omissions")
def preview_omissions(
    req: PreviewOmissionsRequest,
    current_user: User = Depends(get_current_user)
):
    """Preview updated model probability distribution for a given set of omitted models."""
    db = SessionLocal()
    try:
        plan_id, _ = _get_user_plan_id(db, current_user.id)
        if plan_id not in ["hobby", "pro", "max", "ultimate"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The UTIM Rewards Wheel is available exclusively for paid plan subscribers."
            )

        prob_dist = calculate_wheel_probabilities(_get_models_list_dict(), req.omitted_models, plan_id)
        return prob_dist
    finally:
        db.close()


@router.post("/confirm-snapshot")
def confirm_snapshot(
    req: ConfirmSnapshotRequest,
    current_user: Optional[User] = Depends(get_optional_firebase_user)
):
    """Confirm omission selection and save an immutable probability snapshot before spinning."""
    db = SessionLocal()
    try:
        user_id = current_user.id if current_user else "guest"
        plan_id, _ = _get_user_plan_id(db, user_id)
        if plan_id not in ["hobby", "pro", "max", "ultimate"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The UTIM Rewards Wheel is available exclusively for paid plan subscribers."
            )

        prob_dist = calculate_wheel_probabilities(_get_models_list_dict(), req.omitted_models, plan_id)
        
        # Invalidate old AVAILABLE snapshots
        db.query(RewardSnapshot).filter(
            RewardSnapshot.user_id == user_id,
            RewardSnapshot.status == "AVAILABLE"
        ).update({"status": "CANCELLED"})

        # Save new immutable snapshot
        snapshot = RewardSnapshot(
            user_id=user_id,
            plan_id=plan_id,
            omitted_models_json=json.dumps(prob_dist["omitted_models"]),
            category_probs_json=json.dumps(prob_dist["category_probabilities"]),
            model_probs_json=json.dumps(prob_dist["models"]),
            status="AVAILABLE"
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)

        return {
            "message": "Immutable probability snapshot confirmed.",
            "snapshot_id": snapshot.id,
            "probabilities": prob_dist
        }
    finally:
        db.close()


@router.post("/spin")
def perform_reward_spin(current_user: Optional[User] = Depends(get_optional_firebase_user)):
    """Perform a server-authoritative, cryptographically secure weighted wheel spin.
    
    1. Checks paid plan entitlement & monthly spin cycle allowance.
    2. Atomically locks & completes the user's probability snapshot.
    3. Performs cryptographically secure random weighted selection (secrets.SystemRandom).
    4. Activates the won model for 24 hours without consuming normal quota.
    """
    db = SessionLocal()
    try:
        user_id = current_user.id if current_user else "guest"
        plan_id, plan_display = _get_user_plan_id(db, user_id)
        if plan_id not in ["hobby", "pro", "max", "ultimate"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The UTIM Rewards Wheel is available exclusively for paid plan subscribers."
            )

        cycle = _get_or_create_spin_cycle(db, user_id)
        
        active_reward = _get_active_reward(db, user_id)
        if active_reward:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The Rewards Wheel is locked while you have an active 24-hour reward."
            )

        if cycle.spins_used >= cycle.spins_granted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"You have used all {cycle.spins_granted} reward spins for your current subscription cycle."
            )

        # Atomic Snapshot Retrieval & Locking
        snapshot = db.query(RewardSnapshot).filter(
            RewardSnapshot.user_id == user_id,
            RewardSnapshot.status == "AVAILABLE"
        ).order_by(RewardSnapshot.created_at.desc()).first()

        if not snapshot:
            # Generate default snapshot
            prob_dist = calculate_wheel_probabilities(_get_models_list_dict(), [], plan_id)
            snapshot = RewardSnapshot(
                user_id=user_id,
                plan_id=plan_id,
                omitted_models_json=json.dumps([]),
                category_probs_json=json.dumps(prob_dist["category_probabilities"]),
                model_probs_json=json.dumps(prob_dist["models"]),
                status="LOCKED"
            )
            db.add(snapshot)
            db.commit()
            db.refresh(snapshot)
        else:
            snapshot.status = "LOCKED"
            db.commit()

        # Parse probability snapshot
        model_probs = json.loads(snapshot.model_probs_json)
        snapshot_dist = {
            "models": model_probs,
            "total_precision_units": REWARD_PROBABILITY_CONFIG["total_precision_units"]
        }

        # Perform Cryptographically Secure Weighted Selection
        spin_result = select_winning_model_secure(snapshot_dist)
        won_model = spin_result["winning_model"]

        # Mark snapshot COMPLETED
        snapshot.status = "COMPLETED"
        
        # Deduct spin from billing cycle
        cycle.spins_used += 1

        # Log spin transaction
        spin_record = RewardSpin(
            user_id=user_id,
            plan_id=plan_id,
            snapshot_id=snapshot.id,
            winning_model_id=won_model["model_id"],
            winning_model_name=won_model["name"],
            category=won_model["category"],
            probability_percent=won_model["probability_percent"],
            provider=won_model["provider"]
        )
        db.add(spin_record)

        # Activate 24-Hour Reward
        now = datetime.datetime.utcnow()
        reward_end = now + datetime.timedelta(seconds=REWARD_PROBABILITY_CONFIG["reward_duration_seconds"])

        # Deactivate any previous rewards
        db.query(RewardActivation).filter(
            RewardActivation.user_id == user_id,
            RewardActivation.is_active == True
        ).update({"is_active": False})

        activation = RewardActivation(
            user_id=user_id,
            model_id=won_model["model_id"],
            reward_start=now,
            reward_end=reward_end,
            is_active=True
        )
        db.add(activation)
        db.commit()

        return {
            "spin_id": spin_record.id,
            "winning_model": won_model,
            "reward_start": now.isoformat(),
            "reward_end": reward_end.isoformat(),
            "duration_hours": 24,
            "spins_remaining": max(0, cycle.spins_granted - cycle.spins_used),
            "message": f"Congratulations! You won 24-hour unlimited access to {won_model['name']}!"
        }
    except Exception as exc:
        db.rollback()
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Wheel spin processing error: {str(exc)}"
        )
    finally:
        db.close()


@router.post("/simulate")
def simulate_spins(
    req: SimulateSpinsRequest,
    current_user: User = Depends(get_current_user)
):
    """Run fast N-spin simulation engine to empirically verify probability distribution."""
    db = SessionLocal()
    try:
        plan_id, _ = _get_user_plan_id(db, current_user.id)
        simulation_res = simulate_wheel_spins(
            _get_models_list_dict(), req.omitted_models, plan_id, num_spins=req.num_spins
        )
        return simulation_res
    finally:
        db.close()
