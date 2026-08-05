"""
Routes: /completions — LLM proxy with streaming, billing, and token tracking
"""
from __future__ import annotations

import json
import logging
import os
import uuid
import datetime
import asyncio
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import Conversation, Credit, Transaction, User, UserSubscription, QuotaUsage, Plan, get_db, SessionLocal
from ..auth import get_current_user
from ..models import DEFAULT_MODEL, estimate_cost
from ..rate_limit import limiter

router = APIRouter(prefix="/completions", tags=["completions"])

def is_promo_active() -> bool:
    """Check if the July 2026 promotion is active (ends after July 31, 2026)."""
    import datetime
    return datetime.datetime.utcnow() < datetime.datetime(2026, 8, 1, 0, 0, 0)

ACTIVE_COMPLETION_TASKS: Dict[tuple, tuple] = {}

class CancelRequest(BaseModel):
    session_id: Optional[str] = None

class _BypassBillingException(Exception):
    pass

@router.post("/cancel", summary="Cancel an active completion request")
def cancel_completion(
    req: CancelRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    key = (user.id, req.session_id or "default")
    task_info = ACTIVE_COMPLETION_TASKS.get(key)
    if task_info:
        task, _ = task_info
        task.cancel()
        logger.info("cancel_completion_triggered", extra={"user_id": user.id, "session_id": req.session_id})
        return {"success": True, "message": "Request cancelled successfully"}
    return {"success": False, "message": "No active request found to cancel"}

logger = logging.getLogger("utim.routes.completions")

HEAVY_MODELS = {
    "anthropic/claude-opus-4.6",
    "openai/gpt-5.3-codex",
    "google/gemini-3.1-pro-preview",
    "anthropic/claude-sonnet-4.6",
}

def is_model_allowed(model_id: str, allowed_models_str: str, bonus_balance: float = 0.0) -> bool:
    """Check if a model is allowed for the user's plan.
    
    If bonus_balance > 0 on any plan (including free), all models are unlocked.
    """
    if bonus_balance > 0.0:
        return True
    if allowed_models_str == "all":
        return True
    
    allowed_tokens = [t.strip() for t in allowed_models_str.split(",")]
    if model_id in allowed_tokens:
        return True
        
    if "free" in allowed_tokens:
        if model_id.endswith(":free"):
            return True
        from ..models import MODEL_REGISTRY
        entry = MODEL_REGISTRY.get(model_id)
        if entry and "free" in entry.tags:
            return True
            
    return False

def get_or_create_quota(db: Session, user: User) -> QuotaUsage:
    now = datetime.datetime.utcnow()
    sub = db.query(UserSubscription).filter(UserSubscription.user_id == user.id).with_for_update().first()
    if not sub:
        end_date = now + datetime.timedelta(days=30)
        sub = UserSubscription(
            user_id=user.id,
            plan_id="free",
            status="active",
            current_period_start=now,
            current_period_end=end_date,
        )
        db.add(sub)
        db.flush()
    
    plan = sub.plan
    if not plan:
        plan = db.query(Plan).filter(Plan.id == sub.plan_id).first()
    
    limit = 100 if (plan and plan.id == "free") else (plan.credits_per_month if plan else 1000)
    
    quota = db.query(QuotaUsage).filter(
        QuotaUsage.user_id == user.id,
        QuotaUsage.period_start <= now,
        QuotaUsage.period_end >= now
    ).first()
    
    if not quota:
        last_quota = db.query(QuotaUsage).filter(
            QuotaUsage.user_id == user.id
        ).order_by(QuotaUsage.period_end.desc()).first()
        
        cycle_delta = datetime.timedelta(days=30)
        if last_quota and last_quota.period_end > now - datetime.timedelta(days=60):
            period_start = last_quota.period_end
            while period_start + cycle_delta < now:
                period_start = period_start + cycle_delta
            period_end = period_start + cycle_delta
        else:
            period_start = now
            period_end = now + cycle_delta
        
        quota = QuotaUsage(
            user_id=user.id,
            period_start=period_start,
            period_end=period_end,
            credits_used=0.0,
            credits_limit=limit,
            reset_at=period_end,
        )
        db.add(quota)
        
        sub.current_period_start = period_start
        sub.current_period_end = period_end
        db.commit()
        db.refresh(quota)
        
    return quota



# ── OpenRouter client ─────────────────────────────────────────────────────────

def _get_client() -> AsyncOpenAI:
    key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="LLM API key not configured on server.")
    # Attribution: OpenRouter shows "UTIM CLI Agent" only when HTTP-Referer +
    # X-Title are sent on every call. Without these the app logs as "unknown".
    try:
        import httpx
        from utim_cli.server.attribution import OPENROUTER_HEADERS
        http_client = httpx.AsyncClient(headers=OPENROUTER_HEADERS, timeout=900)
        return AsyncOpenAI(
            api_key=key,
            base_url="https://openrouter.ai/api/v1",
            http_client=http_client,
        )
    except Exception:
        return AsyncOpenAI(
            api_key=key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://utim.dev",
                "X-Title": "UTIM CLI Agent",
            },
        )


# ── Schema ────────────────────────────────────────────────────────────────────

class CompletionRequest(BaseModel):
    messages: List[Dict[str, Any]]
    model_id: str = DEFAULT_MODEL
    tools: Optional[List[Dict[str, Any]]] = None
    session_id: Optional[str] = None
    is_reflection: Optional[bool] = False
    preferred_quota: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    reasoning: Optional[Dict[str, Any]] = None



# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("", summary="Streaming LLM completion with automatic billing")
@limiter.limit("30/minute")
async def completions(
    request: Request,
    req: CompletionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Proxies messages to OpenRouter and streams NDJSON events back.

    Event types:
    - `{"type": "content_delta", "text": "..."}` — partial content
    - `{"type": "done", "role": "assistant", "content": "...", "tool_calls": [...]}` — final
    - `{"type": "done", "error": "..."}` — on failure

    Quota is deducted after the stream finishes.
    """
    current_task = asyncio.current_task()
    key = (user.id, req.session_id or "default")
    ACTIVE_COMPLETION_TASKS[key] = (current_task, db)

    if not req.is_reflection:
        # Ensure user has active subscription and quota
        quota = get_or_create_quota(db, user)
        sub = user.subscription
        plan = sub.plan if sub else None
        if not plan:
            plan = db.query(Plan).filter(Plan.id == (sub.plan_id if sub else "free")).first()

        allowed_models = plan.allowed_models if plan else "free"
        # Check model gating — bonus_balance unlocks all models even on free plan
        from ..db import Credit
        _cr = db.query(Credit).filter(Credit.user_id == user.id).first()
        _bonus = getattr(_cr, "bonus_balance", 0.0) or 0.0
        
        pref_quota = (request.headers.get("X-Preferred-Quota") or req.preferred_quota or "regular").lower().strip()
        
        if plan and plan.id == "free" and ":free" not in req.model_id:
            if pref_quota == "regular":
                raise HTTPException(
                    status_code=403,
                    detail="With your current plan you can't use premium models with your quota provided by the free plan. if u want to use premium models on UTIM provided quota please upgrade your plan or please use your bonus quota"
                )
            if _bonus <= 0.0:
                raise HTTPException(
                    status_code=403,
                    detail="Model is gated under your current Free plan and you have no bonus credits. Please top up your bonus quota to use premium models."
                )
        
        if not is_model_allowed(req.model_id, allowed_models, bonus_balance=_bonus):
            raise HTTPException(
                status_code=403,
                detail=f"Model '{req.model_id}' is gated under your current '{plan.display_name if plan else 'Free'}' plan. Please upgrade to Hobby/Pro/Team to access premium models."
            )

        limit_to_check = 3000.0 if (plan and plan.id == "free") else quota.credits_limit
        free_monthly_used = getattr(_cr, "free_monthly_used", 0.0) if _cr else 0.0
        used_to_check = free_monthly_used if (plan and plan.id == "free") else quota.credits_used
        if _bonus <= 0.0 and used_to_check >= limit_to_check:
            raise HTTPException(
                status_code=429,
                detail={
                    "message": "Monthly credit quota exceeded.",
                    "reset_at": quota.reset_at.isoformat() + "Z",
                    "upgrade_url": "https://utim.dev/upgrade"
                }
            )

        now = datetime.datetime.utcnow()

        # Check 5-hour cycle limit + credit bank for free plan
        if plan and plan.id == "free":
            from ..db import Credit
            credit_row = db.query(Credit).filter(Credit.user_id == user.id).first()
            balance = getattr(credit_row, "balance", 0.0) if credit_row else 0.0
            bonus_balance = getattr(credit_row, "bonus_balance", 0.0) if credit_row else 0.0
            if (balance + bonus_balance) <= 0.0:
                refill_interval = 5 * 3600
                period_start = sub.current_period_start if sub else now
                elapsed_in_window = (now - period_start).total_seconds() % refill_interval
                refill_remaining_seconds = int(refill_interval - elapsed_in_window)
                refill_time = now + datetime.timedelta(seconds=refill_remaining_seconds)
                raise HTTPException(
                    status_code=429,
                    detail={
                        "message": "5-hour credit quota exhausted.",
                        "reset_at": refill_time.isoformat() + "Z",
                        "upgrade_url": "https://utim.dev/upgrade"
                    }
                )

        # Check 5-hour cycle limit + credit bank for paid plans
        if plan and plan.id != "free" and sub:
            cycle_allowance = plan.credits_per_month / 144.0
            current_cycle_used = sub.current_cycle_used or 0.0
            if current_cycle_used >= cycle_allowance:
                from ..db import Credit
                credit_row = db.query(Credit).filter(Credit.user_id == user.id).first()
                balance = credit_row.balance if credit_row else 0.0
                bonus_balance = getattr(credit_row, "bonus_balance", 0.0) or 0.0
                if (balance + bonus_balance) <= 0.0:
                    # Calculate next refill time
                    refill_interval = 5 * 3600
                    period_start = sub.current_period_start or sub.created_at or now
                    elapsed_in_window = (now - period_start).total_seconds() % refill_interval
                    refill_remaining_seconds = int(refill_interval - elapsed_in_window)
                    refill_time = now + datetime.timedelta(seconds=refill_remaining_seconds)
                    raise HTTPException(
                        status_code=429,
                        detail={
                            "message": "5-hour credit quota exhausted.",
                            "reset_at": refill_time.isoformat() + "Z",
                            "upgrade_url": "https://utim.dev/upgrade"
                        }
                    )


    client = _get_client()

    # Commit transaction to release all with_for_update locks on UserSubscription
    # before returning the StreamingResponse, preventing deadlocks in the generator's SessionLocal updates.
    db.commit()

    async def _stream() -> AsyncGenerator[str, None]:
        content_buf = ""
        tool_calls_map: Dict[int, Dict[str, Any]] = {}
        input_tokens = 0
        output_tokens = 0
        final_input = 0
        final_output = 0
        error_msg: Optional[str] = None
        is_aborted = False

        try:
            extra_body = {"stream_options": {"include_usage": True}}
            if req.reasoning and isinstance(req.reasoning, dict):
                clean_reasoning = {}
                if req.reasoning.get("enabled") is not False:
                    if "effort" in req.reasoning:
                        clean_reasoning["effort"] = req.reasoning["effort"]
                    if "max_tokens" in req.reasoning:
                        clean_reasoning["max_tokens"] = req.reasoning["max_tokens"]
                if clean_reasoning:
                    extra_body["reasoning"] = clean_reasoning
                
            kwargs = {
                "model": req.model_id,
                "messages": req.messages,
                "tools": req.tools or None,
                "tool_choice": "auto" if req.tools else None,
                "stream": True,
                "timeout": 900,
                "extra_body": extra_body
            }
            if req.temperature is not None:
                kwargs["temperature"] = req.temperature
            if req.max_tokens is not None:
                # OpenRouter accepts max_tokens
                kwargs["max_tokens"] = req.max_tokens

            stream = await client.chat.completions.create(**kwargs)

            async for chunk in stream:
                if getattr(chunk, "usage", None):
                    input_tokens = chunk.usage.prompt_tokens or 0
                    output_tokens = chunk.usage.completion_tokens or 0

                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                if delta.content:
                    content_buf += delta.content
                    yield json.dumps({"type": "content_delta", "text": delta.content}) + "\n"

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index if tc.index is not None else 0
                        if idx not in tool_calls_map:
                            tool_calls_map[idx] = {
                                "id": tc.id or "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            }
                        entry = tool_calls_map[idx]
                        if tc.id and not entry["id"]:
                            entry["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                entry["function"]["name"] += tc.function.name
                            if tc.function.arguments:
                                entry["function"]["arguments"] += tc.function.arguments

        except (asyncio.CancelledError, GeneratorExit) as exc:
            is_aborted = True
            error_msg = "Request cancelled by user"
            logger.info("completion_cancelled", extra={
                "user_id": user.id,
                "model": req.model_id,
            })
            raise exc
        except Exception as exc:
            error_msg = str(exc)
            logger.error("completion_error", extra={
                "user_id": user.id,
                "model": req.model_id,
                "error": error_msg,
            })

        finally:
            ACTIVE_COMPLETION_TASKS.pop(key, None)
            tool_calls = (
                [tool_calls_map[i] for i in sorted(tool_calls_map)]
                if tool_calls_map else None
            )

            # ── Billing / Quota Update (never blocks the done event) ──────
            try:
                if req.is_reflection:
                    raise _BypassBillingException()
                if is_aborted:
                    raise _BypassBillingException()
                fresh_db = SessionLocal()
                try:
                    now_dt = datetime.datetime.utcnow()
                    quota_row = fresh_db.query(QuotaUsage).with_for_update().filter(
                        QuotaUsage.user_id == user.id,
                        QuotaUsage.period_start <= now_dt,
                        QuotaUsage.period_end >= now_dt
                    ).first()
                    if not quota_row:
                        # Auto-create QuotaUsage row for this cycle
                        cycle_start = now_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                        cycle_end = (cycle_start + datetime.timedelta(days=32)).replace(day=1)
                        quota_row = QuotaUsage(
                            user_id=user.id,
                            period_start=cycle_start,
                            period_end=cycle_end,
                            credits_used=0.0,
                            credits_limit=100,
                            reset_at=cycle_end,
                        )
                        fresh_db.add(quota_row)
                        fresh_db.flush()

                    # Fix stale credits_limit
                    if quota_row.credits_limit == 1000:
                        quota_row.credits_limit = 100

                    if True:
                        final_input = input_tokens
                        final_output = output_tokens
                        
                        if final_input <= 0:
                            total_chars = 0
                            for msg in req.messages:
                                content = msg.get("content") or ""
                                if isinstance(content, str):
                                    total_chars += len(content)
                                elif isinstance(content, list):
                                    for part in content:
                                        if isinstance(part, dict) and part.get("type") == "text":
                                            total_chars += len(part.get("text", ""))
                            final_input = max(100, int(total_chars / 3.8))
                            
                        if final_output <= 0:
                            final_output = max(10, int(len(content_buf) / 3.8))

                        sub_row = fresh_db.query(UserSubscription).with_for_update().filter(UserSubscription.user_id == user.id).first()
                        plan = sub_row.plan if (sub_row and sub_row.status == "active") else None
                        is_upgraded = plan is not None and plan.id != "free"

                        credits_cost = estimate_cost(req.model_id, final_input, final_output, is_upgraded=is_upgraded)
                        
                        if plan and plan.id != "free":
                            cycle_days = (sub_row.current_period_end - sub_row.current_period_start).days
                            is_yearly = cycle_days > 45
                            cycle_allowance = plan.credits_per_month / 144.0
                            current_cycle_used = sub_row.current_cycle_used or 0.0
                            
                            cost_to_charge = credits_cost
                            credit_row = fresh_db.query(Credit).with_for_update().filter(Credit.user_id == user.id).first()
                            
                            charged_to_bonus = 0.0
                            if credit_row:
                                bonus_balance = getattr(credit_row, "bonus_balance", 0.0) or 0.0
                                
                                if pref_quota == "bonus":
                                    # Deduct from bonus balance first
                                    if bonus_balance > 0.0:
                                        if cost_to_charge <= bonus_balance:
                                            credit_row.bonus_balance = bonus_balance - cost_to_charge
                                            charged_to_bonus = cost_to_charge
                                            cost_to_charge = 0.0
                                        else:
                                            credit_row.bonus_balance = 0.0
                                            charged_to_bonus = bonus_balance
                                            cost_to_charge -= bonus_balance
                                            
                                    # Deduct remaining from regular cycle allowance
                                    if cost_to_charge > 0.0:
                                        remaining_allowance = max(0.0, cycle_allowance - current_cycle_used)
                                        if cost_to_charge <= remaining_allowance:
                                            sub_row.current_cycle_used = current_cycle_used + cost_to_charge
                                            cost_to_charge = 0.0
                                        else:
                                            sub_row.current_cycle_used = cycle_allowance
                                            cost_to_charge -= remaining_allowance
                                            
                                    # Deduct remaining from credit balance
                                    if cost_to_charge > 0.0:
                                        credit_row.balance = max(0.0, credit_row.balance - cost_to_charge)
                                else:
                                    # pref_quota == "regular" (prioritize cycle allowance and credit balance first)
                                    # Deduct from cycle allowance first
                                    remaining_allowance = max(0.0, cycle_allowance - current_cycle_used)
                                    if cost_to_charge <= remaining_allowance:
                                        sub_row.current_cycle_used = current_cycle_used + cost_to_charge
                                        cost_to_charge = 0.0
                                    else:
                                        sub_row.current_cycle_used = cycle_allowance
                                        cost_to_charge -= remaining_allowance
                                        
                                    # Deduct from credit balance second
                                    if cost_to_charge > 0.0:
                                        if cost_to_charge <= credit_row.balance:
                                            credit_row.balance = credit_row.balance - cost_to_charge
                                            cost_to_charge = 0.0
                                        else:
                                            cost_to_charge -= credit_row.balance
                                            credit_row.balance = 0.0
                                            
                                    # Deduct from bonus balance third
                                    if cost_to_charge > 0.0 and bonus_balance > 0.0:
                                        if cost_to_charge <= bonus_balance:
                                            credit_row.bonus_balance = bonus_balance - cost_to_charge
                                            charged_to_bonus = cost_to_charge
                                            cost_to_charge = 0.0
                                        else:
                                            credit_row.bonus_balance = 0.0
                                            charged_to_bonus = bonus_balance
                                            cost_to_charge -= bonus_balance
                                
                                # Only charge the portion NOT covered by bonus to the regular quota usage
                                charged_to_regular = credits_cost - charged_to_bonus
                                quota_row.credits_used += charged_to_regular
                                
                            if credit_row:
                                # Low / Exhausted Quota Warning Check
                                total_remaining = credit_row.balance + (getattr(credit_row, "bonus_balance", 0.0) or 0.0)
                                limit = plan.credits_per_month * 2.0
                                is_exhausted = total_remaining <= 0.0
                                is_low = total_remaining > 0.0 and total_remaining <= (limit * 0.1)
                                
                                if is_exhausted or is_low:
                                    from ..db import EmailTracking
                                    tracking = fresh_db.query(EmailTracking).filter(EmailTracking.user_id == user.id).first()
                                    if not tracking:
                                        tracking = EmailTracking(
                                            user_id=user.id,
                                            email=user.email,
                                            display_name=user.display_name or user.email.split("@")[0],
                                            welcome_email_sent=True
                                        )
                                        fresh_db.add(tracking)
                                        fresh_db.flush()
                                    
                                    period_start = sub_row.current_period_start or sub_row.created_at
                                    send_type = None
                                    now_utc = datetime.datetime.utcnow()
                                    if is_exhausted:
                                        last_sent = tracking.exhausted_email_sent_at
                                        if not last_sent or last_sent < period_start:
                                            send_type = "exhausted"
                                            tracking.exhausted_email_sent_at = now_utc
                                            fresh_db.commit()
                                    elif is_low:
                                        last_sent = tracking.low_quota_email_sent_at
                                        if not last_sent or last_sent < period_start:
                                            send_type = "low"
                                            tracking.low_quota_email_sent_at = now_utc
                                            fresh_db.commit()
                                            
                                    if send_type:
                                        from ..email_utils import send_quota_left_email
                                        import threading
                                        def send_quota_bg(email, name, percent, exhausted, s_type):
                                            thread_db = SessionLocal()
                                            try:
                                                success = send_quota_left_email(email, name, percent, exhausted)
                                                if not success:
                                                    thread_tracking = thread_db.query(EmailTracking).filter(EmailTracking.user_id == user.id).first()
                                                    if thread_tracking:
                                                        if s_type == "exhausted":
                                                            thread_tracking.exhausted_email_sent_at = None
                                                        else:
                                                            thread_tracking.low_quota_email_sent_at = None
                                                        thread_db.commit()
                                            except Exception as e:
                                                logger.error(f"Error sending quota warning email in thread: {e}")
                                                thread_tracking = thread_db.query(EmailTracking).filter(EmailTracking.user_id == user.id).first()
                                                if thread_tracking:
                                                    if s_type == "exhausted":
                                                        thread_tracking.exhausted_email_sent_at = None
                                                    else:
                                                        thread_tracking.low_quota_email_sent_at = None
                                                    thread_db.commit()
                                            finally:
                                                thread_db.close()
                                        
                                        percent_remaining = (total_remaining / limit) * 100.0
                                        threading.Thread(
                                            target=send_quota_bg,
                                            args=(user.email, user.display_name or user.email.split("@")[0], percent_remaining, is_exhausted, send_type),
                                            daemon=True
                                        ).start()
                        else:
                            # ── Free tier billing ────────────────────────────────────────
                            FREE_PLAN_MONTHLY_CAP = 3000.0
                            FREE_PLAN_SLOT_CAP    = 100.0   # max balance at any time (no stacking)

                            credit_row = fresh_db.query(Credit).filter(Credit.user_id == user.id).first()
                            if credit_row:
                                bonus_bal = getattr(credit_row, "bonus_balance", 0.0) or 0.0
                                free_monthly = getattr(credit_row, "free_monthly_used", 0.0) or 0.0
                                cost_to_charge = credits_cost
                                charged_to_bonus = 0.0

                                if pref_quota == "bonus":
                                    # Prioritize bonus balance
                                    if bonus_bal > 0.0:
                                        if cost_to_charge <= bonus_bal:
                                            credit_row.bonus_balance = bonus_bal - cost_to_charge
                                            charged_to_bonus = cost_to_charge
                                            cost_to_charge = 0.0
                                        else:
                                            credit_row.bonus_balance = 0.0
                                            charged_to_bonus = bonus_bal
                                            cost_to_charge -= bonus_bal

                                    if cost_to_charge > 0.0:
                                        remaining_monthly = FREE_PLAN_MONTHLY_CAP - free_monthly
                                        actual_cost = min(cost_to_charge, remaining_monthly)
                                        if actual_cost > 0.0:
                                            credit_row.balance = max(0.0, credit_row.balance - actual_cost)
                                            credit_row.free_monthly_used = min(FREE_PLAN_MONTHLY_CAP, free_monthly + actual_cost)
                                else:
                                    # pref_quota == "regular" (prioritize free 5-hour quota first)
                                    remaining_monthly = FREE_PLAN_MONTHLY_CAP - free_monthly
                                    actual_cost = min(cost_to_charge, remaining_monthly)
                                    if actual_cost > 0.0:
                                        if actual_cost <= credit_row.balance:
                                            credit_row.balance = credit_row.balance - actual_cost
                                            credit_row.free_monthly_used = min(FREE_PLAN_MONTHLY_CAP, free_monthly + actual_cost)
                                            cost_to_charge -= actual_cost
                                        else:
                                            allowed_deduct = credit_row.balance
                                            credit_row.balance = 0.0
                                            credit_row.free_monthly_used = min(FREE_PLAN_MONTHLY_CAP, free_monthly + allowed_deduct)
                                            cost_to_charge -= allowed_deduct

                                    # Deduct remaining from bonus balance
                                    if cost_to_charge > 0.0 and bonus_bal > 0.0:
                                        if cost_to_charge <= bonus_bal:
                                            credit_row.bonus_balance = bonus_bal - cost_to_charge
                                            charged_to_bonus = cost_to_charge
                                            cost_to_charge = 0.0
                                        else:
                                            credit_row.bonus_balance = 0.0
                                            charged_to_bonus = bonus_bal
                                            cost_to_charge -= bonus_bal

                                # Only charge the portion NOT covered by bonus to the regular quota usage
                                charged_to_regular = credits_cost - charged_to_bonus
                                quota_row.credits_used += charged_to_regular

                                # If bonus just ran out, flag so client can prompt restart
                                if (credit_row.bonus_balance or 0.0) <= 0.0:
                                    credit_row.bonus_balance = 0.0
                                    credit_row.bonus_limit = max(0.0, getattr(credit_row, "bonus_limit", 0.0))
                                    # Signal flag via transaction if they HAD a bonus that is now exhausted
                                    if bonus_bal > 0.0:
                                        _bonus_exhausted_tx = Transaction(
                                            id=str(uuid.uuid4()),
                                            user_id=user.id,
                                            kind="bonus_exhausted",
                                            amount=0.0,
                                            balance_after=credit_row.balance,
                                            description="Free plan bonus credits exhausted — premium models now locked"
                                        )
                                        fresh_db.add(_bonus_exhausted_tx)

                        # Update conversation token counts
                        if req.session_id:
                            conv = fresh_db.query(Conversation).filter(
                                Conversation.id == req.session_id
                            ).first()
                            if conv:
                                conv.token_usage_input += final_input
                                conv.token_usage_output += final_output

                        fresh_db.commit()
                        logger.info("quota_billing", extra={
                            "user_id": user.id,
                            "model": req.model_id,
                            "input_tokens": final_input,
                            "output_tokens": final_output,
                            "credits_cost": credits_cost,
                            "credits_used": quota_row.credits_used,
                            "credits_limit": quota_row.credits_limit,
                        })
                finally:
                    fresh_db.close()
            except _BypassBillingException:
                pass
            except Exception as bill_err:
                logger.error("billing_error", extra={"error": str(bill_err)})

            # ── Done event ─────────────────────────────────────────────────
            done: Dict[str, Any] = {
                "type": "done",
                "role": "assistant",
                "content": content_buf or None,
                "tool_calls": tool_calls,
                "usage": {
                    "input_tokens": final_input if final_input > 0 else input_tokens,
                    "output_tokens": final_output if final_output > 0 else output_tokens,
                },
            }
            if error_msg:
                done["error"] = error_msg
            yield json.dumps(done) + "\n"

    return StreamingResponse(_stream(), media_type="application/x-ndjson")


def deduct_credits_unallocated_first(db: Session, user: User, credits_cost: float, pref_quota: str = "regular") -> float:
    """
    Deduction algorithm that prioritizes unallocated plan pool first, keeping 5-hour cycles untouched.
    Deduction Priority:
       1. bonus_balance (if pref_quota == "bonus")
       2. unallocated plan credits (increments sub.unallocated_deducted)
       3. credit.balance (Quota Bank / Rollover)
       4. bonus_balance (if pref_quota == "regular")
       5. current_cycle_used (last resort)
    """
    from ..db import Credit, UserSubscription, Plan, QuotaUsage
    credit_row = db.query(Credit).with_for_update().filter(Credit.user_id == user.id).first()
    sub_row = db.query(UserSubscription).with_for_update().filter(UserSubscription.user_id == user.id).first()
    quota_row = db.query(QuotaUsage).with_for_update().filter(QuotaUsage.user_id == user.id).first()
    
    if not credit_row or not quota_row:
        return 0.0
        
    plan = sub_row.plan if sub_row else None
    if not plan and sub_row:
        plan = db.query(Plan).filter(Plan.id == sub_row.plan_id).first()
        
    is_free = (not plan or plan.id == "free")
    cost_to_charge = credits_cost
    bonus_bal = getattr(credit_row, "bonus_balance", 0.0) or 0.0
    charged_to_bonus = 0.0
    
    if is_free:
        if pref_quota == "bonus":
            if bonus_bal > 0.0:
                if cost_to_charge <= bonus_bal:
                    credit_row.bonus_balance = bonus_bal - cost_to_charge
                    charged_to_bonus = cost_to_charge
                    cost_to_charge = 0.0
                else:
                    credit_row.bonus_balance = 0.0
                    charged_to_bonus = bonus_bal
                    cost_to_charge -= bonus_bal
            if cost_to_charge > 0.0:
                free_monthly = getattr(credit_row, "free_monthly_used", 0.0) or 0.0
                FREE_PLAN_MONTHLY_CAP = 3000.0
                remaining_monthly = FREE_PLAN_MONTHLY_CAP - free_monthly
                actual_cost = min(cost_to_charge, max(0.0, remaining_monthly))
                credit_row.balance = max(0.0, credit_row.balance - actual_cost)
                credit_row.free_monthly_used = min(FREE_PLAN_MONTHLY_CAP, free_monthly + actual_cost)
        else:
            free_monthly = getattr(credit_row, "free_monthly_used", 0.0) or 0.0
            FREE_PLAN_MONTHLY_CAP = 3000.0
            remaining_monthly = FREE_PLAN_MONTHLY_CAP - free_monthly
            actual_cost = min(cost_to_charge, max(0.0, remaining_monthly))
            if actual_cost > 0.0:
                if actual_cost <= credit_row.balance:
                    credit_row.balance = credit_row.balance - actual_cost
                    credit_row.free_monthly_used = min(FREE_PLAN_MONTHLY_CAP, free_monthly + actual_cost)
                    cost_to_charge -= actual_cost
                else:
                    allowed_deduct = credit_row.balance
                    credit_row.balance = 0.0
                    credit_row.free_monthly_used = min(FREE_PLAN_MONTHLY_CAP, free_monthly + allowed_deduct)
                    cost_to_charge -= allowed_deduct
            if cost_to_charge > 0.0 and bonus_bal > 0.0:
                if cost_to_charge <= bonus_bal:
                    credit_row.bonus_balance = bonus_bal - cost_to_charge
                    charged_to_bonus = cost_to_charge
                    cost_to_charge = 0.0
                else:
                    credit_row.bonus_balance = 0.0
                    charged_to_bonus = bonus_bal
                    cost_to_charge -= bonus_bal
    else:
        # Paid Tier Plans
        # 1. bonus_balance (if pref_quota == "bonus")
        if pref_quota == "bonus" and bonus_bal > 0.0:
            if cost_to_charge <= bonus_bal:
                credit_row.bonus_balance = bonus_bal - cost_to_charge
                charged_to_bonus = cost_to_charge
                cost_to_charge = 0.0
            else:
                credit_row.bonus_balance = 0.0
                charged_to_bonus = bonus_bal
                cost_to_charge -= bonus_bal
                
        # 2. unallocated plan credits (future cycle pool)
        if cost_to_charge > 0.0 and sub_row:
            cycle_allowance = plan.credits_per_month / 144.0
            refills_processed = sub_row.refills_processed or 0
            allocated_to_cycles = refills_processed * cycle_allowance
            quota_bank = max(0.0, credit_row.balance or 0.0)
            current_cycle_used = sub_row.current_cycle_used or 0.0
            unallocated_deducted = getattr(sub_row, "unallocated_deducted", 0.0) or 0.0
            
            unallocated = max(
                0.0,
                plan.credits_per_month - allocated_to_cycles - quota_bank - current_cycle_used - unallocated_deducted
            )
            
            if unallocated > 0.0:
                take = min(cost_to_charge, unallocated)
                sub_row.unallocated_deducted = unallocated_deducted + take
                cost_to_charge -= take
                
        # 3. credit.balance (Quota Bank / Rollover)
        if cost_to_charge > 0.0:
            if cost_to_charge <= credit_row.balance:
                credit_row.balance = credit_row.balance - cost_to_charge
                cost_to_charge = 0.0
            else:
                cost_to_charge -= credit_row.balance
                credit_row.balance = 0.0
                
        # 4. bonus_balance (if pref_quota == "regular")
        if cost_to_charge > 0.0 and pref_quota == "regular":
            remaining_bonus = credit_row.bonus_balance or 0.0
            if remaining_bonus > 0.0:
                if cost_to_charge <= remaining_bonus:
                    credit_row.bonus_balance = remaining_bonus - cost_to_charge
                    charged_to_bonus += cost_to_charge
                    cost_to_charge = 0.0
                else:
                    credit_row.bonus_balance = 0.0
                    charged_to_bonus += remaining_bonus
                    cost_to_charge -= remaining_bonus
                    
        # 5. current_cycle_used (last resort)
        if cost_to_charge > 0.0 and sub_row:
            cycle_allowance = plan.credits_per_month / 144.0
            current_cycle_used = sub_row.current_cycle_used or 0.0
            remaining_allowance = max(0.0, cycle_allowance - current_cycle_used)
            if cost_to_charge <= remaining_allowance:
                sub_row.current_cycle_used = current_cycle_used + cost_to_charge
                cost_to_charge = 0.0
            else:
                sub_row.current_cycle_used = cycle_allowance
                cost_to_charge -= remaining_allowance
                
    charged_to_regular = credits_cost - charged_to_bonus
    quota_row.credits_used += charged_to_regular
    
    # Ensure bonus_balance doesn't become negative
    if (credit_row.bonus_balance or 0.0) <= 0.0:
        credit_row.bonus_balance = 0.0
        credit_row.bonus_limit = max(0.0, getattr(credit_row, "bonus_limit", 0.0))
        
    db.commit()
    return charged_to_bonus


# ── NVIDIA Image Generation Proxy ─────────────────────────────────────────────

class ImageGenerationRequest(BaseModel):
    prompt: str
    model: str
    width: Optional[int] = None
    height: Optional[int] = None
    steps: Optional[int] = None
    cfg_scale: Optional[float] = None
    seed: Optional[int] = None

@router.post("/images/generations", summary="Proxy image generation to NVIDIA NIM API")
def generate_image_proxy(
    request: Request,
    req: ImageGenerationRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Proxies image generation request to NVIDIA NIM / OpenRouter API.
    Deducts 80.0 credits flat rate per generation.
    """
    import requests as _requests

    # Check and enforce quota
    quota = get_or_create_quota(db, user)
    from ..db import Credit
    credit_row = db.query(Credit).filter(Credit.user_id == user.id).first()
    bonus_balance = getattr(credit_row, "bonus_balance", 0.0) or 0.0
    
    sub = user.subscription
    plan = sub.plan if sub else None
    if not plan:
        from ..db import Plan
        plan = db.query(Plan).filter(Plan.id == (sub.plan_id if sub else "free")).first()
        
    limit_to_check = 3000.0 if (plan and plan.id == "free") else quota.credits_limit
    free_monthly_used = getattr(credit_row, "free_monthly_used", 0.0) if credit_row else 0.0
    used_to_check = free_monthly_used if (plan and plan.id == "free") else quota.credits_used
    
    if bonus_balance <= 0.0 and used_to_check >= limit_to_check:
        raise HTTPException(
            status_code=429,
            detail={
                "message": "Monthly credit quota exceeded.",
                "reset_at": quota.reset_at.isoformat() + "Z",
                "upgrade_url": "https://utim.dev/upgrade"
            }
        )

    is_openrouter = False
    from ..models import get_model
    model_entry = get_model(req.model)
    if model_entry and model_entry.provider == "openrouter":
        is_openrouter = True
        
    if is_openrouter:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise HTTPException(status_code=503, detail="OPENROUTER_API_KEY not configured on server.")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://utim.dev",
            "X-Title": "UTIM Agent"
        }
        payload = {
            "model": req.model,
            "prompt": req.prompt
        }
        if req.width is not None and req.height is not None:
            payload["size"] = f"{req.width}x{req.height}"
        elif req.width is not None:
            payload["width"] = req.width
        if req.seed is not None:
            payload["seed"] = req.seed
        if req.steps is not None:
            payload["steps"] = req.steps
        url = "https://openrouter.ai/api/v1/images/generations"
    else:
        nvidia_key = os.environ.get("NVIDIA_API_KEY")
        if not nvidia_key:
            raise HTTPException(status_code=503, detail="NVIDIA_API_KEY not configured on server.")

        headers = {
            "Authorization": f"Bearer {nvidia_key}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        # Format the payload to fit Stability or Flux models
        if "stabilityai" in req.model:
            payload = {
                "text_prompts": [{"text": req.prompt, "weight": 1.0}]
            }
            if req.seed is not None:
                payload["seed"] = req.seed
            if req.width is not None:
                payload["width"] = req.width
            if req.height is not None:
                payload["height"] = req.height
            if req.steps is not None:
                payload["steps"] = req.steps
            if req.cfg_scale is not None:
                payload["cfg_scale"] = req.cfg_scale
        else:
            payload = {
                "prompt": req.prompt
            }
            if req.seed is not None:
                payload["seed"] = req.seed
            if req.width is not None:
                payload["width"] = req.width
            if req.height is not None:
                payload["height"] = req.height
        
        url = f"https://ai.api.nvidia.com/v1/genai/{req.model}"

    try:
        resp = _requests.post(url, json=payload, headers=headers, timeout=120)
        resp_json = resp.json()
    except Exception as e:
        logger.error("image_generation_error", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Failed to generate image via API: {str(e)}")

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp_json)

    # Deduct credit cost for image generation: flat 80.0 credits ($0.08 USD), 50% off during promo until July 31, 2026
    credits_cost = 40.0 if is_promo_active() else 80.0
    try:
        pref_quota = request.headers.get("X-Preferred-Quota", "regular").lower().strip()
        deduct_credits_unallocated_first(db, user, credits_cost, pref_quota)
        logger.info("image_generation_billing", extra={
            "user_id": user.id,
            "model": req.model,
            "credits_cost": credits_cost,
        })
    except Exception as bill_err:
        logger.error("image_billing_error", extra={"error": str(bill_err)})

    return resp_json


class WebSearchRequest(BaseModel):
    query: str
    level: str = "medium"

@router.post("/search", summary="Proxy web search to Tavily API")
def web_search_proxy(
    req: WebSearchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Proxies web search query to Tavily API using server-side TAVILY_API_KEY.
    """
    import requests as _requests
    
    tavily_key = os.environ.get("TAVILY_API_KEY")
    if not tavily_key:
        raise HTTPException(status_code=503, detail="TAVILY_API_KEY is not configured on the server.")
        
    num_results = 5
    search_depth = "advanced" if req.level.lower() in ("medium", "high") else "basic"
    
    try:
        tavily_resp = _requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": tavily_key,
                "query": req.query,
                "search_depth": search_depth,
                "include_answer": False,
                "include_raw_content": False,
                "include_images": False,
                "max_results": num_results
            },
            timeout=15
        )
        tavily_resp.raise_for_status()
        return tavily_resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to query Tavily API: {e}")


# ── Tripo 3D Model Generation Proxy ───────────────────────────────────────────

class Tripo3DRequest(BaseModel):
    type: str # text_to_model, image_to_model, multiview_to_model, texture_model, refine_model
    prompt: Optional[str] = None
    image_url: Optional[str] = None
    file_token: Optional[str] = None
    original_model_task_id: Optional[str] = None
    model: Optional[str] = "v3.1"
    model_version: Optional[str] = None
    model_seed: Optional[int] = None

    # Advanced / Mesh / Post-Processing parameters
    quad: Optional[bool] = None
    face_limit: Optional[int] = None
    texture: Optional[bool] = None
    pbr: Optional[bool] = None
    texture_quality: Optional[str] = None
    texture_size: Optional[int] = None
    texture_format: Optional[str] = None
    geometry_quality: Optional[str] = None
    flatten_bottom: Optional[bool] = None
    flatten_bottom_threshold: Optional[float] = None
    pivot_to_center_bottom: Optional[bool] = None
    scale_factor: Optional[float] = None

    # Rigging & Animation parameters
    rig_type: Optional[str] = None
    spec: Optional[str] = None
    out_format: Optional[str] = None
    animation: Optional[str] = None

    model_config = {"extra": "allow"}

@router.post("/3d/upload", summary="Proxy local file upload to Tripo AI")
def upload_3d_file_proxy(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from ..db import UserSubscription, Plan
    sub_row = db.query(UserSubscription).filter(UserSubscription.user_id == user.id).first()
    plan = sub_row.plan if sub_row else None
    if not plan and sub_row:
        plan = db.query(Plan).filter(Plan.id == sub_row.plan_id).first()
    if not plan or plan.id not in ("pro", "max", "ultimate"):
        raise HTTPException(
            status_code=403,
            detail="Blender & 3D Tools are only available on the Starter plan (Starter Node) or higher. Please upgrade your subscription."
        )
    import os
    import requests as _requests
    
    tripo_key = request.headers.get("X-Tripo-API-Key") or os.environ.get("TRIPO_API_KEY")
    if not tripo_key:
        raise HTTPException(
            status_code=500,
            detail="Tripo 3D API key is not configured on the server."
        )
        
    url = "https://api.tripo3d.ai/v2/openapi/upload"
    headers = {
        "Authorization": f"Bearer {tripo_key}"
    }
    
    try:
        files = {
            "file": (file.filename, file.file.read(), file.content_type)
        }
        resp = _requests.post(url, files=files, headers=headers, timeout=60)
        resp_json = resp.json()
    except Exception as e:
        logger.error("tripo_upload_error", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Failed to upload file to Tripo AI: {str(e)}")
        
    if resp.status_code != 200 or resp_json.get("code") != 0:
        logger.error("tripo_upload_failure", extra={"status": resp.status_code, "response": resp_json})
        msg = resp_json.get("message", "Unknown Tripo upload error")
        raise HTTPException(status_code=resp.status_code if resp.status_code == 200 else 400, detail=f"Tripo AI: {msg}")
        
    return resp_json

def calculate_tripo_credits_cost(req: Tripo3DRequest) -> float:
    task_type = req.type.lower().strip()
    texture_enabled = req.texture if req.texture is not None else True
    base_cost = 0.0

    if task_type == "text_to_model":
        base_cost = 20.0 if texture_enabled else 10.0
    elif task_type in ("image_to_model", "multiview_to_model"):
        base_cost = 30.0 if texture_enabled else 20.0
    elif task_type == "texture_model":
        tq = (req.texture_quality or "standard").lower().strip()
        if tq == "extreme":
            base_cost = 30.0
        elif tq == "detailed":
            base_cost = 20.0
        else:
            base_cost = 10.0
    elif task_type == "refine_model":
        base_cost = 30.0
    elif task_type == "animate_rig":
        base_cost = 25.0
    elif task_type == "animate_retarget":
        base_cost = 10.0
    elif task_type == "animate_prerigcheck":
        base_cost = 0.0
    else:
        base_cost = 20.0

    addons = 0.0
    tq = (req.texture_quality or "standard").lower().strip()
    if texture_enabled and task_type in ("text_to_model", "image_to_model", "multiview_to_model"):
        if tq == "extreme":
            addons += 20.0
        elif tq == "detailed":
            addons += 10.0

    gq = (req.geometry_quality or "standard").lower().strip()
    if gq in ("detailed", "extreme"):
        addons += 20.0

    if req.quad:
        addons += 5.0

    if req.model == "p1" or req.model_version == "P1-20260311":
        addons += 10.0

    has_advanced_convert = (
        req.quad is not None or
        req.face_limit is not None or
        req.flatten_bottom is not None or
        req.flatten_bottom_threshold is not None or
        req.texture_size is not None or
        req.texture_format is not None or
        req.pivot_to_center_bottom is not None or
        req.scale_factor is not None
    )
    if has_advanced_convert and task_type not in ("animate_rig", "animate_retarget", "animate_prerigcheck"):
        addons += 10.0

    tripo_total = base_cost + addons
    utim_credits = tripo_total * 15.0
    return utim_credits


@router.post("/3d/generations", summary="Submit Tripo 3D generation task")
def generate_3d_task_proxy(
    request: Request,
    req: Tripo3DRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Submits a 3D model generation task to Tripo AI and bills the user based on task type.
    """
    import os
    import requests as _requests
    import datetime
    
    # 1. Plan check: Blender tools are only available from Starter plan (pro) or higher
    from ..db import UserSubscription, Plan
    sub_row = db.query(UserSubscription).filter(UserSubscription.user_id == user.id).first()
    plan = sub_row.plan if sub_row else None
    if not plan and sub_row:
        plan = db.query(Plan).filter(Plan.id == sub_row.plan_id).first()
    if not plan or plan.id not in ("pro", "max", "ultimate"):
        raise HTTPException(
            status_code=403,
            detail="Blender & 3D Tools are only available on the Starter plan (Starter Node) or higher. Please upgrade your subscription."
        )

    tripo_key = request.headers.get("X-Tripo-API-Key") or os.environ.get("TRIPO_API_KEY")
    if not tripo_key:
        raise HTTPException(
            status_code=500,
            detail="Tripo 3D API key is not configured on the server."
        )

    # 2. Promo period check (until July 31, 2026): 20% off
    promo_multiplier = 0.8 if is_promo_active() else 1.0

    # Determine credit cost dynamically:
    credits_cost = calculate_tripo_credits_cost(req) * promo_multiplier

    # Verify if user has sufficient credits available across all pools
    from ..db import Credit, UserSubscription, Plan
    credit_row = db.query(Credit).filter(Credit.user_id == user.id).first()
    sub_row = db.query(UserSubscription).filter(UserSubscription.user_id == user.id).first()
    plan = sub_row.plan if sub_row else None
    if not plan and sub_row:
        plan = db.query(Plan).filter(Plan.id == sub_row.plan_id).first()
        
    quota = get_or_create_quota(db, user)
    bonus_balance = getattr(credit_row, "bonus_balance", 0.0) or 0.0
    
    # Calculate total remaining pool available
    if plan and plan.id == "free":
        free_monthly_used = getattr(credit_row, "free_monthly_used", 0.0) or 0.0
        remaining_monthly = max(0.0, 3000.0 - free_monthly_used)
        total_available = remaining_monthly + bonus_balance
    else:
        # Paid tier: credit.balance (Quota Bank) + unallocated + bonus_balance + cycle balance
        cycle_allowance = plan.credits_per_month / 144.0 if plan else 100.0
        refills_processed = sub_row.refills_processed or 0
        allocated_to_cycles = refills_processed * cycle_allowance
        unallocated_deducted = getattr(sub_row, "unallocated_deducted", 0.0) or 0.0
        unallocated = max(0.0, (plan.credits_per_month if plan else 1000.0) - allocated_to_cycles - (credit_row.balance if credit_row else 0.0) - (sub_row.current_cycle_used if sub_row else 0.0) - unallocated_deducted)
        
        cycle_balance = max(0.0, cycle_allowance - (sub_row.current_cycle_used or 0.0)) if sub_row else 0.0
        quota_bank = (credit_row.balance or 0.0) if credit_row else 0.0
        total_available = quota_bank + unallocated + bonus_balance + cycle_balance
        
    if total_available < credits_cost:
        raise HTTPException(
            status_code=402,
            detail={
                "message": f"Insufficient credits for 3D model generation. This task requires {credits_cost:.1f} credits.",
                "required": credits_cost,
                "available": total_available
            }
        )

    # Build Tripo request body
    url = "https://api.tripo3d.ai/v2/openapi/task"
    headers = {
        "Authorization": f"Bearer {tripo_key}",
        "Content-Type": "application/json"
    }
    
    # Start with all provided non-None parameters from the request
    payload = req.model_dump(exclude_none=True) if hasattr(req, "model_dump") else req.dict(exclude_none=True)

    # Handle model version mapping
    raw_version = payload.pop("model_version", None) or payload.pop("model", None) or "v3.1"
    if not req.type.lower().startswith("animate_"):
        version_mapping = {
            "v3.1": "v3.1-20260211",
            "v3.0": "v3.0-20250812",
            "v2.5": "v2.5-20250123",
            "v2.0": "v2.0-20240919",
            "v1.4": "v1.4-20240625",
            "turbo": "Turbo-v1.0-20250506",
            "p1": "P1-20260311"
        }
        selected_version = version_mapping.get(str(raw_version).lower().strip(), str(raw_version))
        payload["model_version"] = selected_version

    # Set up the file structure if file_token/image_url are present
    file_token = payload.pop("file_token", None)
    image_url = payload.pop("image_url", None)
    
    if file_token:
        payload["file"] = {
            "type": "png",  # Default to png
            "file_token": file_token
        }
    elif image_url:
        payload["file"] = {
            "type": image_url.split(".")[-1].split("?")[0] if "." in image_url else "jpg",
            "url": image_url
        }

    # Proxy to Tripo OpenAPI
    try:
        resp = _requests.post(url, json=payload, headers=headers, timeout=30)
        resp_json = resp.json()
    except Exception as e:
        logger.error("tripo_generation_error", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Failed to submit task to Tripo AI: {str(e)}")

    if resp.status_code != 200 or resp_json.get("code") != 0:
        logger.error("tripo_api_failure", extra={"status": resp.status_code, "response": resp_json})
        msg = resp_json.get("message", "Unknown Tripo API error")
        raise HTTPException(status_code=resp.status_code if resp.status_code == 200 else 400, detail=f"Tripo AI: {msg}")

    # Deduct credits
    try:
        pref_quota = request.headers.get("X-Preferred-Quota", "regular").lower().strip()
        deduct_credits_unallocated_first(db, user, credits_cost, pref_quota)
        logger.info("tripo_billing_success", extra={
            "user_id": user.id,
            "task_type": req.type,
            "credits_cost": credits_cost,
        })
    except Exception as bill_err:
        logger.error("tripo_billing_error", extra={"error": str(bill_err)})

    return resp_json


@router.get("/3d/generations/{task_id}", summary="Check Tripo 3D task status")
def check_3d_task_proxy(
    task_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Blender / Tripo tools are only available from Starter plan (pro) or higher
    from ..db import UserSubscription, Plan
    sub_row = db.query(UserSubscription).filter(UserSubscription.user_id == user.id).first()
    plan = sub_row.plan if sub_row else None
    if not plan and sub_row:
        plan = db.query(Plan).filter(Plan.id == sub_row.plan_id).first()
    if not plan or plan.id not in ("pro", "max", "ultimate"):
        raise HTTPException(
            status_code=403,
            detail="Blender & 3D Tools are only available on the Starter plan (Starter Node) or higher. Please upgrade your subscription."
        )
    import os
    import requests as _requests
    
    tripo_key = request.headers.get("X-Tripo-API-Key") or os.environ.get("TRIPO_API_KEY")
    if not tripo_key:
        raise HTTPException(
            status_code=500,
            detail="Tripo 3D API key is not configured on the server."
        )

    url = f"https://api.tripo3d.ai/v2/openapi/task/{task_id}"
    headers = {
        "Authorization": f"Bearer {tripo_key}"
    }

    try:
        resp = _requests.get(url, headers=headers, timeout=20)
        resp_json = resp.json()
    except Exception as e:
        logger.error("tripo_status_error", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Failed to query status from Tripo AI: {str(e)}")

    return resp_json



