import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

import instagram
from database import get_db
from models import Campaign, Config

logger = logging.getLogger("api")

router = APIRouter(prefix="/api")


# ---------- Schemas ----------


class ConfigIn(BaseModel):
    access_token: str
    page_id: str = ""
    instagram_business_account_id: str = ""


class ConfigOut(BaseModel):
    access_token_set: bool
    page_id: str = ""
    instagram_business_account_id: str = ""

    class Config:
        from_attributes = True


class CampaignIn(BaseModel):
    post_id: str
    keywords: str
    comment_reply: str
    dm_message: str
    is_active: bool = True


class CampaignOut(BaseModel):
    id: int
    post_id: str
    post_thumbnail_url: str | None = None
    post_caption: str | None = None
    keywords: str
    comment_reply: str
    dm_message: str
    is_active: bool

    class Config:
        from_attributes = True


# ---------- Config ----------


@router.get("/config", response_model=ConfigOut)
def get_config(db: Session = Depends(get_db)):
    config = db.query(Config).first()
    if not config:
        return ConfigOut(access_token_set=False, page_id="", instagram_business_account_id="")
    return ConfigOut(
        access_token_set=bool(config.access_token),
        page_id=config.page_id or "",
        instagram_business_account_id=config.instagram_business_account_id or "",
    )


@router.post("/config", response_model=ConfigOut)
def save_config(payload: ConfigIn, db: Session = Depends(get_db)):
    config = db.query(Config).first()
    if not config:
        config = Config()
        db.add(config)
    config.access_token = payload.access_token
    config.page_id = payload.page_id
    config.instagram_business_account_id = payload.instagram_business_account_id
    db.commit()
    db.refresh(config)
    return ConfigOut(
        access_token_set=bool(config.access_token),
        page_id=config.page_id or "",
        instagram_business_account_id=config.instagram_business_account_id or "",
    )


# ---------- Campaigns ----------


@router.get("/campaigns", response_model=list[CampaignOut])
def list_campaigns(db: Session = Depends(get_db)):
    return db.query(Campaign).order_by(Campaign.created_at.desc()).all()


@router.get("/campaigns/{campaign_id}", response_model=CampaignOut)
def get_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.post("/campaigns", response_model=CampaignOut)
def create_campaign(payload: CampaignIn, db: Session = Depends(get_db)):
    campaign = Campaign(**payload.model_dump())
    _attach_post_preview(campaign, db)
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


@router.put("/campaigns/{campaign_id}", response_model=CampaignOut)
def update_campaign(campaign_id: int, payload: CampaignIn, db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    post_id_changed = campaign.post_id != payload.post_id
    for field, value in payload.model_dump().items():
        setattr(campaign, field, value)

    if post_id_changed:
        _attach_post_preview(campaign, db)

    db.commit()
    db.refresh(campaign)
    return campaign


@router.delete("/campaigns/{campaign_id}")
def delete_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    db.delete(campaign)
    db.commit()
    return {"status": "deleted"}


@router.post("/campaigns/{campaign_id}/toggle", response_model=CampaignOut)
def toggle_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.is_active = not campaign.is_active
    db.commit()
    db.refresh(campaign)
    return campaign


# ---------- Post preview ----------


class PostPreviewOut(BaseModel):
    thumbnail_url: str | None = None
    caption: str | None = None
    permalink: str | None = None
    error: str | None = None


@router.get("/post-preview", response_model=PostPreviewOut)
def post_preview(post_id: str, db: Session = Depends(get_db)):
    config = db.query(Config).first()
    if not config or not config.access_token:
        return PostPreviewOut(error="Instagram access token not configured. Save it under Settings first.")

    try:
        data = instagram.get_post_details(post_id, config.access_token)
    except instagram.InstagramAPIError as exc:
        logger.warning("Failed to fetch post preview for %s: %s", post_id, exc)
        return PostPreviewOut(error=str(exc))

    return PostPreviewOut(
        thumbnail_url=data.get("preview_url"),
        caption=data.get("caption"),
        permalink=data.get("permalink"),
    )


def _attach_post_preview(campaign: Campaign, db: Session) -> None:
    config = db.query(Config).first()
    if not config or not config.access_token:
        return
    try:
        data = instagram.get_post_details(campaign.post_id, config.access_token)
    except instagram.InstagramAPIError as exc:
        logger.warning("Could not fetch preview while saving campaign for post %s: %s", campaign.post_id, exc)
        return
    campaign.post_thumbnail_url = data.get("preview_url")
    campaign.post_caption = data.get("caption")
