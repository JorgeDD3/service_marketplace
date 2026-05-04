"""
Messaging blueprint for ServiceSphere.

This module handles the booking-centered inbox + conversation threads.

Key rules (intentional constraints):
- Only booking participants can view a thread.
- Demo checkout gate applies only to *clients* and only for unpaid *real* bookings.
- Inquiry pseudo-bookings are never pay-gated (they're just a pre-book thread).
- Read/unread tracking is stored in ConversationRead (DB-backed).
"""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from .extensions import db
from .models import Booking, Conversation, ConversationRead, Message

messages_bp = Blueprint("messages", __name__, url_prefix="/messages")


def _is_inquiry_booking(booking: Booking | None) -> bool:
    """Return True if a booking is an inquiry pseudo-booking.

    Inquiry threads are anchored to a Booking row, but they are not real sessions:
    - tagged by provider_note prefix
    - must never be blocked by checkout gating
    """
    if not booking:
        return False
    note = booking.provider_note or ""
    return note.startswith("[INQUIRY]")


def _should_gate_client_for_booking(booking: Booking | None) -> bool:
    """Return True if a client should be blocked from messaging until checkout.

    Gate ONLY clients for unpaid REAL bookings:
    - Providers are never gated
    - Inquiry pseudo-bookings are never gated
    """
    if not booking:
        return False
    if _is_inquiry_booking(booking):
        return False
    return booking.payment_status != "paid"


@messages_bp.get("/")
@login_required
def inbox():
    """Inbox list view.

    We show all conversations where the current user is either the client or provider.
    Conversation ordering is by last activity (newest message wins).
    """
    conversations = (
        Conversation.query.filter(
            (Conversation.client_id == current_user.id)
            | (Conversation.provider_id == current_user.id)
        )
        .order_by(Conversation.created_at.desc())
        .all()
    )

    convo_ids = [c.id for c in conversations]
    last_by_convo: dict[int, Message] = {}

    if convo_ids:
        # Pull messages newest-first, keep the first per conversation_id.
        msgs = (
            Message.query.filter(Message.conversation_id.in_(convo_ids))
            .order_by(Message.created_at.desc())
            .all()
        )
        for m in msgs:
            if m.conversation_id not in last_by_convo:
                last_by_convo[m.conversation_id] = m

        # Sort conversations by last activity: last message time or created_at.
        def last_time(c: Conversation):
            m = last_by_convo.get(c.id)
            return m.created_at if m else c.created_at

        conversations.sort(key=last_time, reverse=True)

    # Read tracking rows for this user (per conversation).
    read_rows = (
        ConversationRead.query.filter(
            ConversationRead.user_id == current_user.id,
            ConversationRead.conversation_id.in_(convo_ids),
        ).all()
        if convo_ids
        else []
    )
    last_read_by_convo: dict[int, datetime | None] = {
        r.conversation_id: r.last_read_at for r in read_rows
    }

    # Unread = latest message is from the other participant and is newer than last_read_at.
    unread_ids: set[int] = set()

    for c in conversations:
        last = last_by_convo.get(c.id)
        if not last:
            continue

        other_user_id = c.provider_id if current_user.id == c.client_id else c.client_id

        # Only treat unread if the newest message is from the other user.
        if last.sender_id != other_user_id:
            continue

        last_read_at = last_read_by_convo.get(c.id)

        # Never read => any other-user message counts as unread.
        if last_read_at is None or last.created_at > last_read_at:
            unread_ids.add(c.id)

    return render_template(
        "messages/inbox.html",
        conversations=conversations,
        last_by_convo=last_by_convo,
        unread_ids=unread_ids,
    )


@messages_bp.route("/<int:conversation_id>", methods=["GET", "POST"])
@login_required
def thread(conversation_id: int):
    """Conversation thread view and message send handler."""
    convo = Conversation.query.get_or_404(conversation_id)

    if not convo.user_is_participant(current_user.id):
        abort(403)

    # Demo checkout gate:
    # - Providers are never gated
    # - Inquiry threads are never gated
    # - Clients are gated only for unpaid REAL bookings
    is_provider_view = current_user.id == convo.provider_id
    if (not is_provider_view) and convo.booking and _should_gate_client_for_booking(convo.booking):
        flash(
            "Please complete checkout (demo) to unlock messaging for this booking.",
            "warning",
        )
        return redirect(url_for("main.checkout", booking_id=convo.booking_id))

    if request.method == "POST":
        body = (request.form.get("body") or "").strip()
        if not body:
            flash("Message cannot be empty.", "warning")
            return redirect(url_for("messages.thread", conversation_id=conversation_id, _anchor="compose"))

        # Simple anti-spam: prevent rapid-fire sends (per user per conversation).
        last_sent = (
            Message.query.filter_by(conversation_id=convo.id, sender_id=current_user.id)
            .order_by(Message.created_at.desc())
            .first()
        )
        if last_sent and (datetime.utcnow() - last_sent.created_at).total_seconds() < 2:
            flash("You're sending messages too quickly. Please wait a moment.", "warning")
            return redirect(url_for("messages.thread", conversation_id=conversation_id, _anchor="compose"))

        msg = Message(
            conversation_id=convo.id,
            sender_id=current_user.id,
            body=body,
        )
        db.session.add(msg)

        # Mark as read for the sender immediately.
        now = datetime.utcnow()
        read_row = ConversationRead.query.filter_by(
            conversation_id=convo.id,
            user_id=current_user.id,
        ).first()

        if read_row is None:
            read_row = ConversationRead(
                conversation_id=convo.id,
                user_id=current_user.id,
                last_read_at=now,
            )
            db.session.add(read_row)
        else:
            read_row.last_read_at = now

        db.session.commit()
        return redirect(url_for("messages.thread", conversation_id=conversation_id, _anchor="compose"))

    # GET: mark this conversation as read for the current user.
    now = datetime.utcnow()
    read_row = ConversationRead.query.filter_by(
        conversation_id=convo.id,
        user_id=current_user.id,
    ).first()

    if read_row is None:
        read_row = ConversationRead(
            conversation_id=convo.id,
            user_id=current_user.id,
            last_read_at=now,
        )
        db.session.add(read_row)
    else:
        read_row.last_read_at = now

    db.session.commit()
    return render_template("messages/thread.html", convo=convo)


@messages_bp.get("/booking/<int:booking_id>")
@login_required
def booking_thread(booking_id: int):
    """Jump from a booking directly to its conversation.

    This lazy-creates the conversation if missing so other parts of the app can
    link to messages without worrying about setup timing.
    """
    booking = Booking.query.get_or_404(booking_id)

    # Only booking participants can access.
    if current_user.id not in (booking.client_id, booking.provider_id):
        abort(403)

    # Demo checkout gate:
    # - Providers are never gated
    # - Inquiry threads are never gated
    # - Clients are gated only for unpaid REAL bookings
    is_provider_view = current_user.id == booking.provider_id
    if (not is_provider_view) and _should_gate_client_for_booking(booking):
        flash(
            "Please complete checkout (demo) to unlock messaging for this booking.",
            "warning",
        )
        return redirect(url_for("main.checkout", booking_id=booking.id))

    convo = booking.get_or_create_conversation()
    return redirect(url_for("messages.thread", conversation_id=convo.id, _anchor="compose"))