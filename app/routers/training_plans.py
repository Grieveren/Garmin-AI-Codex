"""API endpoints for training plan management."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.database_models import TrainingPlan, PlannedWorkout
from app.models.schemas import (
    TrainingPlanCreate,
    TrainingPlanResponse,
    TrainingPlanWithWorkouts,
    PlannedWorkoutResponse,
    WorkoutCompletionUpdate,
)
from app.services.training_planner import TrainingPlanner


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/training", tags=["training_plans"])


@router.get("/plans/current", response_model=TrainingPlanWithWorkouts)
async def get_current_plan(
    db: Annotated[Session, Depends(get_db)],
    days_ahead: int = 14,
):
    """
    Get the currently active training plan with upcoming workouts.

    Args:
        days_ahead: Number of days ahead to include (default 14)

    Returns:
        TrainingPlanWithWorkouts: Active plan with filtered workouts
    """
    try:
        # Find active training plan
        plan = (
            db.query(TrainingPlan)
            .filter(TrainingPlan.is_active == True)
            .options(joinedload(TrainingPlan.workouts))
            .first()
        )

        if not plan:
            raise HTTPException(status_code=404, detail="No active training plan found")

        # Filter workouts to upcoming dates
        today = date.today()
        end_date = today + timedelta(days=days_ahead)

        upcoming_workouts = [
            w for w in plan.workouts
            if today <= w.date <= end_date
        ]

        # Sort by date
        upcoming_workouts.sort(key=lambda w: w.date)

        # Build response
        plan_dict = {
            "id": plan.id,
            "name": plan.name,
            "goal": plan.goal,
            "start_date": plan.start_date,
            "target_date": plan.target_date,
            "notes": plan.notes,
            "is_active": plan.is_active,
            "created_by_ai": plan.created_by_ai,
            "created_at": plan.created_at,
            "updated_at": plan.updated_at,
            "workouts": upcoming_workouts,
        }

        logger.info(
            "Retrieved current plan: id=%s, workouts=%d",
            plan.id,
            len(upcoming_workouts),
        )
        return plan_dict

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to retrieve current training plan")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve training plan: {str(e)}"
        )


@router.get("/plans/{plan_id}", response_model=TrainingPlanWithWorkouts)
async def get_plan_by_id(
    plan_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Get a specific training plan with all workouts.

    Args:
        plan_id: Training plan ID

    Returns:
        TrainingPlanWithWorkouts: Plan with all workouts
    """
    try:
        plan = (
            db.query(TrainingPlan)
            .filter(TrainingPlan.id == plan_id)
            .options(joinedload(TrainingPlan.workouts))
            .first()
        )

        if not plan:
            raise HTTPException(status_code=404, detail=f"Training plan {plan_id} not found")

        # Sort workouts by date
        sorted_workouts = sorted(plan.workouts, key=lambda w: w.date)

        plan_dict = {
            "id": plan.id,
            "name": plan.name,
            "goal": plan.goal,
            "start_date": plan.start_date,
            "target_date": plan.target_date,
            "notes": plan.notes,
            "is_active": plan.is_active,
            "created_by_ai": plan.created_by_ai,
            "created_at": plan.created_at,
            "updated_at": plan.updated_at,
            "workouts": sorted_workouts,
        }

        logger.info("Retrieved plan: id=%s, workouts=%d", plan.id, len(sorted_workouts))
        return plan_dict

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to retrieve training plan %s", plan_id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve training plan: {str(e)}"
        )


