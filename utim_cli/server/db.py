"""
UTIM Production Server — Database Models
SQLAlchemy 2.x ORM with PostgreSQL support.
"""
from __future__ import annotations

import datetime
import os
import uuid
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Float,
    ForeignKey, Index, Integer, JSON, String, Text, create_engine
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship, backref, sessionmaker

# ── Connection ────────────────────────────────────────────────────────────────

_raw_url = os.environ.get("DATABASE_URL", "sqlite:///utim_production.db")
# Railway exports postgres:// but SQLAlchemy 1.4+ requires postgresql://
DATABASE_URL = _raw_url.replace("postgres://", "postgresql://", 1)

# Use connection pooling for Postgres, simple for SQLite
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {"connect_timeout": 5}
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args=_connect_args,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)




# ── ORM Base ──────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


class EmailOTP(Base):
    __tablename__ = "email_otps"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), nullable=False, index=True)
    otp_code = Column(String(6), nullable=False)
    verified = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<EmailOTP email={self.email} verified={self.verified}>"


# ── Tables ────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    api_key = Column(String(64), unique=True, nullable=False, index=True,
                     default=lambda: f"utim-{uuid.uuid4().hex}")
    display_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    last_project_folder = Column(Text, nullable=True)
    firebase_uid = Column(String(128), nullable=True, index=True)
    referrer_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    referral_code = Column(String(50), unique=True, nullable=False, default=lambda: uuid.uuid4().hex[:8])

    referrer = relationship("User", remote_side=[id], backref="referees")
    credits = relationship("Credit", back_populates="user", uselist=False, cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    subscription = relationship("UserSubscription", back_populates="user", uselist=False, cascade="all, delete-orphan")
    quota_usages = relationship("QuotaUsage", back_populates="user", cascade="all, delete-orphan")
    payment_orders = relationship("PaymentOrder", back_populates="user", cascade="all, delete-orphan")
    feedbacks = relationship("Feedback", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User {self.email}>"


class Plan(Base):
    __tablename__ = "plans"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(50), unique=True, nullable=False)          # "free", "hobby", "pro", "max", "ultimate"
    display_name = Column(String(100), nullable=False)
    price_inr = Column(Integer, default=0, nullable=False)
    credits_per_month = Column(Integer, nullable=False)
    allowed_models = Column(Text, default="free", nullable=False)   # "free" | "all" | comma-separated list
    max_context_k = Column(Integer, default=128, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    subscriptions = relationship("UserSubscription", back_populates="plan")

    def __repr__(self) -> str:
        return f"<Plan name={self.name} limit={self.credits_per_month}>"


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    plan_id = Column(String(36), ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False)
    status = Column(String(20), default="active", nullable=False)   # active|cancelled|past_due
    current_period_start = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    current_period_end = Column(DateTime, nullable=False)
    razorpay_subscription_id = Column(String(255), nullable=True)
    razorpay_customer_id = Column(String(255), nullable=True)
    refills_processed = Column(Integer, default=0, nullable=False)
    current_cycle_used = Column(Float, default=0.0, nullable=False)
    last_refill_at = Column(DateTime, nullable=True)
    # Overrides the default per-cycle credit allocation after a quota-share deduction
    refill_rate_override = Column(Float, nullable=True)
    unallocated_deducted = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="subscription")
    plan = relationship("Plan", back_populates="subscriptions")

    @property
    def refills_used(self) -> int:
        return self.refills_processed or 0

    @refills_used.setter
    def refills_used(self, value: int):
        self.refills_processed = value

    def __repr__(self) -> str:
        return f"<UserSubscription user={self.user_id} plan={self.plan_id} status={self.status}>"


class QuotaUsage(Base):
    __tablename__ = "quota_usage"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    credits_used = Column(Float, default=0.0, nullable=False)
    credits_limit = Column(Integer, nullable=False)
    reset_at = Column(DateTime, nullable=False)

    user = relationship("User", back_populates="quota_usages")

    def __repr__(self) -> str:
        return f"<QuotaUsage user={self.user_id} used={self.credits_used}/{self.credits_limit}>"


class Credit(Base):
    __tablename__ = "credits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    balance = Column(Float, default=0.0, nullable=False)
    bonus_balance = Column(Float, default=0.0, nullable=False)
    bonus_limit = Column(Float, default=0.0, nullable=False)
    total_spent = Column(Float, default=0.0, nullable=False)
    total_topped_up = Column(Float, default=0.0, nullable=False)
    # Free plan: cumulative credits used in the current monthly cycle (3000 cap)
    free_monthly_used = Column(Float, default=0.0, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow,
                        onupdate=datetime.datetime.utcnow)

    user = relationship("User", back_populates="credits")

    def __repr__(self) -> str:
        return f"<Credit user={self.user_id} balance={self.balance:.2f}>"


class Transaction(Base):
    """Immutable ledger record for every credit movement."""
    __tablename__ = "transactions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(32), nullable=False)       # "topup" | "deduction" | "refund"
    amount = Column(Float, nullable=False)          # positive = credit, negative = deduction
    balance_after = Column(Float, nullable=False)
    description = Column(String(512), nullable=True)
    session_id = Column(String(36), nullable=True)  # linked conversation if a deduction
    model_id = Column(String(128), nullable=True)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)

    user = relationship("User", back_populates="transactions")

    __table_args__ = (
        Index("ix_transactions_user_created", "user_id", "created_at"),
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    model_id = Column(String(128), nullable=True)
    title = Column(String(255), nullable=True)
    # Store as TEXT JSON for SQLite compat; Postgres uses JSONB via override below
    messages = Column(Text, nullable=False, default="[]")
    turn_history = Column(Text, nullable=True, default="[]")
    redo_history = Column(Text, nullable=True, default="[]")
    token_usage_input = Column(BigInteger, default=0)
    token_usage_output = Column(BigInteger, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow,
                        onupdate=datetime.datetime.utcnow)

    user = relationship("User", back_populates="conversations")


class PaymentOrder(Base):
    __tablename__ = "payment_orders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id = Column(String(255), unique=True, nullable=False, index=True)
    amount = Column(Float, nullable=False)  # in USD
    amount_inr = Column(Float, nullable=True) # equivalent in INR
    currency = Column(String(10), default="INR", nullable=False)
    status = Column(String(32), default="created", nullable=False)  # created | completed | failed | cancelled
    razorpay_payment_id = Column(String(255), nullable=True)
    razorpay_signature = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="payment_orders")


