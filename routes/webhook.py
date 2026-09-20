import hashlib
import hmac
import logging
import os

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session

import instagram
from database import get_db
from models import Campaign, Config, ProcessedComment

logger = logging.getLogger("webhook")

router = APIRouter()

WEBHOOK_VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "")
FACEBOOK_APP_SECRET = os.getenv("FACEBOOK_APP_SECRET", "")


@router.get("/webhook/instagram")
async def verify_webhook(request: Request):
    """Facebook's webhook verification handshake.

    Facebook calls this with hub.mode=subscribe, hub.verify_token, and
    hub.challenge. We must echo back hub.challenge if the verify token
    matches what's configured in .env.
    """

    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN and WEBHOOK_VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")

    raise HTTPException(status_code=403, detail="Webhook verification failed")


def _verify_signature(raw_body: bytes, signature_header: str | None) -> bool:
    if not FACEBOOK_APP_SECRET:
        logger.warning("FACEBOOK_APP_SECRET not set; skipping signature verification (INSECURE)")
        return True

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected_signature = signature_header.split("sha256=", 1)[1]
    computed = hmac.new(FACEBOOK_APP_SECRET.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_signature, computed)


@router.post("/webhook/instagram")
async def receive_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
):
    raw_body = await request.body()

    if not _verify_signature(raw_body, x_hub_signature_256):
        logger.warning("Rejected webhook: invalid X-Hub-Signature-256")
        raise HTTPException(status_code=403, detail="Invalid signature")

    payload = await request.json()
    logger.info("Received Instagram webhook payload: %s", payload)

    if payload.get("object") != "instagram":
        return {"status": "ignored"}

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "comments":
                continue
            _handle_comment_event(change.get("value", {}), db)

    return {"status": "ok"}


def _handle_comment_event(value: dict, db: Session) -> None:
    comment_id = value.get("id")
    comment_text = (value.get("text") or "").strip()
    media = value.get("media") or {}
    post_id = media.get("id")
    commenter = value.get("from") or {}
    commenter_id = commenter.get("id")

    if not comment_id or not post_id or not commenter_id:
        logger.info("Skipping malformed comment event: %s", value)
        return

    # Deduplication: never process the same comment twice.
    if db.query(ProcessedComment).filter_by(comment_id=comment_id).first():
        logger.info("Comment %s already processed, skipping", comment_id)
        return

    campaigns = (
        db.query(Campaign)
        .filter(Campaign.post_id == post_id, Campaign.is_active.is_(True))
        .all()
    )
    if not campaigns:
        return

    lowered_text = comment_text.lower()
    matched_campaign = None
    for campaign in campaigns:
        if any(keyword in lowered_text for keyword in campaign.keyword_list()):
            matched_campaign = campaign
            break

    if not matched_campaign:
        return

    config = db.query(Config).first()
    if not config or not config.access_token:
        logger.error("No Instagram access token configured; cannot act on comment %s", comment_id)
        return

    try:
        instagram.reply_to_comment(comment_id, matched_campaign.comment_reply, config.access_token)
    except instagram.InstagramAPIError:
        logger.exception("Failed to reply to comment %s", comment_id)

    try:
        if config.instagram_business_account_id:
            instagram.send_dm(
                commenter_id,
                matched_campaign.dm_message,
                config.instagram_business_account_id,
                config.access_token,
            )
    except instagram.InstagramAPIError:
        logger.exception("Failed to send DM for comment %s; falling back to private reply", comment_id)
        try:
            instagram.send_private_reply_to_comment(comment_id, matched_campaign.dm_message, config.access_token)
        except instagram.InstagramAPIError:
            logger.exception("Private reply fallback also failed for comment %s", comment_id)

    db.add(ProcessedComment(comment_id=comment_id, campaign_id=matched_campaign.id))
    db.commit()
