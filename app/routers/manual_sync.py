"""Manual Garmin sync UI for entering MFA codes."""
from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.services.garmin_service import GarminService


router = APIRouter(prefix="/manual", tags=["manual"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/test", response_class=HTMLResponse)
async def test_cached_tokens(request: Request) -> HTMLResponse:
    """Test if cached tokens work without MFA."""

    service = GarminService()
    summary_json: str | None = None
    try:
        service.login()  # Should use cached tokens
        summary = service.get_daily_summary(date.today())
        summary_json = json.dumps(summary, indent=2, default=str)
        message = "Success! Retrieved data using cached tokens (no MFA needed)."
        success = True
    except RuntimeError as err:
        message = str(err)
        success = False
    finally:
        try:
            service.logout()
        except Exception:
            pass

    return templates.TemplateResponse(
        "manual_sync.html",
        {
            "request": request,
            "message": message,
            "success": success,
            "summary_json": summary_json,
        },
    )


@router.get("/mfa", response_class=HTMLResponse)
async def show_mfa_form(request: Request) -> HTMLResponse:
    """Display the MFA entry form."""

    return templates.TemplateResponse(
        "manual_sync.html",
        {
            "request": request,
            "message": None,
            "success": None,
            "summary_json": None,
        },
    )


@router.post("/mfa/request", response_class=HTMLResponse)
async def request_mfa_code(request: Request) -> HTMLResponse:
    """Trigger Garmin to send a new MFA code without completing login."""

    service = GarminService()
    try:
        service.login()
    except RuntimeError as err:
        message = str(err)
        success = "code required" in message.lower()
    else:
        message = "Existing token cache allowed login without MFA."
        success = True
    finally:
        try:
            service.logout()
        except Exception:
            pass

    if success and "code required" in message.lower():
        message = (
            "Verification code requested. Check your Garmin email/SMS and enter it below."
        )

    return templates.TemplateResponse(
        "manual_sync.html",
        {
            "request": request,
            "message": message,
            "success": success,
            "summary_json": None,
        },
    )


@router.post("/mfa", response_class=HTMLResponse)
async def submit_mfa_code(
    request: Request,
    code: str = Form(..., min_length=6, max_length=6),
) -> HTMLResponse:
    """Attempt Garmin login with user-provided MFA code and return summary."""

    service = GarminService()
    summary_json: str | None = None
    try:
        service.login(mfa_code=code.strip())
        summary = service.get_daily_summary(date.today())
        summary_json = json.dumps(summary, indent=2, default=str)
        message = "Success! Retrieved today's Garmin daily summary."
        success = True
    except RuntimeError as err:
        message = str(err)
        success = False
    finally:
        try:
            service.logout()
        except Exception:
            pass

    return templates.TemplateResponse(
        "manual_sync.html",
        {
            "request": request,
            "message": message,
            "success": success,
            "summary_json": summary_json,
        },
    )