class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    chat_history = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="feedbacks")


class DeviceAuthCode(Base):
    """Single-use login token for the Device Authorization Flow (RFC 8628 inspired).
    
    Flow:
      1. CLI POSTs /auth/device/request → gets device_code + user_code + verify_url
      2. CLI polls /auth/device/poll?device_code=... every 3 seconds
      3. User visits verify_url, signs in via Firebase, clicks Authorize
      4. Server stores api_key in this row, sets status='authorized'
      5. CLI poll response returns api_key, row is immediately invalidated
    """
    __tablename__ = "device_auth_codes"

    id          = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_code = Column(String(64), unique=True, nullable=False, index=True,
                         default=lambda: uuid.uuid4().hex)          # secret, only CLI sees this
    user_code   = Column(String(9),  unique=True, nullable=False, index=True)  # e.g. "DFRG-TYHJ"
    status      = Column(String(16), default="pending", nullable=False)        # pending|authorized|expired
    api_key     = Column(String(64), nullable=True)                            # populated on authorization
    user_id     = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    expires_at  = Column(DateTime,   nullable=False)
    created_at  = Column(DateTime,   default=datetime.datetime.utcnow, nullable=False)


class EmotionVector(Base):
    __tablename__ = "emotion_vectors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, index=True)
    conversation_id = Column(Integer, nullable=True, index=True)
    message_number = Column(Integer, nullable=True)
    valence = Column(Float, nullable=True)
    arousal = Column(Float, nullable=True)
    control = Column(Float, nullable=True)
    engagement = Column(Float, nullable=True)
    trust = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class CognitiveState(Base):
    __tablename__ = "cognitive_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, index=True)
    conversation_id = Column(Integer, nullable=True, index=True)
    message_number = Column(Integer, nullable=True)
    cognitive_load = Column(Float, nullable=True)
    goal_clarity = Column(Float, nullable=True)
    momentum = Column(Float, nullable=True)
    agency = Column(Float, nullable=True)
    decision_fatigue = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class LinguisticSignal(Base):
    __tablename__ = "linguistic_signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, index=True)
    conversation_id = Column(Integer, nullable=True, index=True)
    message_number = Column(Integer, nullable=True)
    hedge_count = Column(Integer, default=0)
    fragment_count = Column(Integer, default=0)
    clarifying_questions = Column(Integer, default=0)
    one_word_response_count = Column(Integer, default=0)
    repetition_rate = Column(Float, default=0.0)
    distancing_markers = Column(Integer, default=0)
    preemptive_defense_count = Column(Integer, default=0)
    reassurance_count = Column(Integer, default=0)
    conditional_phrase_count = Column(Integer, default=0)
    passive_voice_ratio = Column(Float, default=0.0)
    average_sentence_length = Column(Float, default=0.0)
    average_word_count = Column(Float, default=0.0)
    sentence_length_variance = Column(Float, default=0.0)
    clause_density = Column(Float, default=0.0)
    punctuation_entropy = Column(Float, default=0.0)
    rapid_fire_questions = Column(Integer, default=0)
    justification_density = Column(Float, default=0.0)
    response_latency = Column(Integer, default=0)
    response_latency_delta = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class MetaState(Base):
    __tablename__ = "meta_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, index=True)
    conversation_id = Column(Integer, nullable=True, index=True)
    message_number = Column(Integer, nullable=True)
    self_awareness = Column(Float, nullable=True)
    emotional_regulation = Column(Float, nullable=True)
    self_minimization = Column(Float, nullable=True)
    defensive_thinking = Column(Float, nullable=True)
    over_control = Column(Float, nullable=True)
    apologetic_tone = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class PressureTrajectory(Base):
    __tablename__ = "pressure_trajectories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, index=True)
    conversation_id = Column(Integer, nullable=True)
    current_pressure = Column(Float, nullable=True)
    direction = Column(String(50), nullable=True)
    acceleration = Column(String(50), nullable=True)
    volatility = Column(Float, nullable=True)
    projected_next_state = Column(String(50), nullable=True)
    time_to_escalation = Column(Integer, nullable=True)
    measurement_depth = Column(Integer, nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class AdaptationDirective(Base):
    __tablename__ = "adaptation_directives"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, index=True)
    conversation_id = Column(Integer, nullable=True)
    message_number = Column(Integer, nullable=True)
    direction = Column(String(50), nullable=True)
    magnitude = Column(String(50), nullable=True)
    mode = Column(String(50), nullable=True)
    timing = Column(String(50), nullable=True)
    reasoning = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    is_reversible = Column(Boolean, nullable=True)
    safety_risk = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class UserBaseline(Base):
    __tablename__ = "user_baselines"

    user_id = Column(String(255), primary_key=True)
    avg_word_count = Column(Float, default=0.0)
    avg_sentence_length = Column(Float, default=0.0)
    typical_hedging_rate = Column(Float, default=0.0)
    typical_question_density = Column(Float, default=0.0)
    typical_passive_voice_ratio = Column(Float, default=0.0)
    typical_response_latency = Column(Integer, default=0)
    typical_politeness_score = Column(Float, default=0.5)
    typical_verbosity_score = Column(Float, default=0.5)
    average_valence = Column(Float, default=0.0)
    average_arousal = Column(Float, default=0.0)
    message_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)


