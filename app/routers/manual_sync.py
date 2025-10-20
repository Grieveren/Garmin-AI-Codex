"""Manual Garmin sync UI for entering MFA codes."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.database import SessionLocal
from app.models.database_models import DailyMetric, Activity
from app.services.garmin_service import GarminService
from app.services.ai_analyzer import AIAnalyzer


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


def _fetch_and_save_metrics(garmin: GarminService, db: SessionLocal, target_date: date) -> tuple[str, dict]:
    """
    Helper function to fetch and save metrics for a specific date.

    Returns:
        tuple of (action, metrics_dict) where action is 'created', 'updated', or 'skipped'
    """
    # Fetch daily metrics
    date_str = target_date.isoformat()
    stats = garmin._client.get_stats(date_str)
    sleep = garmin._client.get_sleep_data(date_str)
    hrv = garmin._client.get_hrv_data(date_str)
    hr = garmin._client.get_heart_rates(date_str)
    stress = garmin._client.get_stress_data(date_str)
    body_battery = garmin._client.get_body_battery(date_str)

    # Fetch enhanced metrics (Phase 1)
    try:
        training_readiness = garmin._client.get_training_readiness(date_str)
    except Exception:
        training_readiness = None

    try:
        training_status = garmin._client.get_training_status(date_str)
    except Exception:
        training_status = None

    try:
        spo2 = garmin._client.get_spo2_data(date_str)
    except Exception:
        spo2 = None

    try:
        respiration = garmin._client.get_respiration_data(date_str)
    except Exception:
        respiration = None

    # Build metrics dict
    metrics = {
        "date": target_date,
        "steps": stats.get("totalSteps"),
        "distance_meters": stats.get("totalDistanceMeters"),
        "active_calories": stats.get("activeKilocalories"),
    }

    if hr and (not isinstance(hr, dict) or "error" not in hr):
        metrics["resting_hr"] = hr.get("restingHeartRate")
        metrics["max_hr"] = hr.get("maxHeartRate")

    if hrv and "hrvSummary" in hrv:
        metrics["hrv_morning"] = hrv["hrvSummary"].get("lastNightAvg")

    if sleep and "dailySleepDTO" in sleep:
        sleep_dto = sleep["dailySleepDTO"]
        metrics["sleep_seconds"] = sleep_dto.get("sleepTimeSeconds")
        metrics["deep_sleep_seconds"] = sleep_dto.get("deepSleepSeconds")
        metrics["light_sleep_seconds"] = sleep_dto.get("lightSleepSeconds")
        metrics["rem_sleep_seconds"] = sleep_dto.get("remSleepSeconds")
        sleep_scores = sleep_dto.get("sleepScores", {}).get("overall", {})
        metrics["sleep_score"] = sleep_scores.get("value")

    if stress and isinstance(stress, list) and stress:
        stress_values = [s.get("stressLevel", 0) for s in stress if isinstance(s, dict) and "stressLevel" in s]
        if stress_values:
            metrics["stress_avg"] = int(sum(stress_values) / len(stress_values))

    if body_battery and isinstance(body_battery, list) and body_battery:
        latest = body_battery[-1]
        metrics["body_battery_charged"] = latest.get("charged")
        metrics["body_battery_drained"] = latest.get("drained")
        max_vals = [bb.get("charged", 0) for bb in body_battery if "charged" in bb]
        if max_vals:
            metrics["body_battery_max"] = max(max_vals)

    # Training Readiness Score (Garmin's AI readiness 0-100)
    # API returns a list, extract first item if available - uses "score" key
    if training_readiness and isinstance(training_readiness, list) and len(training_readiness) > 0:
        if isinstance(training_readiness[0], dict):
            metrics["training_readiness_score"] = training_readiness[0].get("score")
    elif training_readiness and isinstance(training_readiness, dict):
        metrics["training_readiness_score"] = training_readiness.get("score")

    # Training Status (VO2 max, training status)
    if training_status and isinstance(training_status, dict):
        # VO2 Max - nested in mostRecentVO2Max → generic → vo2MaxValue
        if "mostRecentVO2Max" in training_status:
            vo2_data = training_status.get("mostRecentVO2Max")
            if vo2_data and isinstance(vo2_data, dict):
                generic = vo2_data.get("generic")
                if generic and isinstance(generic, dict):
                    metrics["vo2_max"] = generic.get("vo2MaxValue")

        # Training Status - nested in mostRecentTrainingStatus → latestTrainingStatusData → {deviceId}
        if "mostRecentTrainingStatus" in training_status:
            status_data = training_status.get("mostRecentTrainingStatus")
            if status_data and isinstance(status_data, dict):
                latest = status_data.get("latestTrainingStatusData")
                if latest and isinstance(latest, dict):
                    # Get first device's data (usually primary device)
                    for device_id, device_data in latest.items():
                        if device_data and isinstance(device_data, dict):
                            metrics["training_status"] = device_data.get("trainingStatusFeedbackPhrase")
                            break

    # SPO2 (Blood Oxygen) - Garmin uses different keys
    if spo2 and isinstance(spo2, dict):
        # Keys are at root level: avgSleepSpO2, lowestSpO2
        if "avgSleepSpO2" in spo2:
            metrics["spo2_avg"] = spo2.get("avgSleepSpO2")
        if "lowestSpO2" in spo2:
            metrics["spo2_min"] = spo2.get("lowestSpO2")

    # Respiration Rate - Garmin uses avgSleepRespirationValue
    if respiration and isinstance(respiration, dict):
        if "avgSleepRespirationValue" in respiration:
            metrics["respiration_avg"] = respiration.get("avgSleepRespirationValue")

    # Save to database
    existing = db.query(DailyMetric).filter(DailyMetric.date == target_date).first()

    if existing:
        # Update existing
        for key, value in metrics.items():
            if key != "date":
                setattr(existing, key, value)
        existing.updated_at = datetime.utcnow()
        action = "updated"
    else:
        # Create new
        metric = DailyMetric(**metrics)
        db.add(metric)
        action = "created"

    db.commit()
    return action, metrics


@router.post("/sync/now")
async def sync_now():
    """
    Manually trigger data sync for today and yesterday.

    Fetches:
    - TODAY: Sleep and HRV from last night (available after waking up)
    - YESTERDAY: Complete metrics and activities

    This is perfect for morning training decisions - you get last night's
    recovery data to inform today's workout recommendation.

    Returns:
        JSON response with sync status and details
    """
    today = date.today()
    yesterday = today - timedelta(days=1)

    garmin = GarminService()
    db = SessionLocal()

    try:
        # Login (will use cached tokens, no MFA needed if valid)
        garmin.login()

        # Sync TODAY's data (sleep/HRV from last night)
        today_action, today_metrics = _fetch_and_save_metrics(garmin, db, today)

        # Sync YESTERDAY's complete data
        yesterday_action, yesterday_metrics = _fetch_and_save_metrics(garmin, db, yesterday)

        # Fetch and save activities for both dates
        activities = garmin._client.get_activities(0, 20)  # Get more to cover both days
        activities_synced = 0

        for activity in activities:
            if not activity.get("startTimeLocal"):
                continue

            activity_date_str = activity["startTimeLocal"][:10]
            activity_date = date.fromisoformat(activity_date_str)

            # Only save if it's today or yesterday
            if activity_date not in [today, yesterday]:
                continue

            activity_data = {
                "id": activity.get("activityId"),
                "date": activity_date,
                "activity_type": activity.get("activityType", {}).get("typeKey"),
                "activity_name": activity.get("activityName"),
                "duration_seconds": activity.get("duration"),
                "distance_meters": activity.get("distance"),
                "aerobic_training_effect": activity.get("aerobicTrainingEffect"),
                "anaerobic_training_effect": activity.get("anaerobicTrainingEffect"),
                "training_load": activity.get("trainingEffect"),
                "avg_hr": activity.get("averageHR"),
                "max_hr": activity.get("maxHR"),
                "avg_pace": activity.get("avgPace"),
                "elevation_gain": activity.get("elevationGain"),
                "calories": activity.get("calories"),
                "start_time": datetime.fromisoformat(activity["startTimeLocal"].replace("Z", "+00:00")) if activity.get("startTimeLocal") else None,
            }

            existing_activity = db.query(Activity).filter(Activity.id == activity_data["id"]).first()

            if existing_activity:
                for key, value in activity_data.items():
                    if key != "id":
                        setattr(existing_activity, key, value)
                existing_activity.updated_at = datetime.utcnow()
            else:
                activity_obj = Activity(**activity_data)
                db.add(activity_obj)

            activities_synced += 1

        db.commit()

        # Clear AI response cache since we have new data
        AIAnalyzer.clear_cache()

        # Build detailed response
        response_message = []

        # Today's data summary
        today_sleep_hours = today_metrics.get("sleep_seconds", 0) / 3600 if today_metrics.get("sleep_seconds") else 0
        if today_sleep_hours > 0:
            response_message.append(f"Today: Sleep {today_sleep_hours:.1f}h, HRV {today_metrics.get('hrv_morning', 'N/A')}")
        else:
            response_message.append(f"Today: Partial data ({today_action})")

        # Yesterday's data summary
        response_message.append(f"Yesterday: Complete data ({yesterday_action})")

        if activities_synced > 0:
            response_message.append(f"{activities_synced} activities")

        return JSONResponse({
            "success": True,
            "dates_synced": {
                "today": str(today),
                "yesterday": str(yesterday)
            },
            "today_action": today_action,
            "yesterday_action": yesterday_action,
            "activities_synced": activities_synced,
            "message": " | ".join(response_message)
        })

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Sync failed: {str(e)}"
        )
    finally:
        db.close()
        try:
            garmin.logout()
        except Exception:
            pass