@router.post("/plans/generate", response_model=TrainingPlanWithWorkouts, status_code=201)
async def generate_training_plan(
    plan_request: TrainingPlanCreate,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Generate a new AI-powered training plan.

    Args:
        plan_request: Plan generation parameters (goal, dates, fitness level, volume)

    Returns:
        TrainingPlanWithWorkouts: Generated plan with all workouts
    """
    try:
        # Validate dates
        if plan_request.target_date <= plan_request.start_date:
            raise HTTPException(
                status_code=400,
                detail="Target date must be after start date"
            )

        # Deactivate existing active plans
        db.query(TrainingPlan).filter(TrainingPlan.is_active == True).update(
            {"is_active": False}
        )

        # Generate plan using TrainingPlanner service
        planner = TrainingPlanner()
        plan_data = planner.generate_plan(
            goal=plan_request.goal,
            target_date=plan_request.target_date,
        )

        # Create training plan record
        new_plan = TrainingPlan(
            name=plan_request.name,
            goal=plan_request.goal,
            start_date=plan_request.start_date,
            target_date=plan_request.target_date,
            notes=plan_request.notes,
            is_active=True,
            created_by_ai=True,
        )

        db.add(new_plan)
        db.flush()  # Get the plan ID

        # Generate placeholder workouts
        # TODO: Integrate with enhanced TrainingPlanner when it has real workout generation
        workouts = []
        current_date = plan_request.start_date
        week_pattern = ["easy_run", "tempo", "rest", "easy_run", "intervals", "long_run", "rest"]

        while current_date <= plan_request.target_date:
            day_index = (current_date - plan_request.start_date).days % 7
            workout_type = week_pattern[day_index]

            # Generate workout based on type
            if workout_type == "rest":
                target_duration = None
                target_distance = None
                intensity = 0
                description = "Rest and recovery day"
            elif workout_type == "easy_run":
                target_duration = 45
                target_distance = 6000
                intensity = 3
                description = "Easy conversational pace"
            elif workout_type == "tempo":
                target_duration = 55
                target_distance = 8000
                intensity = 7
                description = "Comfortably hard tempo pace"
            elif workout_type == "intervals":
                target_duration = 60
                target_distance = 10000
                intensity = 9
                description = "High intensity interval training"
            elif workout_type == "long_run":
                target_duration = 90
                target_distance = 12000
                intensity = 4
                description = "Long slow distance run"
            else:
                target_duration = 45
                target_distance = 6000
                intensity = 3
                description = "Easy run"

            workout = PlannedWorkout(
                plan_id=new_plan.id,
                date=current_date,
                workout_type=workout_type,
                description=description,
                target_duration_minutes=target_duration,
                target_distance_meters=target_distance,
                intensity_level=intensity,
                was_completed=False,
            )
            workouts.append(workout)
            current_date += timedelta(days=1)

        db.add_all(workouts)
        db.commit()

        # Reload plan with workouts
        db.refresh(new_plan)

        plan_dict = {
            "id": new_plan.id,
            "name": new_plan.name,
            "goal": new_plan.goal,
            "start_date": new_plan.start_date,
            "target_date": new_plan.target_date,
            "notes": new_plan.notes,
            "is_active": new_plan.is_active,
            "created_by_ai": new_plan.created_by_ai,
            "created_at": new_plan.created_at,
            "updated_at": new_plan.updated_at,
            "workouts": sorted(workouts, key=lambda w: w.date),
        }

        logger.info(
            "Generated training plan: id=%s, goal=%s, workouts=%d",
            new_plan.id,
            new_plan.goal,
            len(workouts),
        )
        return plan_dict

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to generate training plan")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate training plan: {str(e)}"
        )


@router.put("/workouts/{workout_id}/complete", response_model=PlannedWorkoutResponse)
async def complete_workout(
    workout_id: int,
    completion: WorkoutCompletionUpdate,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Mark a planned workout as complete with actual performance data.

    Args:
        workout_id: Planned workout ID
        completion: Completion details (completed flag, actual metrics, notes)

    Returns:
        PlannedWorkoutResponse: Updated workout record
    """
    try:
        workout = db.query(PlannedWorkout).filter(PlannedWorkout.id == workout_id).first()

        if not workout:
            raise HTTPException(status_code=404, detail=f"Workout {workout_id} not found")

        # Update completion status
        workout.was_completed = completion.completed
        workout.actual_duration_minutes = completion.actual_duration_min
        workout.actual_distance_km = completion.actual_distance_km
        workout.completion_notes = completion.notes
        workout.completed_at = completion.completed_at or datetime.utcnow()
        workout.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(workout)

        logger.info(
            "Marked workout %s as %s",
            workout_id,
            "complete" if completion.completed else "incomplete",
        )
        return workout

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to update workout %s", workout_id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update workout: {str(e)}"
        )


@router.delete("/plans/{plan_id}", status_code=200)
async def deactivate_plan(
    plan_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Deactivate a training plan (soft delete).

    Args:
        plan_id: Training plan ID to deactivate

    Returns:
        dict: Success message
    """
    try:
        plan = db.query(TrainingPlan).filter(TrainingPlan.id == plan_id).first()

        if not plan:
            raise HTTPException(status_code=404, detail=f"Training plan {plan_id} not found")

        plan.is_active = False
        plan.updated_at = datetime.utcnow()

        db.commit()

        logger.info("Deactivated training plan: id=%s", plan_id)
        return {"message": f"Training plan {plan_id} deactivated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to deactivate plan %s", plan_id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to deactivate plan: {str(e)}"
        )
