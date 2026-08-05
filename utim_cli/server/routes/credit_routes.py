"""
Routes: /credits & /transactions — balance queries and ledger
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db, User, Transaction, Credit, PaymentOrder
from ..auth import get_current_user, get_current_firebase_user

router = APIRouter(tags=["credits"])
logger = logging.getLogger("utim.routes.credits")


class TopupRequest(BaseModel):
    amount: float  # Top-up amount in USD
    currency: Optional[str] = "INR"


class VerifyPaymentRequest(BaseModel):
    razorpay_payment_id: Optional[str] = None
    razorpay_signature: Optional[str] = None


@router.get("/credits/balance", summary="Get your current credit balance")
def balance(user: User = Depends(get_current_user)):
    return {
        "balance": user.credits.balance if user.credits else 0,
        "total_spent": user.credits.total_spent if user.credits else 0,
        "total_topped_up": user.credits.total_topped_up if user.credits else 0,
        "currency": "UTIM",
    }


@router.get("/credits/transactions", summary="Paginated transaction ledger")
def transactions(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    kind: Optional[str] = Query(None, description="Filter by kind: topup | deduction | refund"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Transaction).filter(Transaction.user_id == user.id)
    if kind:
        q = q.filter(Transaction.kind == kind)
    q = q.order_by(Transaction.created_at.desc()).offset(offset).limit(limit)
    rows = q.all()
    return {
        "total": db.query(Transaction).filter(Transaction.user_id == user.id).count(),
        "results": [
            {
                "id": tx.id,
                "kind": tx.kind,
                "amount": tx.amount,
                "balance_after": tx.balance_after,
                "description": tx.description,
                "session_id": tx.session_id,
                "model_id": tx.model_id,
                "input_tokens": tx.input_tokens,
                "output_tokens": tx.output_tokens,
                "created_at": tx.created_at.isoformat(),
            }
            for tx in rows
        ],
    }


@router.get("/api/credits", summary="Get user credits in USD")
def api_credits(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_firebase_user)
):
    balance_usd = (user.credits.balance / 1000.0) if user.credits else 0.0
    return {"balance": balance_usd}


@router.post("/api/credits/topup", summary="Create payment order for top-up")
def api_credits_topup(
    req: TopupRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_firebase_user)
):
    key_id = os.environ.get("RAZORPAY_KEY_ID", "")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "")
    
    amount_usd = req.amount
    if amount_usd < 2:
        raise HTTPException(status_code=400, detail="Minimum top-up amount is $2.00")
    if amount_usd > 4500:
        raise HTTPException(status_code=400, detail="Maximum top-up amount is $4,500.00")

    # Sliding scale markup rate (varies from 2% to 5%, scaled for $2 to $4,500 range)
    if amount_usd < 50:
        markup_rate = 1.02
    elif amount_usd < 250:
        markup_rate = 1.03
    elif amount_usd < 1000:
        markup_rate = 1.04
    else:
        markup_rate = 1.05

    currency = (req.currency or "INR").upper().strip()
    
    if currency == "USD":
        amount_usd_charged = amount_usd * markup_rate
        amount_paise = int(amount_usd_charged * 100)  # cents
        amount_inr = 0.0
    else:
        from ..exchange_rate import ExchangeRateStore
        usd_to_inr = ExchangeRateStore.get_rate()
        amount_inr = amount_usd * usd_to_inr * markup_rate
        amount_paise = int(amount_inr * 100)  # paise

    if not key_id or key_id == "mock_key_id":
        order_id = f"order_mock_{uuid.uuid4().hex[:12]}"
        
        payment_order = PaymentOrder(
            id=str(uuid.uuid4()),
            user_id=user.id,
            order_id=order_id,
            amount=amount_usd,
            amount_inr=amount_inr if currency != "USD" else amount_usd_charged,
            currency=currency,
            status="created"
        )
        db.add(payment_order)
        db.commit()
        
        return {
            "success": True,
            "orderId": order_id,
            "keyId": "mock_key_id",
            "amount": amount_paise,
            "currency": currency
        }
        
    import requests
    import base64
    
    url = "https://api.razorpay.com/v1/orders"
    auth_str = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_str}",
        "Content-Type": "application/json"
    }
    payload = {
        "amount": amount_paise,
        "currency": currency,
        "receipt": f"receipt_{uuid.uuid4().hex[:12]}",
        "notes": {
            "user_id": user.id,
            "amount_usd": str(amount_usd)
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code != 200:
            logger.error(f"razorpay_order_create_error_body: {response.text}")
            response.raise_for_status()
        res_data = response.json()
        order_id = res_data["id"]
        
        payment_order = PaymentOrder(
            id=str(uuid.uuid4()),
            user_id=user.id,
            order_id=order_id,
            amount=amount_usd,
            amount_inr=amount_inr if currency != "USD" else amount_usd_charged,
            currency=currency,
            status="created"
        )
        db.add(payment_order)
        db.commit()
        
        return {
            "success": True,
            "orderId": order_id,
            "keyId": key_id,
            "amount": amount_paise,
            "currency": currency
        }
    except Exception as e:
        err_msg = str(e)
        if hasattr(e, "response") and e.response is not None:
            err_msg += f" | Response: {e.response.text}"
        logger.error(f"razorpay_order_create_error: {err_msg}")
        raise HTTPException(status_code=500, detail=f"Failed to create payment order: {err_msg}")


@router.post("/api/credits/verify/{chargeId}", summary="Verify top-up payment order")
def api_credits_verify(
    chargeId: str,
    req: VerifyPaymentRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_firebase_user)
):
    payment_order = db.query(PaymentOrder).filter(PaymentOrder.order_id == chargeId).first()
    if not payment_order:
        raise HTTPException(status_code=404, detail="Payment order not found")
        
    if payment_order.status == "completed":
        return {"success": True, "status": "completed"}
        
    key_id = os.environ.get("RAZORPAY_KEY_ID", "")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "")
    
    mock_env = os.environ.get("UTIM_MOCK_PAYMENTS", "false").lower() == "true"
    is_mock = mock_env and (chargeId.startswith("order_mock") or key_id == "mock_key_id")
    
    if not is_mock and (not key_id or not key_secret):
        raise HTTPException(status_code=500, detail="Payment verification keys not configured")
        
    if not is_mock:
        import hmac
        import hashlib
        
        msg = f"{chargeId}|{req.razorpay_payment_id}"
        generated_sig = hmac.new(
            key_secret.encode('utf-8'),
            msg.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        if generated_sig != req.razorpay_signature:
            logger.warning("payment_signature_mismatch", extra={"order_id": chargeId})
            raise HTTPException(status_code=400, detail="Signature verification failed.")
            
    payment_order.status = "completed"
    payment_order.razorpay_payment_id = req.razorpay_payment_id
    payment_order.razorpay_signature = req.razorpay_signature
    
    credits_to_add = payment_order.amount * 1000.0
    
    from ..db import UserSubscription, get_max_bonus_limit
    
    if not user.credits:
        user.credits = Credit(user_id=user.id, balance=0.0, bonus_balance=0.0, bonus_limit=0.0, total_topped_up=0.0)
        db.add(user.credits)
        
    # Ensure bonus fields exist
    if not hasattr(user.credits, "bonus_balance") or user.credits.bonus_balance is None:
        user.credits.bonus_balance = 0.0
    if not hasattr(user.credits, "bonus_limit") or user.credits.bonus_limit is None:
        user.credits.bonus_limit = 0.0
        
    # Fetch active plan to determine max bonus quota limit
    sub = db.query(UserSubscription).filter(
        UserSubscription.user_id == user.id,
        UserSubscription.status == "active"
    ).first()
    plan_id = sub.plan_id if sub else "free"
    max_bonus = get_max_bonus_limit(plan_id)

    user.credits.bonus_balance = min(max_bonus, user.credits.bonus_balance + credits_to_add)
    user.credits.bonus_limit = min(max_bonus, user.credits.bonus_limit + credits_to_add)
    user.credits.total_topped_up += credits_to_add
    new_balance = user.credits.balance + user.credits.bonus_balance
    
    tx = Transaction(
        id=str(uuid.uuid4()),
        user_id=user.id,
        kind="topup",
        amount=credits_to_add,
        balance_after=new_balance,
        description=f"Online payment top-up of ${payment_order.amount:.2f}"
    )
    db.add(tx)
    db.commit()
    
    logger.info("payment_order_completed", extra={
        "user_id": user.id,
        "amount_usd": payment_order.amount,
        "credits_added": credits_to_add,
        "new_balance": new_balance
    })
    
    return {"success": True, "status": "completed", "bonus_credits_added": credits_to_add}

