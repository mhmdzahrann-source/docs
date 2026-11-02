import json
import logging
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import booking
import whatsapp
from database import get_db
from models import Reservation, WhatsAppConfig, WhatsAppConversation

logger = logging.getLogger("whatsapp_api")

router = APIRouter(prefix="/api/whatsapp")

RESERVATION_STATUSES = {"pending", "confirmed", "declined", "cancelled"}


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _require_config(db: Session) -> WhatsAppConfig:
    config = db.query(WhatsAppConfig).first()
    if not config or not config.access_token or not config.phone_number_id:
        raise HTTPException(status_code=400, detail="WhatsApp is not configured yet. Save it under Settings first.")
    return config


# ---------- Config ----------


class WhatsAppConfigIn(BaseModel):
    access_token: str = ""  # blank = keep the saved token
    phone_number_id: str = ""
    business_name: str = ""
    owner_phone: str = ""
    opening_hours: str = ""
    location: str = ""
    max_party_size: int = Field(default=20, ge=1, le=500)
    bot_enabled: bool = True


class WhatsAppConfigOut(BaseModel):
    access_token_set: bool
    phone_number_id: str = ""
    business_name: str = ""
    owner_phone: str = ""
    opening_hours: str = ""
    location: str = ""
    max_party_size: int = 20
    bot_enabled: bool = True


def _config_out(config: WhatsAppConfig | None) -> WhatsAppConfigOut:
    if not config:
        return WhatsAppConfigOut(access_token_set=False)
    return WhatsAppConfigOut(
        access_token_set=bool(config.access_token),
        phone_number_id=config.phone_number_id or "",
        business_name=config.business_name or "",
        owner_phone=config.owner_phone or "",
        opening_hours=config.opening_hours or "",
        location=config.location or "",
        max_party_size=config.max_party_size or 20,
        bot_enabled=bool(config.bot_enabled),
    )


@router.get("/config", response_model=WhatsAppConfigOut)
def get_config(db: Session = Depends(get_db)):
    return _config_out(db.query(WhatsAppConfig).first())


@router.post("/config", response_model=WhatsAppConfigOut)
def save_config(payload: WhatsAppConfigIn, db: Session = Depends(get_db)):
    config = db.query(WhatsAppConfig).first()
    if not config:
        config = WhatsAppConfig()
        db.add(config)
    if payload.access_token.strip():
        config.access_token = payload.access_token.strip()
    config.phone_number_id = payload.phone_number_id.strip()
    config.business_name = payload.business_name.strip()
    config.owner_phone = _digits(payload.owner_phone)
    config.opening_hours = payload.opening_hours.strip()
    config.location = payload.location.strip()
    config.max_party_size = payload.max_party_size
    config.bot_enabled = payload.bot_enabled
    db.commit()
    db.refresh(config)
    return _config_out(config)


# ---------- Reservations ----------


class ReservationOut(BaseModel):
    id: int
    wa_id: str
    customer_name: str
    date: str
    time: str
    guests: int
    lang: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class StatusIn(BaseModel):
    status: str


class StatusOut(BaseModel):
    reservation: ReservationOut
    customer_notified: bool
    notify_error: str | None = None


@router.get("/reservations", response_model=list[ReservationOut])
def list_reservations(status: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Reservation)
    if status:
        query = query.filter(Reservation.status == status)
    return query.order_by(Reservation.date.asc(), Reservation.time.asc()).all()


@router.post("/reservations/{reservation_id}/status", response_model=StatusOut)
def set_reservation_status(reservation_id: int, payload: StatusIn, db: Session = Depends(get_db)):
    if payload.status not in RESERVATION_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(RESERVATION_STATUSES)}")
    reservation = db.get(Reservation, reservation_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")

    reservation.status = payload.status
    db.commit()
    db.refresh(reservation)

    notified, error = False, None
    config = db.query(WhatsAppConfig).first()
    text = booking.status_message(
        payload.status,
        {"date": reservation.date, "time": reservation.time, "guests": reservation.guests, "lang": reservation.lang},
        (config.business_name if config else None) or "Khayal",
    )
    if text and config and config.access_token and config.phone_number_id:
        try:
            whatsapp.send_text(reservation.wa_id, text, config.phone_number_id, config.access_token)
            notified = True
        except whatsapp.WhatsAppAPIError as exc:
            logger.warning("Could not notify customer for reservation %s: %s", reservation.id, exc)
            error = str(exc)

    return StatusOut(reservation=reservation, customer_notified=notified, notify_error=error)


# ---------- Chats waiting for staff ----------


class HandoffOut(BaseModel):
    wa_id: str
    profile_name: str | None = None
    since: str | None = None


class ReplyIn(BaseModel):
    text: str = Field(min_length=1, max_length=4096)


@router.get("/handoffs", response_model=list[HandoffOut])
def list_handoffs(db: Session = Depends(get_db)):
    conversations = db.query(WhatsAppConversation).filter_by(state="handoff").all()
    return [
        HandoffOut(wa_id=c.wa_id, profile_name=c.profile_name, since=json.loads(c.data or "{}").get("handoff_at"))
        for c in conversations
    ]


@router.post("/handoffs/{wa_id}/reply")
def reply_to_handoff(wa_id: str, payload: ReplyIn, db: Session = Depends(get_db)):
    config = _require_config(db)
    try:
        whatsapp.send_text(wa_id, payload.text, config.phone_number_id, config.access_token)
    except whatsapp.WhatsAppAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"status": "sent"}


@router.post("/handoffs/{wa_id}/resume")
def resume_bot(wa_id: str, db: Session = Depends(get_db)):
    """Hand the chat back to the bot."""

    conversation = db.query(WhatsAppConversation).filter_by(wa_id=wa_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conversation.state = "menu"
    conversation.data = "{}"
    db.commit()
    return {"status": "resumed"}
