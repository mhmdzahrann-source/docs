from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/")
async def root(request: Request):
    return templates.TemplateResponse(request, "campaigns.html", {"active_page": "campaigns"})


@router.get("/dashboard")
async def dashboard_redirect(request: Request):
    return templates.TemplateResponse(request, "campaigns.html", {"active_page": "campaigns"})


@router.get("/dashboard/campaigns")
async def campaigns_page(request: Request):
    return templates.TemplateResponse(request, "campaigns.html", {"active_page": "campaigns"})


@router.get("/dashboard/settings")
async def settings_page(request: Request):
    return templates.TemplateResponse(request, "settings.html", {"active_page": "settings"})
