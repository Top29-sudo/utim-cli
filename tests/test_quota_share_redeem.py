import datetime
import pytest
from fastapi import HTTPException

from utim_cli.server.db import SessionLocal, User, Credit, UserSubscription, Plan, RedeemCode, QuotaTransfer, Base, engine, init_db
from utim_cli.server.routes.quota_share_routes import (
    quota_share_info,
    quota_share_preview,
    quota_share_transfer,
    redeem_code_lookup,
    redeem_quota_code,
    QuotaSharePreviewRequest,
    QuotaShareTransferRequest,
    RedeemCodeRequest,
)

@pytest.fixture(autouse=True)
def setup_db():
    init_db(silent=False)
    db = SessionLocal()
    # Seeding plans if not present (handled normally by init_db, but let's be safe)
    if not db.query(Plan).filter(Plan.id == "pro").first():
        pro_plan = Plan(
            id="pro",
            name="pro",
            display_name="Starter Node",
            price_inr=2500,
            credits_per_month=18000,
            allowed_models="all",
            max_context_k=1024
        )
        db.add(pro_plan)
        db.commit()
    db.close()
    yield


def test_quota_share_and_redeem_flow():
    db = SessionLocal()

    # 1. Setup Sender (subscribed user) and Referee
    sender = db.query(User).filter(User.email == "sender@utim.dev").first()
    if sender:
        db.query(RedeemCode).filter(RedeemCode.sender_id == sender.id).delete()
        db.query(QuotaTransfer).filter(QuotaTransfer.sender_id == sender.id).delete()
        db.query(Credit).filter(Credit.user_id == sender.id).delete()
        db.query(UserSubscription).filter(UserSubscription.user_id == sender.id).delete()
        db.delete(sender)

    referee = db.query(User).filter(User.email == "referee@utim.dev").first()
    if referee:
        db.query(RedeemCode).filter(RedeemCode.intended_recipient_id == referee.id).delete()
        db.query(QuotaTransfer).filter(QuotaTransfer.recipient_id == referee.id).delete()
        db.query(Credit).filter(Credit.user_id == referee.id).delete()
        db.delete(referee)

    ineligible_user = db.query(User).filter(User.email == "stranger@utim.dev").first()
    if ineligible_user:
        db.query(Credit).filter(Credit.user_id == ineligible_user.id).delete()
        db.delete(ineligible_user)

    db.commit()

    sender = User(
        email="sender@utim.dev",
        firebase_uid="uid-sender",
        display_name="Sender User",
        referral_code="ref-sender-123"
    )
    db.add(sender)
    db.flush()

    referee = User(
        email="referee@utim.dev",
        firebase_uid="uid-referee",
        display_name="Referee User",
        referrer_id=sender.id
    )
    db.add(referee)
    db.flush()

    ineligible_user = User(
        email="stranger@utim.dev",
        firebase_uid="uid-stranger",
        display_name="Stranger User"
    )
    db.add(ineligible_user)
    db.flush()

    # Credit setup
    sender_credit = Credit(
        user_id=sender.id,
        balance=10000.0, # Quota Bank balance
        bonus_balance=0.0,
        bonus_limit=0.0
    )
    referee_credit = Credit(
        user_id=referee.id,
        balance=0.0,
        bonus_balance=0.0,
        bonus_limit=0.0
    )
    ineligible_credit = Credit(
        user_id=ineligible_user.id,
        balance=0.0,
        bonus_balance=0.0,
        bonus_limit=0.0
    )
    db.add_all([sender_credit, referee_credit, ineligible_credit])

    # Active subscription for sender (Starter Node plan)
    now = datetime.datetime.utcnow()
    sub = UserSubscription(
        user_id=sender.id,
        plan_id="pro",
        status="active",
        current_period_start=now,
        current_period_end=now + datetime.timedelta(days=30),
        refills_processed=0,
        current_cycle_used=0.0
    )
    db.add(sub)
    db.commit()

    # 2. Test get shareable info for sender
    info = quota_share_info(db, sender)
    assert info["shareable_balance"] > 0
    assert len(info["referred_users"]) == 1
    assert info["referred_users"][0]["uid"] == referee.firebase_uid

    # 3. Preview transfer
    preview = quota_share_preview(
        QuotaSharePreviewRequest(recipient_uid="redeem_code_only", amount=5000.0),
        db,
        sender
    )
    assert preview["amount"] == 5000.0
    assert preview["deductions"]["from_quota_bank"] == 5000.0

    # 4. Perform transfer (produces redeem code)
    transfer_res = quota_share_transfer(
        QuotaShareTransferRequest(recipient_uid="redeem_code_only", amount=5000.0),
        db,
        sender
    )
    assert transfer_res["success"] is True
    assert transfer_res["direct_transfer"] is False
    redeem_code_str = transfer_res["redeem_code"]
    assert redeem_code_str.startswith("UTIM-")

    # Check sender balance is deducted
    db.refresh(sender_credit)
    assert sender_credit.balance == 5000.0

    # 5. Look up code
    lookup = redeem_code_lookup(redeem_code_str, db, referee)
    assert lookup["amount"] == 5000.0
    assert lookup["sender_name"] == "Sender User"

    # 6. Verify non-referred (ineligible) user cannot lookup or redeem the code
    with pytest.raises(HTTPException) as exc_info:
        redeem_code_lookup(redeem_code_str, db, ineligible_user)
    assert exc_info.value.status_code == 403

    with pytest.raises(HTTPException) as exc_info:
        redeem_quota_code(RedeemCodeRequest(code=redeem_code_str), db, ineligible_user)
    assert exc_info.value.status_code == 403

    # 7. Referee claims the code
    claim_res = redeem_quota_code(RedeemCodeRequest(code=redeem_code_str), db, referee)
    assert claim_res["success"] is True
    assert claim_res["credits_added"] == 5000.0

    # Verify referee bonus balance is credited
    db.refresh(referee_credit)
    assert referee_credit.bonus_balance == 5000.0

    # 8. Try to redeem already redeemed code
    with pytest.raises(HTTPException) as exc_info:
        redeem_quota_code(RedeemCodeRequest(code=redeem_code_str), db, referee)
    assert exc_info.value.status_code == 409

    # 9. Create another code and verify sender themselves can redeem it
    transfer_res_self = quota_share_transfer(
        QuotaShareTransferRequest(recipient_uid="redeem_code_only", amount=3000.0),
        db,
        sender
    )
    self_redeem_code = transfer_res_self["redeem_code"]

    # Sender claims the code
    claim_self_res = redeem_quota_code(RedeemCodeRequest(code=self_redeem_code), db, sender)
    assert claim_self_res["success"] is True
    assert claim_self_res["credits_added"] == 3000.0

    db.refresh(sender_credit)
    assert sender_credit.bonus_balance == 3000.0

    # 10. Test Direct Transfer Path (direct share)
    # Deduct 1000.0 remaining credits directly to referee
    direct_res = quota_share_transfer(
        QuotaShareTransferRequest(recipient_uid=referee.firebase_uid, amount=1000.0),
        db,
        sender
    )
    assert direct_res["success"] is True
    assert direct_res["direct_transfer"] is True
    assert direct_res["redeem_code"] is None

    # Check recipient bonus balance is immediately updated (previous 5000.0 + new 1000.0 = 6000.0)
    db.refresh(referee_credit)
    assert referee_credit.bonus_balance == 6000.0

    # Check sender balance is deducted (2000.0 - 1000.0 = 1000.0)
    db.refresh(sender_credit)
    assert sender_credit.balance == 1000.0

    # Clean up
    db.query(RedeemCode).filter(RedeemCode.sender_id == sender.id).delete()
    db.query(QuotaTransfer).filter(QuotaTransfer.sender_id == sender.id).delete()
    db.query(Credit).filter(Credit.user_id.in_([sender.id, referee.id, ineligible_user.id])).delete()
    db.query(UserSubscription).filter(UserSubscription.user_id == sender.id).delete()
    db.delete(sender)
    db.delete(referee)
    db.delete(ineligible_user)
    db.commit()
    db.close()