class ConstraintHypothesis(Base):
    __tablename__ = "constraint_hypotheses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, index=True)
    type = Column(String(50), nullable=True)
    confidence = Column(Float, nullable=True)
    inferred_from = Column(Text, nullable=True)
    detection_count = Column(Integer, default=1)
    last_detected = Column(DateTime, default=datetime.datetime.utcnow)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class ValueAlignment(Base):
    __tablename__ = "value_alignments"

    user_id = Column(String(255), primary_key=True)
    fairness = Column(Float, default=0.5)
    efficiency = Column(Float, default=0.5)
    elegance = Column(Float, default=0.5)
    control_need = Column(Float, default=0.5)
    safety = Column(Float, default=0.5)
    simplicity = Column(Float, default=0.5)
    autonomy = Column(Float, default=0.5)
    transparency = Column(Float, default=0.5)
    most_important = Column(String(50), nullable=True)
    detected_from = Column(Text, default="[]")
    detection_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)


class SessionState(Base):
    __tablename__ = "session_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, index=True)
    conversation_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class EmailTracking(Base):
    __tablename__ = "email_tracking"

    user_id = Column(String(255), primary_key=True)
    email = Column(String(255), nullable=True)
    display_name = Column(String(255), nullable=True)
    welcome_email_sent = Column(Boolean, default=False)
    low_quota_email_sent_at = Column(DateTime, nullable=True)
    exhausted_email_sent_at = Column(DateTime, nullable=True)
    bonus_email_sent_at = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_welcome_back_sent_at = Column(DateTime, nullable=True)
    consecutive_empty_responses = Column(Integer, default=0)
    last_error_email_sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)


class UsedEmailBonus(Base):
    """Tracks email addresses that have claimed a first purchase bonus for specific plans.
    
    Importantly, this table does NOT have a foreign key to the users table, and is not cascading.
    This prevents users from deleting their accounts and creating new ones to re-claim bonuses.
    """
    __tablename__ = "used_email_bonuses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=False, index=True)
    plan_id = Column(String(50), nullable=False)
    claimed_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class QuotaTransfer(Base):
    """
    Immutable audit record for every quota-share transfer between users.

    Deduction breakdown:
      from_quota_bank    — credits taken from sender's Quota Bank.
      from_current_cycle — credits taken from sender's active 5-hour cycle balance.
      from_unallocated   — credits taken from sender's unallocated future-cycle pool.
    """
    __tablename__ = "quota_transfers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sender_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    amount = Column(Float, nullable=False)                      # total credits transferred
    from_quota_bank = Column(Float, default=0.0, nullable=False)
    from_current_cycle = Column(Float, default=0.0, nullable=False)
    from_unallocated = Column(Float, default=0.0, nullable=False)
    billing_cycle_start = Column(DateTime, nullable=True)       # billing period when transfer occurred
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)

    sender = relationship("User", foreign_keys=[sender_id], backref="sent_quota_transfers")
    recipient = relationship("User", foreign_keys=[recipient_id], backref="received_quota_transfers")

    __table_args__ = (
        Index("ix_quota_transfers_sender_created", "sender_id", "created_at"),
        Index("ix_quota_transfers_recipient_created", "recipient_id", "created_at"),
    )


class RedeemCode(Base):
    """
    Model representing generated redeem codes from credit sharing.
    Claimable by directly referred users of the sender, or the sender themselves.
    Redeemed credits are added to the recipient's bonus_balance.
    """
    __tablename__ = "redeem_codes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(32), unique=True, nullable=False, index=True)
    sender_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    intended_recipient_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    amount = Column(Float, nullable=False)
    from_quota_bank = Column(Float, default=0.0, nullable=False)
    from_current_cycle = Column(Float, default=0.0, nullable=False)
    from_unallocated = Column(Float, default=0.0, nullable=False)
    billing_cycle_start = Column(DateTime, nullable=True)
    is_redeemed = Column(Boolean, default=False, nullable=False)
    redeemed_by_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    redeemed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    sender = relationship("User", foreign_keys=[sender_id], backref="created_redeem_codes")
    intended_recipient = relationship("User", foreign_keys=[intended_recipient_id], backref="intended_redeem_codes")
    redeemed_by = relationship("User", foreign_keys=[redeemed_by_id], backref="redeemed_codes")


# ── Bootstrap ─────────────────────────────────────────────────────────────────

