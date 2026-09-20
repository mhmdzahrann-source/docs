import logging
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from database import SessionLocal, init_db
from routes import api, dashboard, webhook

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Instagram Comment-to-DM Automation")

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(webhook.router)
app.include_router(api.router)
app.include_router(dashboard.router)


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


@app.on_event("startup")
def on_startup():
    init_db()
    _seed_config_from_env()


@app.get("/health")
def health():
    return {"status": "ok"}
