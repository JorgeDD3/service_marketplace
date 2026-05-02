"""
Database models for ServiceSphere (SQLAlchemy ORM).

This file defines the core tables and relationships for the marketplace:
- users + roles (RBAC)
- provider profiles, availability rules, time off, verification
- services and bookings (including booking state + payment state)
- service requests (clients posting unmet needs)
- messaging tables (conversations + messages + read tracking)
- password reset tokens (stored hashed, with expiration)

I keep everything here so the schema stays in one place and is easy to review.
"""

import hashlib
import secrets
from datetime import datetime, timedelta

from flask_login import UserMixin
from sqlalchemy import UniqueConstraint

from .extensions import db  # important: import from extensions so db is initialized through the app factory


class Role(db.Model):
    """Simple roles table used for RBAC (client/provider/admin)."""

    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    role_name = db.Column(db.String(50), unique=True, nullable=False)

    users = db.relationship("User", back_populates="role")

    def __repr__(self):
        return f"<Role {self.role_name}>"


class User(db.Model, UserMixin):
    """User accounts for ServiceSphere.

    Notes:
    - Flask-Login uses `is_active` to allow/deny authentication.
    - Role is a FK to roles table (RBAC).
    - Providers are users with the provider role and an attached ProviderProfile.
    """

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)

    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=True)

    # Account moderation fields used by admin enable/disable.
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    disabled_at = db.Column(db.DateTime, nullable=True)
    disabled_reason = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    role = db.relationship("Role", back_populates="users")

    provider_profile = db.relationship(
        "ProviderProfile",
        back_populates="user",
        uselist=False,
    )

    bookings_as_client = db.relationship(
        "Booking",
        foreign_keys="Booking.client_id",
        back_populates="client",
    )

    bookings_as_provider = db.relationship(
        "Booking",
        foreign_keys="Booking.provider_id",
        back_populates="provider",
    )

    # Service requests created by this user as a client.
    service_requests = db.relationship(
        "ServiceRequest",
        foreign_keys="ServiceRequest.client_id",
        back_populates="client",
    )

    @property
    def role_display(self) -> str | None:
        """Returns the role name string (or None)."""
        return self.role.role_name if self.role else None

    def has_role(self, *roles: str) -> bool:
        """Convenience helper for RBAC checks."""
        if not self.role:
            return False
        return self.role.role_name in roles

    def __repr__(self):
        return f"<User {self.email} role={self.role_display}>"


