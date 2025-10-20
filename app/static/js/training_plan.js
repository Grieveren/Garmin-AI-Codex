/**
 * Training Plan Calendar - Interactive workout tracking and plan management
 */

// State management
let currentPlan = null;
let allWorkouts = [];
let currentWeekStart = new Date();

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Set default dates in form
    const today = new Date();
    const startInput = document.getElementById('start-date-input');
    const targetInput = document.getElementById('target-date-input');

    if (startInput) {
        startInput.valueAsDate = today;
    }

    if (targetInput) {
        const futureDate = new Date();
        futureDate.setDate(futureDate.getDate() + 90); // 90 days from now
        targetInput.valueAsDate = futureDate;
    }

    // Load current plan
    loadCurrentPlan();

    // Set current week to start of this week (Monday)
    setToStartOfWeek(currentWeekStart);
});

/**
 * Set date to start of week (Monday)
 */
function setToStartOfWeek(date) {
    const day = date.getDay();
    const diff = date.getDate() - day + (day === 0 ? -6 : 1); // Adjust when day is Sunday
    date.setDate(diff);
    date.setHours(0, 0, 0, 0);
}

/**
 * Load current active training plan
 */
async function loadCurrentPlan() {
    try {
        showLoading();

        const response = await fetch('/api/training/plans/current');

        if (response.status === 404) {
            // No active plan
            showNoPlanView();
            return;
        }

        if (!response.ok) {
            throw new Error(`Failed to load plan: ${response.statusText}`);
        }

        const data = await response.json();

        if (!data.plan) {
            showNoPlanView();
            return;
        }

        currentPlan = data.plan;
        allWorkouts = data.workouts || [];

        displayPlanOverview();
        renderCalendarWeek();
        showPlanView();

    } catch (error) {
        console.error('Error loading plan:', error);
        showError('Failed to load training plan. Please try again.');
        showNoPlanView();
    }
}

/**
 * Display plan overview section
 */
function displayPlanOverview() {
    if (!currentPlan) return;

    // Plan name and goal
    document.getElementById('plan-name').textContent = currentPlan.name;
    document.getElementById('plan-goal').textContent = formatGoal(currentPlan.goal);

    // Plan dates
    const startDate = new Date(currentPlan.start_date);
    const targetDate = new Date(currentPlan.target_date);
    const dateRange = `${formatDate(startDate)} - ${formatDate(targetDate)}`;
    document.getElementById('plan-dates').textContent = dateRange;

    // Progress calculation
    const today = new Date();
    const totalDays = Math.ceil((targetDate - startDate) / (1000 * 60 * 60 * 24));
    const elapsedDays = Math.ceil((today - startDate) / (1000 * 60 * 60 * 24));
    const progressPercent = Math.min(100, Math.max(0, (elapsedDays / totalDays) * 100));

    document.getElementById('progress-fill').style.width = `${progressPercent}%`;
    document.getElementById('progress-text').textContent =
        `${Math.round(progressPercent)}% complete · ${Math.max(0, totalDays - elapsedDays)} days remaining`;
}

/**
 * Render calendar week view
 */
function renderCalendarWeek() {
    const grid = document.getElementById('calendar-grid');
    grid.innerHTML = '';

    // Update week header
    const weekEnd = new Date(currentWeekStart);
    weekEnd.setDate(weekEnd.getDate() + 6);
    document.getElementById('week-header').textContent =
        `Week of ${formatDate(currentWeekStart)} - ${formatDate(weekEnd)}`;

    // Render 7 days
    for (let i = 0; i < 7; i++) {
        const currentDate = new Date(currentWeekStart);
        currentDate.setDate(currentDate.getDate() + i);

        const dayCard = createDayCard(currentDate);
        grid.appendChild(dayCard);
    }
}

/**
 * Create calendar day card
 */
