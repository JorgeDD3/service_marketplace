# app/models.py
import hashlib
import secrets
from datetime import datetime, timedelta

from flask_login import UserMixin
from sqlalchemy import UniqueConstraint

from .extensions import db  # IMPORTANT: import from extensions, not app


# Role Model
class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    role_name = db.Column(db.String(50), unique=True, nullable=False)

    users = db.relationship("User", back_populates="role")

    def __repr__(self):
        return f"<Role {self.role_name}>"


# User Model
class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)

    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=True)

    # --- Account moderation (admin disable/enable) ---
    # Flask-Login uses is_active to determine if the user can authenticate
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    disabled_at = db.Column(db.DateTime, nullable=True)
    disabled_reason = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    role = db.relationship("Role", back_populates="users")
    provider_profile = db.relationship(
        "ProviderProfile", back_populates="user", uselist=False
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

    # IMPORTANT: disambiguate client vs claimed_by_provider_id
    service_requests = db.relationship(
        "ServiceRequest",
        foreign_keys="ServiceRequest.client_id",
        back_populates="client",
    )

    # --- RBAC helpers (clean + scalable) ---
    @property
    def role_display(self) -> str | None:
        return self.role.role_name if self.role else None

    def has_role(self, *roles: str) -> bool:
        if not self.role:
            return False
        return self.role.role_name in roles

    def __repr__(self):
        return f"<User {self.email} role={self.role_display}>"


def hash_token(raw_token: str) -> str:
    """Hash a raw reset token so we never store it in plaintext."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    # Store only a hash of the token (never the token itself)
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)

    used_at = db.Column(db.DateTime, nullable=True)

    # Optional audit fields (handy for admin/security logs)
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
        """
        Creates a reset token row and returns (raw_token, token_row).
        raw_token is what you show to the user (or email later).
        """
        raw = secrets.token_urlsafe(32)  # ~43 chars, URL-safe
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
    __tablename__ = "provider_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    bio = db.Column(db.Text)
    hourly_rate = db.Column(db.Float)
    availability_notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="provider_profile")
    services = db.relationship("Service", back_populates="provider_profile")

    # Provider verification (1:1)
    verification = db.relationship(
        "ProviderVerification",
        back_populates="provider_profile",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def get_or_create_verification(self):
        """
        Ensures a ProviderVerification row exists for this provider.
        Returns the ProviderVerification instance.
        """
        if self.verification:
            return self.verification

        v = ProviderVerification(provider_profile_id=self.id, status="unverified")
        db.session.add(v)
        db.session.commit()
        return v

    def __repr__(self):
        return f"<ProviderProfile {self.id}>"


# Provider Availability (weekly recurring windows)
class ProviderAvailability(db.Model):
    __tablename__ = "provider_availability"

    id = db.Column(db.Integer, primary_key=True)
    provider_profile_id = db.Column(
        db.Integer, db.ForeignKey("provider_profiles.id"), nullable=False
    )

    # 0=Mon ... 6=Sun
    day_of_week = db.Column(db.Integer, nullable=False)

    # Store as "HH:MM" strings (simple + SQLite friendly)
    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5), nullable=False)

    # Slot size in minutes (default 30)
    slot_minutes = db.Column(db.Integer, default=30, nullable=False)

    is_active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    provider_profile = db.relationship("ProviderProfile", backref="availability_rules")

    def __repr__(self):
        return (
            f"<ProviderAvailability profile={self.provider_profile_id} "
            f"dow={self.day_of_week} {self.start_time}-{self.end_time}>"
        )


# Provider Timeoff
class ProviderTimeOff(db.Model):
    __tablename__ = "provider_time_off"

    id = db.Column(db.Integer, primary_key=True)
    provider_profile_id = db.Column(
        db.Integer,
        db.ForeignKey("provider_profiles.id"),
        nullable=False,
    )

    start_datetime = db.Column(db.DateTime, nullable=False)
    end_datetime = db.Column(db.DateTime, nullable=False)

    all_day = db.Column(db.Boolean, nullable=False, default=False)
    reason = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    provider_profile = db.relationship("ProviderProfile", backref="time_off_entries")


# Provider Verification
class ProviderVerification(db.Model):
    __tablename__ = "provider_verifications"

    id = db.Column(db.Integer, primary_key=True)

    # One verification application per provider profile
    provider_profile_id = db.Column(
        db.Integer,
        db.ForeignKey("provider_profiles.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Workflow: unverified -> pending_review -> verified / rejected
    status = db.Column(db.String(32), nullable=False, default="unverified", index=True)

    # "KYC-lite" fields
    legal_name = db.Column(db.String(120), nullable=True)
    license_number = db.Column(db.String(80), nullable=True)
    portfolio_url = db.Column(db.String(255), nullable=True)

    # Upload fields: store filenames/relative paths only
    id_document_filename = db.Column(db.String(255), nullable=True)
    certification_filename = db.Column(db.String(255), nullable=True)

    # Audit trail
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
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    provider_profile = db.relationship(
        "ProviderProfile",
        back_populates="verification",
        uselist=False,
    )
    reviewed_by_admin = db.relationship("User", foreign_keys=[reviewed_by_admin_id])

    def is_verified(self) -> bool:
        return self.status == "verified"

    def __repr__(self) -> str:
        return (
            f"<ProviderVerification provider_profile_id={self.provider_profile_id} "
            f"status={self.status}>"
        )


# Services
class Service(db.Model):
    __tablename__ = "services"

    id = db.Column(db.Integer, primary_key=True)
    provider_profile_id = db.Column(
        db.Integer, db.ForeignKey("provider_profiles.id"), nullable=False
    )

    title = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text)
    price = db.Column(db.Float)
    duration_minutes = db.Column(db.Integer, default=60, nullable=False)

    # --- Admin moderation fields (soft hide/unhide) ---
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    moderation_note = db.Column(db.Text, nullable=True)
    moderated_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    provider_profile = db.relationship("ProviderProfile", back_populates="services")
    bookings = db.relationship("Booking", back_populates="service")

    def __repr__(self):
        return f"<Service {self.title}>"


# Bookings
class Booking(db.Model):
    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)

    provider_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey("services.id"), nullable=False)

    booking_datetime = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, default=60, nullable=False)

    status = db.Column(db.String(50), default="pending")

    # --- Booking status rules (single source of truth) ---
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_DECLINED = "declined"
    STATUS_CANCELLED = "cancelled"

    VALID_STATUSES = {
        STATUS_PENDING,
        STATUS_ACCEPTED,
        STATUS_DECLINED,
        STATUS_CANCELLED,
    }

    # Minimal state machine for core flows
    ALLOWED_TRANSITIONS = {
        STATUS_PENDING: {STATUS_ACCEPTED, STATUS_DECLINED, STATUS_CANCELLED},
        STATUS_ACCEPTED: set(),  # keep strict for now (admin actions can override elsewhere)
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

    # --- Dummy checkout / payment tracking (demo) ---
    payment_status = db.Column(
        db.String(32),
        nullable=False,
        default="unpaid",
        index=True,
    )
    paid_at = db.Column(db.DateTime, nullable=True)
    payment_reference = db.Column(db.String(64), nullable=True)

    decided_at = db.Column(db.DateTime, nullable=True)
    provider_note = db.Column(db.Text, nullable=True)

    # --- Admin moderation fields ---
    admin_note = db.Column(db.Text, nullable=True)
    admin_action_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    provider = db.relationship(
        "User",
        foreign_keys=[provider_id],
        back_populates="bookings_as_provider",
    )

    client = db.relationship(
        "User",
        foreign_keys=[client_id],
        back_populates="bookings_as_client",
    )

    service = db.relationship("Service", back_populates="bookings")

    @classmethod
    def find_open_inquiry(cls, *, client_id: int, provider_id: int, service_id: int):
        """
        Inquiry bookings are pseudo-bookings that store an inquiry marker in provider_note.
        We reuse/convert these into a real booking to avoid creating a second conversation/thread.
        """
        return (
            cls.query.filter_by(
                client_id=client_id,
                provider_id=provider_id,
                service_id=service_id,
            )
            .filter(cls.provider_note.isnot(None))
            .filter(cls.provider_note.like("[INQUIRY]%"))
            .order_by(cls.created_at.desc())
            .first()
        )

    def get_or_create_conversation(self):
        """
        Lazy-create the 1:1 conversation for this booking.
        Returns the Conversation instance.
        """
        convo = Conversation.query.filter_by(booking_id=self.id).first()
        if convo:
            return convo

        convo = Conversation(
            booking_id=self.id,
            client_id=self.client_id,
            provider_id=self.provider_id,
        )
        db.session.add(convo)
        db.session.commit()
        return convo

    def __repr__(self):
        return f"<Booking {self.id}>"


# Service Requests
class ServiceRequest(db.Model):
    __tablename__ = "service_requests"

    id = db.Column(db.Integer, primary_key=True)

    client_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    subject = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)

    status = db.Column(db.String(50), default="open", nullable=False)

    # Provider can "claim" a request
    claimed_by_provider_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    closed_at = db.Column(db.DateTime, nullable=True)

    # IMPORTANT: disambiguate which FK is used for "client"
    client = db.relationship(
        "User",
        foreign_keys=[client_id],
        back_populates="service_requests",
    )

    # optional relationship (useful later for UI)
    claimed_by_provider = db.relationship(
        "User",
        foreign_keys=[claimed_by_provider_id],
    )

    def __repr__(self):
        return f"<ServiceRequest {self.subject}>"


class Conversation(db.Model):
    __tablename__ = "conversations"

    id = db.Column(db.Integer, primary_key=True)

    # 1:1 with booking
    booking_id = db.Column(
        db.Integer, db.ForeignKey("bookings.id"), nullable=False, unique=True
    )

    # Participants (redundant to booking, but intentional for fast access checks)
    client_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    provider_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    booking = db.relationship(
        "Booking",
        backref=db.backref("conversation", uselist=False),
    )
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
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)

    conversation_id = db.Column(
        db.Integer, db.ForeignKey("conversations.id"), nullable=False, index=True
    )

    sender_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )

    body = db.Column(db.Text, nullable=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    conversation = db.relationship("Conversation", back_populates="messages")
    sender = db.relationship("User", foreign_keys=[sender_id])

    def __repr__(self) -> str:
        return f"<Message id={self.id} convo={self.conversation_id} sender={self.sender_id}>"


class ConversationRead(db.Model):
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

    # "Read up to" timestamp for this user in this conversation.
    last_read_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

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
        return (
            f"<ConversationRead convo={self.conversation_id} "
            f"user={self.user_id} last_read_at={self.last_read_at}>"
        )