def hash_token(raw_token: str) -> str:
    """Hashes a raw reset token so we never store it in plaintext."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class PasswordResetToken(db.Model):
    """Stores password reset tokens (hashed) with expiration and optional audit fields."""

    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    # I only store a hash of the token, never the token itself.
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)

    used_at = db.Column(db.DateTime, nullable=True)

    request_ip = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)

    user = db.relationship(
        "User",
        backref=db.backref("password_reset_tokens", lazy="dynamic"),
    )

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() >= self.expires_at

    @classmethod
    def create_for_user(
        cls,
        user,
        *,
        ttl_minutes: int = 30,
        request_ip: str | None = None,
        user_agent: str | None = None,
    ):
        """Creates a reset token row and returns (raw_token, token_row).

        `raw_token` is what you show/email to the user.
        The database stores only the SHA-256 hash.
        """
        raw = secrets.token_urlsafe(32)
        row = cls(
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=datetime.utcnow() + timedelta(minutes=ttl_minutes),
            request_ip=request_ip,
            user_agent=(user_agent[:255] if user_agent else None),
        )
        db.session.add(row)
        db.session.commit()
        return raw, row


class ProviderProfile(db.Model):
    """Provider public profile (bio, rate, notes).

    This is how a provider "becomes bookable" in the marketplace.
    Services belong to provider profiles, not directly to users.
    """

    __tablename__ = "provider_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    bio = db.Column(db.Text)
    hourly_rate = db.Column(db.Float)
    availability_notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="provider_profile")
    services = db.relationship("Service", back_populates="provider_profile")

    verification = db.relationship(
        "ProviderVerification",
        back_populates="provider_profile",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def get_or_create_verification(self):
        """Ensures a ProviderVerification row exists for this provider."""
        if self.verification:
            return self.verification

        v = ProviderVerification(provider_profile_id=self.id, status="unverified")
        db.session.add(v)
        db.session.commit()
        return v

    def __repr__(self):
        return f"<ProviderProfile {self.id}>"


class ProviderAvailability(db.Model):
    """Weekly recurring availability windows used to generate bookable slots."""

    __tablename__ = "provider_availability"

    id = db.Column(db.Integer, primary_key=True)
    provider_profile_id = db.Column(db.Integer, db.ForeignKey("provider_profiles.id"), nullable=False)

    # 0=Mon ... 6=Sun
    day_of_week = db.Column(db.Integer, nullable=False)

    # Stored as "HH:MM" strings to keep it simple and DB-friendly.
    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5), nullable=False)

    slot_minutes = db.Column(db.Integer, default=30, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    provider_profile = db.relationship("ProviderProfile", backref="availability_rules")

    def __repr__(self):
        return (
            f"<ProviderAvailability profile={self.provider_profile_id} "
            f"dow={self.day_of_week} {self.start_time}-{self.end_time}>"
        )


class ProviderTimeOff(db.Model):
    """One-time time off blocks (vacation, appointments, exceptions to weekly rules)."""

    __tablename__ = "provider_time_off"

    id = db.Column(db.Integer, primary_key=True)
    provider_profile_id = db.Column(db.Integer, db.ForeignKey("provider_profiles.id"), nullable=False)

    start_datetime = db.Column(db.DateTime, nullable=False)
    end_datetime = db.Column(db.DateTime, nullable=False)

    all_day = db.Column(db.Boolean, nullable=False, default=False)
    reason = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    provider_profile = db.relationship("ProviderProfile", backref="time_off_entries")


class ProviderVerification(db.Model):
    """Provider verification workflow (admin-reviewed trust badge)."""

    __tablename__ = "provider_verifications"

    id = db.Column(db.Integer, primary_key=True)

    provider_profile_id = db.Column(
        db.Integer,
        db.ForeignKey("provider_profiles.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Workflow: unverified -> pending_review -> verified / rejected
    status = db.Column(db.String(32), nullable=False, default="unverified", index=True)

    legal_name = db.Column(db.String(120), nullable=True)
    license_number = db.Column(db.String(80), nullable=True)
    portfolio_url = db.Column(db.String(255), nullable=True)

    id_document_filename = db.Column(db.String(255), nullable=True)
    certification_filename = db.Column(db.String(255), nullable=True)

    submitted_at = db.Column(db.DateTime, nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    reviewed_by_admin_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    admin_notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    provider_profile = db.relationship(
        "ProviderProfile",
        back_populates="verification",
        uselist=False,
    )
    reviewed_by_admin = db.relationship("User", foreign_keys=[reviewed_by_admin_id])

    def is_verified(self) -> bool:
        return self.status == "verified"

    def __repr__(self) -> str:
        return f"<ProviderVerification provider_profile_id={self.provider_profile_id} status={self.status}>"


class Service(db.Model):
    """Services offered by providers and visible in the marketplace (unless moderated/hidden)."""

    __tablename__ = "services"

    id = db.Column(db.Integer, primary_key=True)
    provider_profile_id = db.Column(db.Integer, db.ForeignKey("provider_profiles.id"), nullable=False)

    title = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text)
    price = db.Column(db.Float)
    duration_minutes = db.Column(db.Integer, default=60, nullable=False)

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    moderation_note = db.Column(db.Text, nullable=True)
    moderated_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    provider_profile = db.relationship("ProviderProfile", back_populates="services")
    bookings = db.relationship("Booking", back_populates="service")

    def __repr__(self):
        return f"<Service {self.title}>"


class Booking(db.Model):
    """Bookings connect a client to a provider/service at a scheduled datetime.

    This model also acts as the "single source of truth" for:
    - booking status (pending/accepted/declined/cancelled)
    - payment status (unpaid/paid)
    - basic admin/provider notes and audit timestamps

    Some helper methods here are used to enforce conflict rules and keep state changes controlled.
    """

    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)

    provider_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey("services.id"), nullable=False)

    booking_datetime = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, default=60, nullable=False)

    status = db.Column(db.String(50), default="pending")

    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_DECLINED = "declined"
    STATUS_CANCELLED = "cancelled"

    VALID_STATUSES = {STATUS_PENDING, STATUS_ACCEPTED, STATUS_DECLINED, STATUS_CANCELLED}

    ALLOWED_TRANSITIONS = {
        STATUS_PENDING: {STATUS_ACCEPTED, STATUS_DECLINED, STATUS_CANCELLED},
        STATUS_ACCEPTED: set(),
        STATUS_DECLINED: set(),
        STATUS_CANCELLED: set(),
    }

    @classmethod
    def is_valid_status(cls, status: str) -> bool:
        return (status or "").strip().lower() in cls.VALID_STATUSES

    def can_transition_to(self, new_status: str) -> bool:
        new_status = (new_status or "").strip().lower()
        current = (self.status or "").strip().lower()
        return new_status in self.ALLOWED_TRANSITIONS.get(current, set())

    payment_status = db.Column(db.String(32), nullable=False, default="unpaid", index=True)
    paid_at = db.Column(db.DateTime, nullable=True)
    payment_reference = db.Column(db.String(64), nullable=True)

    decided_at = db.Column(db.DateTime, nullable=True)
    provider_note = db.Column(db.Text, nullable=True)

    admin_note = db.Column(db.Text, nullable=True)
    admin_action_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    provider = db.relationship("User", foreign_keys=[provider_id], back_populates="bookings_as_provider")
    client = db.relationship("User", foreign_keys=[client_id], back_populates="bookings_as_client")
    service = db.relationship("Service", back_populates="bookings")

    @classmethod
    def find_open_inquiry(cls, *, client_id: int, provider_id: int, service_id: int):
        """Find an existing inquiry pseudo-booking so we can reuse the same thread."""
        return (
            cls.query.filter_by(client_id=client_id, provider_id=provider_id, service_id=service_id)
            .filter(cls.provider_note.isnot(None))
            .filter(cls.provider_note.like("[INQUIRY]%"))
            .order_by(cls.created_at.desc())
            .first()
        )

    @classmethod
    def auto_cancel_unpaid_within_hours(cls, *, hours: int = 24) -> int:
        """Auto-cancel unpaid pending bookings that are too close to start time.

        This is called from request-handling code so we don't need a background job.
        Returns how many bookings were cancelled.
        """
        now = datetime.utcnow()
        cutoff = now + timedelta(hours=hours)

        candidates = (
            cls.query.filter(cls.status == cls.STATUS_PENDING)
            .filter(cls.payment_status != "paid")
            .filter((cls.provider_note.is_(None)) | (~cls.provider_note.like("[INQUIRY]%")))
            .filter(cls.booking_datetime <= cutoff)
            .all()
        )

        if not candidates:
            return 0

        for b in candidates:
            b.status = cls.STATUS_CANCELLED
            b.decided_at = now

            note = f"[AUTO] Cancelled: unpaid within {hours}h of session."
            b.admin_note = f"{b.admin_note}\n{note}" if b.admin_note else note
            b.admin_action_at = now

        db.session.commit()
        return len(candidates)

    @classmethod
    def has_time_conflict(
        cls,
        *,
        provider_id: int,
        start_dt: datetime,
        duration_minutes: int,
        exclude_booking_id: int | None = None,
    ) -> bool:
        """True if provider has an overlapping pending/accepted booking in the requested window."""
        requested_end = start_dt + timedelta(minutes=duration_minutes)

        q = (
            cls.query.filter(cls.provider_id == provider_id)
            .filter(cls.status.in_([cls.STATUS_PENDING, cls.STATUS_ACCEPTED]))
            .filter((cls.provider_note.is_(None)) | (~cls.provider_note.like("[INQUIRY]%")))
        )

        if exclude_booking_id is not None:
            q = q.filter(cls.id != exclude_booking_id)

        day_start = datetime(start_dt.year, start_dt.month, start_dt.day)
        day_end = day_start + timedelta(days=1)

        candidates = q.filter(cls.booking_datetime >= day_start).filter(cls.booking_datetime < day_end).all()

        for b in candidates:
            b_end = b.booking_datetime + timedelta(minutes=b.duration_minutes)
            if start_dt < b_end and requested_end > b.booking_datetime:
                return True

        return False

    @classmethod
    def client_has_time_conflict(
        cls,
        *,
        client_id: int,
        start_dt: datetime,
        duration_minutes: int,
        exclude_booking_id: int | None = None,
    ) -> bool:
        """True if client has an overlapping pending/accepted booking in the requested window."""
        requested_end = start_dt + timedelta(minutes=duration_minutes)

        q = (
            cls.query.filter(cls.client_id == client_id)
            .filter(cls.status.in_([cls.STATUS_PENDING, cls.STATUS_ACCEPTED]))
            .filter((cls.provider_note.is_(None)) | (~cls.provider_note.like("[INQUIRY]%")))
        )

        if exclude_booking_id is not None:
            q = q.filter(cls.id != exclude_booking_id)

        day_start = datetime(start_dt.year, start_dt.month, start_dt.day)
        day_end = day_start + timedelta(days=1)

        candidates = q.filter(cls.booking_datetime >= day_start).filter(cls.booking_datetime < day_end).all()

        for b in candidates:
            b_end = b.booking_datetime + timedelta(minutes=b.duration_minutes)
            if start_dt < b_end and requested_end > b.booking_datetime:
                return True

        return False

    def get_or_create_conversation(self):
        """Lazy-create the 1:1 conversation for this booking."""
        convo = Conversation.query.filter_by(booking_id=self.id).first()
        if convo:
            return convo

        convo = Conversation(booking_id=self.id, client_id=self.client_id, provider_id=self.provider_id)
        db.session.add(convo)
        db.session.commit()
        return convo

    def __repr__(self):
        return f"<Booking {self.id}>"


class ServiceRequest(db.Model):
    """Client-submitted request when a service is not currently listed."""

    __tablename__ = "service_requests"

    id = db.Column(db.Integer, primary_key=True)

    client_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    subject = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)

    status = db.Column(db.String(50), default="open", nullable=False)

    claimed_by_provider_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    closed_at = db.Column(db.DateTime, nullable=True)

    client = db.relationship("User", foreign_keys=[client_id], back_populates="service_requests")
    claimed_by_provider = db.relationship("User", foreign_keys=[claimed_by_provider_id])

    def __repr__(self):
        return f"<ServiceRequest {self.subject}>"


class Conversation(db.Model):
    """One conversation per booking (client <-> provider)."""

    __tablename__ = "conversations"

    id = db.Column(db.Integer, primary_key=True)

    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=False, unique=True)

    client_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    provider_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    booking = db.relationship("Booking", backref=db.backref("conversation", uselist=False))
    client = db.relationship("User", foreign_keys=[client_id])
    provider = db.relationship("User", foreign_keys=[provider_id])

    messages = db.relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at.asc()",
    )

    reads = db.relationship(
        "ConversationRead",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )

    def user_is_participant(self, user_id: int) -> bool:
        return user_id in (self.client_id, self.provider_id)

    def __repr__(self) -> str:
        return f"<Conversation id={self.id} booking_id={self.booking_id}>"


class Message(db.Model):
    """Message inside a conversation (sent by either participant)."""

    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)

    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id"), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    body = db.Column(db.Text, nullable=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    conversation = db.relationship("Conversation", back_populates="messages")
    sender = db.relationship("User", foreign_keys=[sender_id])

    def __repr__(self) -> str:
        return f"<Message id={self.id} convo={self.conversation_id} sender={self.sender_id}>"


class ConversationRead(db.Model):
    """Tracks the last-read timestamp per user per conversation."""

    __tablename__ = "conversation_reads"

    id = db.Column(db.Integer, primary_key=True)

    conversation_id = db.Column(
        db.Integer,
        db.ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    last_read_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "user_id",
            name="uq_conversation_reads_conversation_user",
        ),
    )

    conversation = db.relationship("Conversation", back_populates="reads")
    user = db.relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:
        return f"<ConversationRead convo={self.conversation_id} user={self.user_id} last_read_at={self.last_read_at}>"