import base64
import binascii
import logging
import os
import secrets

from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from database import SessionLocal, init_db
from routes import api, dashboard, webhook, whatsapp_api, whatsapp_webhook

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Instagram & WhatsApp Automation")

app.mount("/static", StaticFiles(directory="static"), name="static")

DASHBOARD_USERNAME = os.getenv("DASHBOARD_USERNAME", "admin")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "")

# Meta must reach the webhooks and hosts must reach /health without a
# password; webhooks are protected by their signature check instead.
PUBLIC_PREFIXES = ("/webhook/", "/health", "/static/")


def _credentials_ok(header: str | None) -> bool:
    if not header or not header.startswith("Basic "):
        return False
    try:
        username, _, password = base64.b64decode(header[6:]).decode("utf-8").partition(":")
    except (binascii.Error, UnicodeDecodeError):
        return False
    return secrets.compare_digest(username.encode(), DASHBOARD_USERNAME.encode()) and secrets.compare_digest(
        password.encode(), DASHBOARD_PASSWORD.encode()
    )


@app.middleware("http")
async def require_dashboard_login(request: Request, call_next):
    """Password-protect the dashboard and its API (HTTP Basic auth).

    Enabled when DASHBOARD_PASSWORD is set. The dashboard holds customer
    names/phone numbers and can send WhatsApp messages, so always set it
    in production.
    """

    if DASHBOARD_PASSWORD and not request.url.path.startswith(PUBLIC_PREFIXES):
        if not _credentials_ok(request.headers.get("Authorization")):
            return Response(
                "Login required",
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="Dashboard", charset="UTF-8"'},
            )
    return await call_next(request)


app.include_router(webhook.router)
app.include_router(api.router)
app.include_router(dashboard.router)
app.include_router(whatsapp_webhook.router)
app.include_router(whatsapp_api.router)


def _seed_config_from_env():
    """On first boot, seed the Config row from env vars if one doesn't exist
    yet, so credentials set in .env are picked up without a dashboard visit.
    Values saved later via the dashboard always take precedence.
    """

    from models import Config

    db = SessionLocal()
    try:
        if db.query(Config).first():
            return
        access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        ig_account_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")
        if access_token or ig_account_id:
            db.add(Config(access_token=access_token, instagram_business_account_id=ig_account_id))
            db.commit()
    finally:
        db.close()


def _seed_whatsapp_config_from_env():
    """Same as above for the WhatsApp bot settings."""

    from models import WhatsAppConfig

    db = SessionLocal()
    try:
        if db.query(WhatsAppConfig).first():
            return
        access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
        phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
        if access_token or phone_number_id:
            db.add(
                WhatsAppConfig(
                    access_token=access_token,
                    phone_number_id=phone_number_id,
                    business_name=os.getenv("BUSINESS_NAME") or "Khayal",
                    owner_phone="".join(ch for ch in os.getenv("OWNER_WHATSAPP_NUMBER", "") if ch.isdigit()),
                )
            )
            db.commit()
    finally:
        db.close()


@app.on_event("startup")
def on_startup():
    if not DASHBOARD_PASSWORD:
        logging.getLogger("main").warning(
            "DASHBOARD_PASSWORD is not set: the dashboard and API are open to anyone who can reach this server."
        )
    init_db()
    _seed_config_from_env()
    _seed_whatsapp_config_from_env()


@app.get("/health")
def health():
    return {"status": "ok"}