def init_db(silent: bool = True) -> None:
    """Create all tables and ensure the schema is up to date."""
    import logging as _logging
    _mig_log = _logging.getLogger("utim.db.migration")

    def _print(msg: str):
        if not silent:
            print(msg)
    
    _print("[DB INIT] init_db() starting...")
    try:
        _print(f"[DB INIT] Connecting to DB: {engine.url.drivername} (host: {engine.url.host})")
        Base.metadata.create_all(bind=engine)
        _print("[DB INIT] create_all() completed.")
    except Exception as exc:
        _print(f"[DB INIT] create_all() failed: {exc}")
        _mig_log.warning(f"Skipping table creation (database might be unavailable): {exc}")
        return
    
    # Run manual migrations for missing columns
    # Each ALTER runs in its OWN transaction so one failure doesn't block the rest.
    from sqlalchemy import text, inspect as sa_inspect

    # Ensure referral_discounts table exists (defined in referral_routes, not imported into Base yet)
    try:
        from .routes.referral_routes import ReferralDiscount
        Base.metadata.create_all(bind=engine, tables=[ReferralDiscount.__table__])
    except Exception as _ref_tbl_exc:
        _print(f"[DB INIT] referral_discounts table init note: {_ref_tbl_exc}")

    is_postgres = DATABASE_URL.startswith("postgresql")

    try:
        inspector = sa_inspect(engine)
        existing_tables = inspector.get_table_names()
    except Exception as inspect_exc:
        _print(f"[DB INIT] DB inspection failed (might be normal on new DB): {inspect_exc}")
        existing_tables = []

    def _col_exists(table_name: str, col_name: str) -> bool:
        if table_name not in existing_tables:
            return False
        try:
            columns = [c["name"] for c in inspector.get_columns(table_name)]
            return col_name in columns
        except Exception:
            return False

    def _run_migration(table_name: str, col_name: str, sql: str, label: str):
        if _col_exists(table_name, col_name):
            _print(f"[DB INIT] Column {table_name}.{col_name} already exists. Skipping.")
            return
        
        _print(f"[DB INIT] Running migration: {label}")
        try:
            with engine.begin() as _conn:
                if is_postgres:
                    # Never hang startup for lock queues: fail fast if blocked for > 3s
                    _conn.execute(text("SET lock_timeout = 3000"))
                _conn.execute(text(sql))
            _print(f"[DB INIT] Migration OK: {label}")
            _mig_log.info(f"Migration OK: {label}")
        except Exception as _exc:
            _print(f"[DB INIT] Migration skipped/failed ({label}): {_exc}")
            _mig_log.debug(f"Migration skipped ({label}): {_exc}")

    # Ensure quota_transfers table exists
    try:
        Base.metadata.create_all(bind=engine, tables=[QuotaTransfer.__table__])
    except Exception as _qt_exc:
        _print(f"[DB INIT] quota_transfers table init note: {_qt_exc}")

    # Ensure redeem_codes table exists
    try:
        Base.metadata.create_all(bind=engine, tables=[RedeemCode.__table__])
    except Exception as _rc_exc:
        _print(f"[DB INIT] redeem_codes table init note: {_rc_exc}")

    if is_postgres:
        _print("[DB INIT] Postgres detected. Running ALTER TABLE migrations if needed.")
        # Drop NOT NULL constraints to support general redeem codes
        try:
            with engine.begin() as _conn:
                _conn.execute(text("SET lock_timeout = 3000"))
                _conn.execute(text("ALTER TABLE quota_transfers ALTER COLUMN recipient_id DROP NOT NULL"))
                _conn.execute(text("ALTER TABLE redeem_codes ALTER COLUMN intended_recipient_id DROP NOT NULL"))
            _print("[DB INIT] PostgreSQL ALTER COLUMN DROP NOT NULL constraints OK")
        except Exception as _exc:
            _print(f"[DB INIT] PostgreSQL ALTER COLUMN DROP NOT NULL constraints failed/skipped: {_exc}")

        _run_migration("credits", "free_monthly_used", "ALTER TABLE credits ADD COLUMN IF NOT EXISTS free_monthly_used FLOAT DEFAULT 0.0 NOT NULL", "postgres add free_monthly_used")
        _run_migration("users", "firebase_uid", "ALTER TABLE users ADD COLUMN IF NOT EXISTS firebase_uid VARCHAR(128)", "postgres add firebase_uid")
        _run_migration("users", "referrer_id", "ALTER TABLE users ADD COLUMN IF NOT EXISTS referrer_id VARCHAR(36)", "postgres add referrer_id")
        _run_migration("users", "referral_code", "ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_code VARCHAR(50)", "postgres add referral_code")
        _run_migration("feedbacks", "chat_history", "ALTER TABLE feedbacks ADD COLUMN IF NOT EXISTS chat_history TEXT", "postgres add chat_history")
        _run_migration("user_subscriptions", "refill_rate_override", "ALTER TABLE user_subscriptions ADD COLUMN IF NOT EXISTS refill_rate_override FLOAT", "postgres add refill_rate_override")
        _run_migration("user_subscriptions", "unallocated_deducted", "ALTER TABLE user_subscriptions ADD COLUMN IF NOT EXISTS unallocated_deducted FLOAT DEFAULT 0.0 NOT NULL", "postgres add unallocated_deducted")
        _run_migration("marketplace_listings", "payment_type", "ALTER TABLE marketplace_listings ADD COLUMN IF NOT EXISTS payment_type VARCHAR(32) DEFAULT 'one_time'", "postgres add payment_type")
        _run_migration("marketplace_listings", "subscription_interval", "ALTER TABLE marketplace_listings ADD COLUMN IF NOT EXISTS subscription_interval VARCHAR(16)", "postgres add subscription_interval")
        _run_migration("marketplace_listings", "razorpay_plan_id", "ALTER TABLE marketplace_listings ADD COLUMN IF NOT EXISTS razorpay_plan_id VARCHAR(128)", "postgres add razorpay_plan_id")
        _run_migration("seller_withdrawals", "upi_id", "ALTER TABLE seller_withdrawals ADD COLUMN IF NOT EXISTS upi_id VARCHAR(128)", "postgres add upi_id")
        _run_migration("seller_withdrawals", "account_number", "ALTER TABLE seller_withdrawals ADD COLUMN IF NOT EXISTS account_number VARCHAR(64)", "postgres add account_number")
        _run_migration("seller_withdrawals", "account_name", "ALTER TABLE seller_withdrawals ADD COLUMN IF NOT EXISTS account_name VARCHAR(128)", "postgres add account_name")
        _run_migration("seller_withdrawals", "ifsc_code", "ALTER TABLE seller_withdrawals ADD COLUMN IF NOT EXISTS ifsc_code VARCHAR(32)", "postgres add ifsc_code")
    else:
        # SQLite: no IF NOT EXISTS on ADD COLUMN, swallow duplicate errors
        _run_migration("user_subscriptions", "refills_processed", "ALTER TABLE user_subscriptions ADD COLUMN refills_processed INTEGER DEFAULT 0 NOT NULL", "sqlite add refills_processed")
        _run_migration("user_subscriptions", "last_refill_at", "ALTER TABLE user_subscriptions ADD COLUMN last_refill_at TIMESTAMP", "sqlite add last_refill_at")
        _run_migration("user_subscriptions", "current_cycle_used", "ALTER TABLE user_subscriptions ADD COLUMN current_cycle_used FLOAT DEFAULT 0.0 NOT NULL", "sqlite add current_cycle_used")
        _run_migration("user_subscriptions", "refill_rate_override", "ALTER TABLE user_subscriptions ADD COLUMN refill_rate_override FLOAT", "sqlite add refill_rate_override")
        _run_migration("user_subscriptions", "unallocated_deducted", "ALTER TABLE user_subscriptions ADD COLUMN unallocated_deducted FLOAT DEFAULT 0.0 NOT NULL", "sqlite add unallocated_deducted")
        _run_migration("credits", "bonus_balance", "ALTER TABLE credits ADD COLUMN bonus_balance FLOAT DEFAULT 0.0 NOT NULL", "sqlite add bonus_balance")
        _run_migration("credits", "bonus_limit", "ALTER TABLE credits ADD COLUMN bonus_limit FLOAT DEFAULT 0.0 NOT NULL", "sqlite add bonus_limit")
        _run_migration("credits", "free_monthly_used", "ALTER TABLE credits ADD COLUMN free_monthly_used FLOAT DEFAULT 0.0 NOT NULL", "sqlite add free_monthly_used")
        _run_migration("email_tracking", "low_quota_email_sent_at", "ALTER TABLE email_tracking ADD COLUMN low_quota_email_sent_at TIMESTAMP", "sqlite add low_quota_email_sent_at")
        _run_migration("email_tracking", "exhausted_email_sent_at", "ALTER TABLE email_tracking ADD COLUMN exhausted_email_sent_at TIMESTAMP", "sqlite add exhausted_email_sent_at")
        _run_migration("email_tracking", "bonus_email_sent_at", "ALTER TABLE email_tracking ADD COLUMN bonus_email_sent_at TIMESTAMP", "sqlite add bonus_email_sent_at")
        _run_migration("users", "last_project_folder", "ALTER TABLE users ADD COLUMN last_project_folder TEXT", "sqlite add last_project_folder")
        _run_migration("users", "firebase_uid", "ALTER TABLE users ADD COLUMN firebase_uid VARCHAR(128)", "sqlite add firebase_uid")
        _run_migration("users", "referrer_id", "ALTER TABLE users ADD COLUMN referrer_id VARCHAR(36)", "sqlite add referrer_id")
        _run_migration("users", "referral_code", "ALTER TABLE users ADD COLUMN referral_code VARCHAR(50)", "sqlite add referral_code")
        _run_migration("feedbacks", "chat_history", "ALTER TABLE feedbacks ADD COLUMN chat_history TEXT", "sqlite add feedbacks chat_history")
        _run_migration("marketplace_listings", "payment_type", "ALTER TABLE marketplace_listings ADD COLUMN payment_type VARCHAR(32) DEFAULT 'one_time'", "sqlite add payment_type")
        _run_migration("marketplace_listings", "subscription_interval", "ALTER TABLE marketplace_listings ADD COLUMN subscription_interval VARCHAR(16)", "sqlite add subscription_interval")
        _run_migration("marketplace_listings", "razorpay_plan_id", "ALTER TABLE marketplace_listings ADD COLUMN razorpay_plan_id VARCHAR(128)", "sqlite add razorpay_plan_id")
        _run_migration("seller_withdrawals", "upi_id", "ALTER TABLE seller_withdrawals ADD COLUMN upi_id VARCHAR(128)", "sqlite add upi_id")
        _run_migration("seller_withdrawals", "account_number", "ALTER TABLE seller_withdrawals ADD COLUMN account_number VARCHAR(64)", "sqlite add account_number")
        _run_migration("seller_withdrawals", "account_name", "ALTER TABLE seller_withdrawals ADD COLUMN account_name VARCHAR(128)", "sqlite add account_name")
        _run_migration("seller_withdrawals", "ifsc_code", "ALTER TABLE seller_withdrawals ADD COLUMN ifsc_code VARCHAR(32)", "sqlite add ifsc_code")
        
    # Seed the plans if they don't exist
    _print("[DB INIT] Seeding plans checking...")
    db = SessionLocal()
    try:
        free_plan = db.query(Plan).filter(Plan.id == "free").first()
        _print(f"[DB INIT] Free plan query done. Exists: {bool(free_plan)}")
        if not free_plan:
            _print("[DB INIT] Creating new plans...")
            plans = [
                Plan(
                    id="free",
                    name="free",
                    display_name="Free",
                    price_inr=0,
                    credits_per_month=1000,
                    allowed_models="free",
                    max_context_k=128
                ),
                Plan(
                    id="hobby",
                    name="hobby",
                    display_name="Hobbyist Node",
                    price_inr=700,
                    credits_per_month=4000,
                    allowed_models="all",
                    max_context_k=256
                ),
                Plan(
                    id="pro",
                    name="pro",
                    display_name="Starter Node",
                    price_inr=2500,
                    credits_per_month=18000,
                    allowed_models="all",
                    max_context_k=1024
                ),
                Plan(
                    id="max",
                    name="max",
                    display_name="Professional Core",
                    price_inr=5500,
                    credits_per_month=45000,
                    allowed_models="all",
                    max_context_k=1024
                ),
                Plan(
                    id="ultimate",
                    name="ultimate",
                    display_name="MAX Node",
                    price_inr=11000,
                    credits_per_month=90000,
                    allowed_models="all",
                    max_context_k=1024
                )
            ]
            db.add_all(plans)
            db.commit()
        else:
            # Delete legacy plans if present to prevent confusion
            db.query(Plan).filter(Plan.id.in_(["team", "enterprise"])).delete(synchronize_session=False)

            # Update existing plan details
            pro_plan = db.query(Plan).filter(Plan.id == "pro").first()
            if pro_plan:
                if pro_plan.credits_per_month != 18000:
                    pro_plan.credits_per_month = 18000
                if pro_plan.price_inr != 2500:
                    pro_plan.price_inr = 2500
                pro_plan.display_name = "Starter Node"

            hobby_plan = db.query(Plan).filter(Plan.id == "hobby").first()
            if hobby_plan:
                if hobby_plan.credits_per_month != 4000:
                    hobby_plan.credits_per_month = 4000
                if hobby_plan.allowed_models != "all":
                    hobby_plan.allowed_models = "all"
                if hobby_plan.price_inr != 700:
                    hobby_plan.price_inr = 700
                hobby_plan.display_name = "Hobbyist Node"

            max_plan = db.query(Plan).filter(Plan.id == "max").first()
            if not max_plan:
                db.add(Plan(
                    id="max",
                    name="max",
                    display_name="Professional Core",
                    price_inr=5500,
                    credits_per_month=45000,
                    allowed_models="all",
                    max_context_k=1024
                ))
            else:
                if max_plan.credits_per_month != 45000:
                    max_plan.credits_per_month = 45000
                if max_plan.price_inr != 5500:
                    max_plan.price_inr = 5500
                max_plan.display_name = "Professional Core"

            ultimate_plan = db.query(Plan).filter(Plan.id == "ultimate").first()
            if not ultimate_plan:
                db.add(Plan(
                    id="ultimate",
                    name="ultimate",
                    display_name="MAX Node",
                    price_inr=11000,
                    credits_per_month=90000,
                    allowed_models="all",
                    max_context_k=1024
                ))
            else:
                if ultimate_plan.credits_per_month != 90000:
                    ultimate_plan.credits_per_month = 90000
                if ultimate_plan.price_inr != 11000:
                    ultimate_plan.price_inr = 11000
                ultimate_plan.display_name = "MAX Node"
            
            # Generate referral codes for existing users that don't have one
            try:
                users_without_code = db.query(User).filter(User.referral_code == None).all()
                if users_without_code:
                    _print(f"[DB INIT] Generating referral codes for {len(users_without_code)} users...")
                    for u in users_without_code:
                        u.referral_code = uuid.uuid4().hex[:8]
            except Exception as ref_exc:
                _print(f"[DB INIT] Referral code migration check failed: {ref_exc}")
                
            # Seed 4 Google Drive storage nodes (20 TB total capacity)
            try:
                from .storage_nodes import StorageNodeManager
                StorageNodeManager.seed_storage_nodes(db)
            except Exception as node_exc:
                _print(f"[DB INIT] Storage node seeding warning: {node_exc}")

            db.commit()
    except Exception as exc:
        db.rollback()
        # Non-fatal during DB init if tables are locking/not ready yet
        _print(f"[DB INIT] Error during plan seeding: {exc}")

    finally:
        db.close()
        _print("[DB INIT] init_db() completed successfully.")


