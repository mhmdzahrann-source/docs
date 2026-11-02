"""WhatsApp Cloud API webhook: receives customer messages and auto-replies.

Meta expects a fast 200, so the actual work (state machine + outgoing API
calls) runs in a background task with its own DB session.
"""

import json
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, Response
from sqlalchemy.exc import IntegrityError

import booking
import whatsapp
from database import SessionLocal
from models import ProcessedWhatsAppMessage, Reservation, WhatsAppConfig, WhatsAppConversation
from routes.webhook import WEBHOOK_VERIFY_TOKEN, _verify_signature

logger = logging.getLogger("whatsapp_webhook")

router = APIRouter()


def business_now() -> datetime:
    """Current wall-clock time in the business's timezone (naive)."""

    tz_name = os.getenv("BUSINESS_TIMEZONE", "Asia/Riyadh")
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        logger.warning("Unknown BUSINESS_TIMEZONE %r, falling back to UTC", tz_name)
        tz = ZoneInfo("UTC")
    return datetime.now(tz).replace(tzinfo=None)


def bot_settings(config: WhatsAppConfig) -> booking.BotSettings:
    return booking.BotSettings(
        business_name=config.business_name or "Khayal",
        opening_hours=config.opening_hours or "",
        location=config.location or "",
        max_party_size=config.max_party_size or 20,
    )


@router.get("/webhook/whatsapp")
async def verify_webhook(request: Request):
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and WEBHOOK_VERIFY_TOKEN
        and params.get("hub.verify_token") == WEBHOOK_VERIFY_TOKEN
    ):
        return Response(content=params.get("hub.challenge"), media_type="text/plain")
    raise HTTPException(status_code=403, detail="Webhook verification failed")


@router.post("/webhook/whatsapp")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
):
    raw_body = await request.body()
    if not _verify_signature(raw_body, x_hub_signature_256):
        logger.warning("Rejected WhatsApp webhook: invalid X-Hub-Signature-256")
        raise HTTPException(status_code=403, detail="Invalid signature")

    payload = json.loads(raw_body or b"{}")
    if payload.get("object") != "whatsapp_business_account":
        return {"status": "ignored"}

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "messages":
                continue
            value = change.get("value", {})
            names = {c.get("wa_id"): (c.get("profile") or {}).get("name") for c in value.get("contacts", [])}
            # `statuses` (sent/delivered/read receipts) are ignored; only real messages are handled.
            for message in value.get("messages", []):
                background_tasks.add_task(process_message, message, names.get(message.get("from")))

    return {"status": "ok"}


def _extract(message: dict) -> tuple[str, str | None]:
    """Return (text, button_id) for any message type we understand."""

    msg_type = message.get("type")
    if msg_type == "text":
        return (message.get("text") or {}).get("body", ""), None
    if msg_type == "interactive":
        interactive = message.get("interactive") or {}
        reply = interactive.get("button_reply") or interactive.get("list_reply") or {}
        return reply.get("title", ""), reply.get("id")
    if msg_type == "button":  # quick-reply button on a template message
        button = message.get("button") or {}
        return button.get("text", ""), button.get("payload")
    return "", None  # image, voice note, location, sticker...


def process_message(message: dict, profile_name: str | None) -> None:
    message_id = message.get("id")
    wa_id = message.get("from")
    if not message_id or not wa_id:
        return

    db = SessionLocal()
    try:
        # Meta retries deliveries; never answer the same message twice.
        if db.query(ProcessedWhatsAppMessage).filter_by(message_id=message_id).first():
            return
        db.add(ProcessedWhatsAppMessage(message_id=message_id))
        try:
            db.commit()
        except IntegrityError:  # a parallel retry of the same delivery got there first
            db.rollback()
            return

        config = db.query(WhatsAppConfig).first()
        if not config or not config.access_token or not config.phone_number_id:
            logger.error("WhatsApp not configured; cannot reply to %s", wa_id)
            return
        if not config.bot_enabled:
            return

        conversation = db.query(WhatsAppConversation).filter_by(wa_id=wa_id).first()
        if not conversation:
            conversation = WhatsAppConversation(wa_id=wa_id, state="new", data="{}", lang="ar")
            db.add(conversation)
        if profile_name:
            conversation.profile_name = profile_name

        text, button_id = _extract(message)
        settings = bot_settings(config)
        now = business_now()

        result = booking.handle_message(
            state=conversation.state or "new",
            data=json.loads(conversation.data or "{}"),
            lang=conversation.lang or "ar",
            text=text,
            button_id=button_id,
            now=now,
            settings=settings,
        )

        conversation.state = result.state
        conversation.data = json.dumps(result.data, ensure_ascii=False)
        conversation.lang = result.lang

        reservation = None
        if result.reservation:
            reservation = Reservation(
                wa_id=wa_id,
                customer_name=result.reservation["name"],
                date=result.reservation["date"],
                time=result.reservation["time"],
                guests=result.reservation["guests"],
                lang=result.reservation["lang"],
                status="pending",
            )
            db.add(reservation)
        db.commit()

        token, sender = config.access_token, config.phone_number_id
        try:
            whatsapp.mark_as_read(message_id, sender, token)
        except whatsapp.WhatsAppAPIError:
            logger.warning("Could not mark message %s as read", message_id)

        for reply in result.replies:
            try:
                if reply.buttons:
                    whatsapp.send_buttons(wa_id, reply.text, reply.buttons, sender, token)
                else:
                    whatsapp.send_text(wa_id, reply.text, sender, token)
            except whatsapp.WhatsAppAPIError:
                logger.exception("Failed to send reply to %s", wa_id)

        if reservation or result.handoff_requested:
            _notify_owner(config, wa_id, conversation.profile_name, reservation)
    finally:
        db.close()


def _notify_owner(config: WhatsAppConfig, wa_id: str, profile_name: str | None, reservation: Reservation | None) -> None:
    """Alert the owner's WhatsApp about a new booking or a request for staff.

    Free-form messages only reach the owner if the owner's number messaged
    the business number in the last 24 hours — see README. The dashboard
    always shows new bookings regardless.
    """

    if not config.owner_phone:
        return
    who = f"{profile_name or ''} (+{wa_id})".strip()
    if reservation:
        text = (
            "🔔 New booking request #{id}\n"
            "👤 {name}\n📞 {who}\n📅 {date}\n🕘 {time}\n👥 {guests} guests\n\n"
            "Confirm or decline it in the dashboard → Reservations."
        ).format(
            id=reservation.id,
            name=reservation.customer_name,
            who=who,
            date=booking.format_date(reservation.date, "en"),
            time=booking.format_time(reservation.time, "en"),
            guests=reservation.guests,
        )
    else:
        text = f"🙋 A customer asked to talk to staff: {who}\nReply to them from the dashboard → Reservations → Chats waiting for staff."
    try:
        whatsapp.send_text(config.owner_phone, text, config.phone_number_id, config.access_token)
    except whatsapp.WhatsAppAPIError:
        logger.warning("Could not notify owner %s (outside 24h window?)", config.owner_phone)
