from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from database import Base


class Config(Base):
    """Singleton-ish settings row holding Instagram credentials."""

    __tablename__ = "config"

    id = Column(Integer, primary_key=True, index=True)
    access_token = Column(Text, nullable=True)
    page_id = Column(String(64), nullable=True)
    instagram_business_account_id = Column(String(64), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(String(128), nullable=False, index=True)
    post_thumbnail_url = Column(Text, nullable=True)
    post_caption = Column(Text, nullable=True)
    keywords = Column(Text, nullable=False)  # comma-separated
    comment_reply = Column(Text, nullable=False)
    dm_message = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def keyword_list(self):
        return [k.strip().lower() for k in self.keywords.split(",") if k.strip()]


class ProcessedComment(Base):
    __tablename__ = "processed_comments"

    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(String(128), unique=True, nullable=False, index=True)
    campaign_id = Column(Integer, nullable=True)
    processed_at = Column(DateTime, default=datetime.utcnow)


# ---------- WhatsApp reservation bot ----------


class WhatsAppConfig(Base):
    """Singleton-ish settings row for the WhatsApp Business (Cloud API) bot."""

    __tablename__ = "whatsapp_config"

    id = Column(Integer, primary_key=True, index=True)
    access_token = Column(Text, nullable=True)
    phone_number_id = Column(String(64), nullable=True)
    business_name = Column(String(128), nullable=True)
    owner_phone = Column(String(32), nullable=True)  # digits only, gets new-booking alerts
    opening_hours = Column(Text, nullable=True)
    location = Column(Text, nullable=True)
    max_party_size = Column(Integer, default=20)
    bot_enabled = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WhatsAppConversation(Base):
    """Where each customer is in the booking flow."""

    __tablename__ = "whatsapp_conversations"

    id = Column(Integer, primary_key=True, index=True)
    wa_id = Column(String(32), unique=True, nullable=False, index=True)
    profile_name = Column(String(128), nullable=True)
    lang = Column(String(2), default="ar")
    state = Column(String(32), default="new")
    data = Column(Text, default="{}")  # JSON scratch space for the booking in progress
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Reservation(Base):
    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, index=True)
    wa_id = Column(String(32), nullable=False, index=True)
    customer_name = Column(String(128), nullable=False)
    date = Column(String(10), nullable=False)  # YYYY-MM-DD
    time = Column(String(5), nullable=False)  # HH:MM (24h)
    guests = Column(Integer, nullable=False)
    lang = Column(String(2), default="ar")
    status = Column(String(16), default="pending")  # pending | confirmed | declined | cancelled
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProcessedWhatsAppMessage(Base):
    __tablename__ = "processed_whatsapp_messages"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String(128), unique=True, nullable=False, index=True)
    processed_at = Column(DateTime, default=datetime.utcnow)