def get_db():
    """FastAPI dependency — yields a DB session and closes it on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_max_bonus_limit(plan_id: str) -> float:
    pid = (plan_id or "free").lower().strip()
    if pid == "free":
        return 20000.0
    elif pid == "hobby":
        return 50000.0
    elif pid == "pro":
        return 1500000.0
    elif pid == "max":
        return 3000000.0
    elif pid == "ultimate":
        return 4500000.0
    return 20000.0


class MarketplaceListing(Base):
    __tablename__ = "marketplace_listings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    seller_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(128), nullable=False)  # display name
    slug = Column(String(128), unique=True, nullable=False, index=True)  # url-safe id
    type = Column(String(32), nullable=False)  # 'skill', 'miniagent', 'tool', 'mcp'
    category = Column(String(64), nullable=True)  # 'productivity', 'coding', 'ai', etc.
    description = Column(Text, nullable=False)
    readme = Column(Text, nullable=True)  # full readme/docs markdown
    tags = Column(JSON, nullable=True)  # ["python", "gpt", ...]
    icon_emoji = Column(String(8), nullable=True)  # e.g. "🔧"
    price_usd = Column(Float, default=0.0)  # 0 = free
    is_paid = Column(Boolean, default=False)
    is_published = Column(Boolean, default=False)
    is_featured = Column(Boolean, default=False)
    payment_type = Column(String(32), default="one_time")  # 'one_time' | 'subscription'
    subscription_interval = Column(String(16), nullable=True)  # 'monthly' | 'yearly'
    razorpay_plan_id = Column(String(128), nullable=True)  # Razorpay Plan ID for subscriptions
    download_count = Column(Integer, default=0)
    rating_avg = Column(Float, default=0.0)
    rating_count = Column(Integer, default=0)
    version = Column(String(32), default="1.0.0")
    zip_url = Column(Text, nullable=True)  # CDN URL for the zip archive
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    seller = relationship("User", foreign_keys=[seller_id], backref="marketplace_listings")
    reviews = relationship("MarketplaceReview", back_populates="listing", cascade="all, delete-orphan")


class MarketplaceReview(Base):
    __tablename__ = "marketplace_reviews"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    listing_id = Column(String(36), ForeignKey("marketplace_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    rating = Column(Integer, nullable=False)  # 1-5
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    listing = relationship("MarketplaceListing", back_populates="reviews")
    reviewer = relationship("User", foreign_keys=[reviewer_id])
    
    __table_args__ = (
        Index("ix_mp_review_listing_reviewer", "listing_id", "reviewer_id", unique=True),
    )


class MarketplacePurchase(Base):
    __tablename__ = "marketplace_purchases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    listing_id = Column(String(36), ForeignKey("marketplace_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    buyer_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount_usd = Column(Float, nullable=False)
    status = Column(String(32), default="completed")  # 'completed', 'refunded'
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    listing = relationship("MarketplaceListing", foreign_keys=[listing_id])
    buyer = relationship("User", foreign_keys=[buyer_id])
    
    __table_args__ = (
        Index("ix_mp_purchase_listing_buyer", "listing_id", "buyer_id"),
    )


class StorageNode(Base):
    __tablename__ = "storage_nodes"

    id = Column(String(36), primary_key=True, default=lambda: f"node-{uuid.uuid4().hex[:8]}")
    provider_type = Column(String(32), default="gdrive", nullable=False)  # 'gdrive', 's3', 'r2', 'b2'
    account_label = Column(String(128), nullable=False)  # e.g. "Google Drive Storage Node 1 (5TB)"
    refresh_token_ref = Column(Text, nullable=True)
    total_capacity_bytes = Column(BigInteger, default=5_497_558_138_880)  # 5 TB in bytes
    used_bytes = Column(BigInteger, default=0)
    available_bytes = Column(BigInteger, default=5_497_558_138_880)
    is_enabled = Column(Boolean, default=True, nullable=False)
    health_status = Column(String(32), default="healthy", nullable=False)  # 'healthy', 'degraded', 'offline'
    error_count = Column(Integer, default=0)
    last_check_at = Column(DateTime, nullable=True)
    last_upload_at = Column(DateTime, nullable=True)
    last_download_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class MarketplacePackageVersion(Base):
    __tablename__ = "marketplace_package_versions"

    id = Column(String(36), primary_key=True, default=lambda: f"pkg_{uuid.uuid4().hex[:12]}")
    listing_id = Column(String(36), ForeignKey("marketplace_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    seller_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(String(32), nullable=False, default="1.0.0")
    package_type = Column(String(32), nullable=False, default="skill")  # 'skill', 'miniagent', 'tool', 'mcp'
    storage_node_id = Column(String(36), ForeignKey("storage_nodes.id", ondelete="SET NULL"), nullable=True, index=True)
    drive_file_id = Column(String(128), nullable=True, index=True)
    zip_filename = Column(String(255), nullable=False)  # e.g. pkg_8f29c1a4.zip
    size_bytes = Column(BigInteger, nullable=False, default=0)
    sha256_checksum = Column(String(64), nullable=False)
    upload_timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    moderation_status = Column(String(32), default="approved", nullable=False)  # 'approved', 'pending', 'rejected'
    compatibility_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    listing = relationship("MarketplaceListing", foreign_keys=[listing_id], backref=backref("package_versions", cascade="all, delete-orphan", passive_deletes=True))
    storage_node = relationship("StorageNode", foreign_keys=[storage_node_id])
    seller = relationship("User", foreign_keys=[seller_id])

    __table_args__ = (
        Index("ix_mp_version_listing_ver", "listing_id", "version", unique=True),
    )


class SellerProfile(Base):
    __tablename__ = "seller_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    display_name = Column(String(128), nullable=True)
    bio = Column(Text, nullable=True)
    avatar_emoji = Column(String(8), default="🧑💻", nullable=True)
    is_verified = Column(Boolean, default=False)
    razorpay_contact_id = Column(String(128), nullable=True)  # Razorpay Fund Account Contact ID
    razorpay_fund_account_id = Column(String(128), nullable=True)  # Razorpay Fund Account ID
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = relationship("User", foreign_keys=[user_id], backref="seller_profile")
    wallet = relationship("SellerWallet", back_populates="seller", uselist=False, cascade="all, delete-orphan")


class SellerWallet(Base):
    __tablename__ = "seller_wallets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    seller_id = Column(String(36), ForeignKey("seller_profiles.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    balance_usd = Column(Float, default=0.0)       # Current withdrawable balance
    total_earned_usd = Column(Float, default=0.0)  # All-time earnings
    total_withdrawn_usd = Column(Float, default=0.0)
    pending_withdrawal_usd = Column(Float, default=0.0)  # Amount locked in pending withdrawals
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    seller = relationship("SellerProfile", back_populates="wallet")
    withdrawals = relationship("SellerWithdrawal", back_populates="wallet", cascade="all, delete-orphan")


class SellerWithdrawal(Base):
    __tablename__ = "seller_withdrawals"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    wallet_id = Column(String(36), ForeignKey("seller_wallets.id", ondelete="CASCADE"), nullable=False, index=True)
    amount_usd = Column(Float, nullable=False)
    method = Column(String(32), default="upi")  # 'upi' | 'bank'
    upi_id = Column(String(128), nullable=True)
    account_number = Column(String(64), nullable=True)
    account_name = Column(String(128), nullable=True)
    ifsc_code = Column(String(32), nullable=True)
    status = Column(String(32), default="pending")  # 'pending', 'processing', 'completed', 'failed'
    razorpay_payout_id = Column(String(128), nullable=True)
    failure_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    wallet = relationship("SellerWallet", back_populates="withdrawals")


class MarketplacePurchaseOrder(Base):
    """Razorpay order for marketplace item purchase (before verification)."""
    __tablename__ = "marketplace_purchase_orders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    listing_id = Column(String(36), ForeignKey("marketplace_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    buyer_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    razorpay_order_id = Column(String(128), unique=True, nullable=False, index=True)
    amount_usd = Column(Float, nullable=False)
    amount_inr = Column(Float, nullable=False)
    currency = Column(String(8), default="INR")
    status = Column(String(32), default="created")  # 'created', 'paid', 'failed'
    razorpay_payment_id = Column(String(128), nullable=True)
    razorpay_signature = Column(String(255), nullable=True)
    platform_fee_usd = Column(Float, default=0.0)   # 5%
    seller_amount_usd = Column(Float, default=0.0)  # 95%
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    paid_at = Column(DateTime, nullable=True)

    listing = relationship("MarketplaceListing", foreign_keys=[listing_id])
    buyer = relationship("User", foreign_keys=[buyer_id])

    __table_args__ = (
        Index("ix_mp_purchase_order_buyer_listing", "buyer_id", "listing_id"),
    )


class ModelDB(Base):
    __tablename__ = "model_registry"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    model_id = Column(String(128), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    provider = Column(String(64), nullable=False, default="openrouter")
    description = Column(Text, nullable=True)
    context_window = Column(Integer, default=128000)
    max_output_tokens = Column(Integer, nullable=True)
    cost_input_per_1m = Column(Float, default=0.0)
    cost_output_per_1m = Column(Float, default=0.0)
    capabilities = Column(JSON, nullable=True)
    tags = Column(JSON, nullable=True)
    is_free = Column(Boolean, default=False, index=True)
    is_vision = Column(Boolean, default=False, index=True)
    is_reasoning = Column(Boolean, default=False, index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


# ── CLI signature & build identity ────────────────────────────────────────────

class ClientBuild(Base):
    """One row per officially released UTIM CLI build that is allowed to call
    the server. The HMAC secret is stored here so the server can verify requests
    signed by that build. When a new release ships, insert a new row (and let
    the old one expire after the grace window).
    """
    __tablename__ = "client_builds"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    build_version = Column(String(32), nullable=False, index=True)   # e.g. "2.0.4"
    channel = Column(String(16), default="stable", nullable=False)   # stable | beta | dev
    hmac_secret = Column(String(128), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)                      # NULL = never expires
    notes = Column(Text, nullable=True)


class ClientBuildNonce(Base):
    """Single-use nonce issued by /auth/cli-challenge. Marked used_at on consume."""
    __tablename__ = "client_build_nonces"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    nonce = Column(String(64), unique=True, nullable=False, index=True)
    install_id = Column(String(64), nullable=True, index=True)
    ip = Column(String(64), nullable=True)
    expires_at = Column(Integer, nullable=False, index=True)         # epoch seconds
    used_at = Column(Integer, nullable=True, index=True)              # epoch seconds; NULL = unused
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class ClientInstall(Base):
    """Telemetry row for a unique CLI install (one row per install_id). Used
    to detect suspicious patterns (e.g. one install_id signing thousands of
    requests from different IPs in a minute).
    """
    __tablename__ = "client_installs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    install_id = Column(String(64), unique=True, nullable=False, index=True)
    cli_version = Column(String(32), nullable=True)
    first_seen_ip = Column(String(64), nullable=True)
    last_seen_ip = Column(String(64), nullable=True)
    first_seen_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False,
                          onupdate=datetime.datetime.utcnow)
    request_count = Column(BigInteger, default=0, nullable=False)
    is_flagged = Column(Boolean, default=False, nullable=False, index=True)
    flag_reason = Column(String(255), nullable=True)


# ── Helpers used by cli_auth.py (kept in db.py to share the SessionLocal) ────

import os as _os
_CLIENT_BUILDS_CACHE: list[str] = [""]
_CLIENT_BUILDS_CACHE_TS: float = 0.0
_CLIENT_BUILDS_CACHE_TTL: float = 60.0


def get_client_build_secrets() -> list[str]:
    """Return the list of active HMAC secrets for currently-valid CLI builds.

    Reads from BOTH the DB (if init_db has run) and the env var
    `UTIM_CLI_HMAC_SECRETS` (comma-separated) so that the system can boot even
    before any DB rows are seeded. Results are cached for 60 s.
    """
    global _CLIENT_BUILDS_CACHE, _CLIENT_BUILDS_CACHE_TS
    import time as _t
    now = _t.time()
    if _CLIENT_BUILDS_CACHE != [""] and (now - _CLIENT_BUILDS_CACHE_TS) < _CLIENT_BUILDS_CACHE_TTL:
        return _CLIENT_BUILDS_CACHE

    secrets_list: list[str] = []

    # 1. Environment variable (fast, available at boot before any DB write)
    env_secrets = _os.environ.get("UTIM_CLI_HMAC_SECRETS", "").strip()
    if env_secrets:
        for piece in env_secrets.split(","):
            piece = piece.strip()
            if piece:
                secrets_list.append(piece)

    # 2. Database rows
    try:
        db = SessionLocal()
        try:
            rows = db.query(ClientBuild).filter(ClientBuild.is_active == True).all()
            now_dt = datetime.datetime.utcnow()
            for row in rows:
                if row.expires_at is not None and row.expires_at < now_dt:
                    continue
                if row.hmac_secret and row.hmac_secret not in secrets_list:
                    secrets_list.append(row.hmac_secret)
        finally:
            db.close()
    except Exception:
        # DB unavailable (e.g. during local sqlite dev) → env-only is fine
        pass

    _CLIENT_BUILDS_CACHE = secrets_list
    _CLIENT_BUILDS_CACHE_TS = now
    return secrets_list


def is_install_id_known(install_id: str, version: str = "") -> bool:
    """Upsert telemetry for a CLI install. Returns True if the install was
    already known (used by rate-limit logic to weight known installs).
    """
    if not install_id or len(install_id) > 64:
        return False
    try:
        from sqlalchemy import text
        db = SessionLocal()
        try:
            row = db.query(ClientInstall).filter(ClientInstall.install_id == install_id).first()
            if row:
                row.request_count = (row.request_count or 0) + 1
                row.last_seen_at = datetime.datetime.utcnow()
                if version:
                    row.cli_version = version[:32]
                db.commit()
                return True
            new = ClientInstall(
                install_id=install_id[:64],
                cli_version=version[:32] if version else None,
                first_seen_ip=None,
                last_seen_ip=None,
            )
            db.add(new)
            db.commit()
            return False
        finally:
            db.close()
    except Exception:
        return False