function createDayCard(date) {
    const dayCard = document.createElement('div');
    dayCard.className = 'calendar-day';

    // Day header
    const dayHeader = document.createElement('div');
    dayHeader.className = 'day-header';

    const dayName = document.createElement('div');
    dayName.className = 'day-name';
    dayName.textContent = formatDayName(date);

    const dayDate = document.createElement('div');
    dayDate.className = 'day-date';
    dayDate.textContent = formatShortDate(date);

    dayHeader.appendChild(dayName);
    dayHeader.appendChild(dayDate);
    dayCard.appendChild(dayHeader);

    // Find workout for this date
    const dateStr = date.toISOString().split('T')[0];
    const workout = allWorkouts.find(w => w.date === dateStr);

    if (workout) {
        const workoutCard = createWorkoutCard(workout);
        dayCard.appendChild(workoutCard);
    } else {
        const noWorkout = document.createElement('div');
        noWorkout.className = 'workout-details';
        noWorkout.textContent = 'No workout scheduled';
        noWorkout.style.fontStyle = 'italic';
        dayCard.appendChild(noWorkout);
    }

    // Highlight today
    const today = new Date();
    if (date.toDateString() === today.toDateString()) {
        dayCard.style.border = '2px solid #3b82f6';
    }

    return dayCard;
}

/**
 * Create workout card
 */
function createWorkoutCard(workout) {
    const card = document.createElement('div');
    card.className = 'workout-card';
    if (workout.was_completed) {
        card.classList.add('workout-completed');
    }

    // Workout type
    const workoutType = document.createElement('div');
    workoutType.className = `workout-type ${workout.workout_type}`;
    workoutType.textContent = formatWorkoutType(workout.workout_type);
    card.appendChild(workoutType);

    // Description
    if (workout.description) {
        const description = document.createElement('div');
        description.className = 'workout-details';
        description.textContent = workout.description;
        card.appendChild(description);
    }

    // Workout meta (distance, duration, intensity)
    const meta = document.createElement('div');
    meta.className = 'workout-meta';

    if (workout.target_distance_meters) {
        const distanceBadge = document.createElement('span');
        distanceBadge.className = 'workout-badge';
        distanceBadge.textContent = `${(workout.target_distance_meters / 1000).toFixed(1)} km`;
        meta.appendChild(distanceBadge);
    }

    if (workout.target_duration_minutes) {
        const durationBadge = document.createElement('span');
        durationBadge.className = 'workout-badge';
        durationBadge.textContent = `${workout.target_duration_minutes} min`;
        meta.appendChild(durationBadge);
    }

    if (workout.intensity_level) {
        const intensityBadge = document.createElement('span');
        intensityBadge.className = 'workout-badge';
        intensityBadge.textContent = `Intensity: ${workout.intensity_level}/10`;
        meta.appendChild(intensityBadge);
    }

    if (meta.children.length > 0) {
        card.appendChild(meta);
    }

    // Completion checkbox
    const checkboxContainer = document.createElement('div');
    checkboxContainer.className = 'completion-checkbox';
    checkboxContainer.onclick = (e) => {
        e.stopPropagation();
        toggleWorkoutCompletion(workout.id, !workout.was_completed);
    };

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = workout.was_completed;
    checkbox.onclick = (e) => e.stopPropagation();

    const label = document.createElement('span');
    label.className = 'completion-label';
    label.textContent = workout.was_completed ? 'Completed' : 'Mark complete';

    checkboxContainer.appendChild(checkbox);
    checkboxContainer.appendChild(label);
    card.appendChild(checkboxContainer);

    return card;
}

/**
 * Toggle workout completion status
 */
async function toggleWorkoutCompletion(workoutId, completed) {
    try {
        const requestBody = {
            completed: completed,
            completed_at: completed ? new Date().toISOString() : null
        };

        // If completing, ask for details
        if (completed) {
            const duration = prompt('Actual duration (minutes):');
            const distance = prompt('Actual distance (km):');
            const notes = prompt('Notes (optional):');

            if (duration) requestBody.actual_duration_min = parseInt(duration);
            if (distance) requestBody.actual_distance_km = parseFloat(distance);
            if (notes) requestBody.notes = notes;
        }

        const response = await fetch(`/api/training/workouts/${workoutId}/complete`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            throw new Error(`Failed to update workout: ${response.statusText}`);
        }

        const updatedWorkout = await response.json();

        // Update local state
        const index = allWorkouts.findIndex(w => w.id === workoutId);
        if (index !== -1) {
            allWorkouts[index] = updatedWorkout;
        }

        // Re-render calendar
        renderCalendarWeek();

    } catch (error) {
        console.error('Error updating workout:', error);
        showError('Failed to update workout. Please try again.');
    }
}

/**
 * Generate new training plan
 */
async function generatePlan(event) {
    event.preventDefault();

    const generateBtn = document.getElementById('generate-btn');
    const originalText = generateBtn.textContent;

    try {
        // Disable button and show loading
        generateBtn.disabled = true;
        generateBtn.innerHTML = '<span class="loading-spinner"></span> Generating...';

        // Gather form data
        const formData = {
            name: document.getElementById('plan-name-input').value,
            goal: document.getElementById('goal-select').value,
            start_date: document.getElementById('start-date-input').value,
            target_date: document.getElementById('target-date-input').value,
            current_fitness_level: parseInt(document.getElementById('fitness-level-input').value) || 50,
            weekly_volume_km: parseFloat(document.getElementById('weekly-volume-input').value) || 30,
            notes: document.getElementById('notes-input').value || null
        };

        // Validate dates
        if (new Date(formData.target_date) <= new Date(formData.start_date)) {
            throw new Error('Target date must be after start date');
        }

        const response = await fetch('/api/training/plans/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData)
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to generate plan');
        }

        const newPlan = await response.json();

        // Reset form and reload
        document.getElementById('generate-plan-form').reset();
        hideGenerateForm();
        loadCurrentPlan();

    } catch (error) {
        console.error('Error generating plan:', error);
        showError(error.message || 'Failed to generate training plan. Please try again.');
    } finally {
        // Re-enable button
        generateBtn.disabled = false;
        generateBtn.textContent = originalText;
    }
}

/**
 * Deactivate current plan
 */
async function deactivatePlan() {
    if (!currentPlan) return;

    if (!confirm('Are you sure you want to deactivate this training plan?')) {
        return;
    }

    try {
        const response = await fetch(`/api/training/plans/${currentPlan.id}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error('Failed to deactivate plan');
        }

        currentPlan = null;
        allWorkouts = [];
        showNoPlanView();

    } catch (error) {
        console.error('Error deactivating plan:', error);
        showError('Failed to deactivate plan. Please try again.');
    }
}

/**
 * Navigation functions
 */
function previousWeek() {
    currentWeekStart.setDate(currentWeekStart.getDate() - 7);
    renderCalendarWeek();
}

function nextWeek() {
    currentWeekStart.setDate(currentWeekStart.getDate() + 7);
    renderCalendarWeek();
}

function goToToday() {
    currentWeekStart = new Date();
    setToStartOfWeek(currentWeekStart);
    renderCalendarWeek();
}

/**
 * View management
 */
function showLoading() {
    document.getElementById('loading-plan').style.display = 'block';
    document.getElementById('no-plan-view').style.display = 'none';
    document.getElementById('plan-view').style.display = 'none';
    document.getElementById('generate-form-container').style.display = 'none';
}

function showNoPlanView() {
    document.getElementById('loading-plan').style.display = 'none';
    document.getElementById('no-plan-view').style.display = 'block';
    document.getElementById('plan-view').style.display = 'none';
    document.getElementById('generate-form-container').style.display = 'none';
}

function showPlanView() {
    document.getElementById('loading-plan').style.display = 'none';
    document.getElementById('no-plan-view').style.display = 'none';
    document.getElementById('plan-view').style.display = 'block';
    document.getElementById('generate-form-container').style.display = 'none';
}

function showGenerateForm() {
    document.getElementById('generate-form-container').style.display = 'block';
    window.scrollTo({ top: document.getElementById('generate-form-container').offsetTop, behavior: 'smooth' });
}

function hideGenerateForm() {
    document.getElementById('generate-form-container').style.display = 'none';
}

/**
 * Error handling
 */
function showError(message) {
    const errorContainer = document.getElementById('error-container');
    errorContainer.innerHTML = `<div class="error-message">${message}</div>`;
    setTimeout(() => {
        errorContainer.innerHTML = '';
    }, 5000);
}

/**
 * Formatting utilities
 */
function formatGoal(goal) {
    const goalMap = {
        '5k': '5K Race',
        '10k': '10K Race',
        'half_marathon': 'Half Marathon',
        'marathon': 'Marathon',
        'general_fitness': 'General Fitness'
    };
    return goalMap[goal] || goal;
}

function formatWorkoutType(type) {
    const typeMap = {
        'easy_run': 'Easy Run',
        'tempo': 'Tempo',
        'intervals': 'Intervals',
        'long_run': 'Long Run',
        'rest': 'Rest Day'
    };
    return typeMap[type] || type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
}

function formatDate(date) {
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

function formatShortDate(date) {
    return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric'
    });
}

function formatDayName(date) {
    return date.toLocaleDateString('en-US', { weekday: 'short' });
}
