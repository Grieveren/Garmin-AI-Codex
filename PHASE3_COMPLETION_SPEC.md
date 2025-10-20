# Phase 3 Completion Specification

**Branch:** `feature/phase3-completion`
**Goal:** Complete remaining 2% of Phase 3 Web Interface features
**Target:** 100% Phase 3 completion (currently 98%)
**Estimated Time:** 3-4 days

---

## Current Status

**Completed (98%):**
- ✅ Recommendation-first dashboard (2145 lines: HTML/CSS/JS)
- ✅ `/api/recommendations/today` endpoint with multi-language support
- ✅ Manual sync UI with MFA flow
- ✅ Responsive design with dark mode
- ✅ Enhanced metrics visualization
- ✅ Integration tests

**Missing (2%):**
- ⚠️ AI chat interface (template exists, needs JS + API)
- ⚠️ Analytics/insights dashboard (templates exist, needs router + charts)
- ⚠️ Training plan visualization (template exists, needs enhancement)
- ⚠️ Site-wide navigation (base template needs nav system)

---

## Feature 1: AI Chat Interface

**Priority:** High
**Estimated Time:** 1 day
**Status:** Partially complete (backend 70%, frontend 30%)

### Backend (Already Complete per Todo List)
- ✅ `chat_messages` database table created
- ✅ Chat router with streaming endpoint implemented
- ✅ Tests written for chat API
- ✅ Chat-specific prompt templates added

### Frontend (Needs Implementation)

#### File: `app/static/js/chat.js`
**What:** Interactive chat interface with server-sent events (SSE)

**Features Required:**
1. **Message Display**
   - Chat history rendering (user messages + AI responses)
   - Message bubbles with timestamps
   - Typing indicators during streaming
   - Auto-scroll to latest message

2. **SSE Streaming**
   - Connect to `/api/chat/stream` endpoint
   - Handle server-sent events for token-by-token streaming
   - Display streaming text in real-time
   - Handle connection errors and reconnection

3. **Input Handling**
   - Text input with "Send" button
   - Enter key to send (Shift+Enter for new line)
   - Disable input during streaming
   - Input validation (non-empty)

4. **Message History**
   - Load previous messages from API
   - Scroll pagination for long histories
   - Clear chat functionality

5. **Context Awareness**
   - Include recent training data in prompts
   - Display current readiness score in chat header
   - Quick action buttons ("Analyze today's workout", "Suggest modifications")

**API Endpoints (Already Implemented):**
- `POST /api/chat/send` - Send message, get streaming response
- `GET /api/chat/history` - Retrieve conversation history
- `DELETE /api/chat/clear` - Clear conversation

**Technical Requirements:**
- Use EventSource API for SSE
- Implement exponential backoff for reconnection
- Store conversation context in localStorage
- Markdown rendering for AI responses
- Mobile-responsive design

---

## Feature 2: Analytics/Insights Dashboard

**Priority:** High
**Estimated Time:** 1.5 days
**Status:** Not started (0%)

### Backend: Analytics Router

#### File: `app/routers/analytics.py` (New)
**What:** API endpoints for historical analytics and visualizations

**Required Endpoints:**

1. **`GET /api/analytics/readiness-trend`**
   - Query params: `days` (default 30), `start_date`, `end_date`
   - Returns: Time series of readiness scores with dates
   - Format: `[{"date": "2025-10-20", "score": 75, "recommendation": "moderate"}, ...]`

2. **`GET /api/analytics/training-load`**
   - Query params: `days` (default 90)
   - Returns: Training load metrics over time (ACWR, fitness, fatigue, form)
   - Format: `[{"date": "...", "acwr": 1.2, "fitness": 45, "fatigue": 38, "form": 7}, ...]`

3. **`GET /api/analytics/sleep-performance`**
   - Query params: `days` (default 30)
   - Returns: Sleep metrics correlated with performance
   - Format: `[{"date": "...", "sleep_score": 80, "hrv": 58, "readiness": 75}, ...]`

4. **`GET /api/analytics/activity-breakdown`**
   - Query params: `days` (default 30)
   - Returns: Activity type distribution (running, cycling, etc.) with volumes
   - Format: `{"running": {"count": 12, "distance": 85.4, "time": 720}, ...}`

5. **`GET /api/analytics/recovery-correlation`**
   - Query params: `metric` (hrv|sleep|rhr), `days` (default 30)
   - Returns: Correlation between recovery metric and performance
   - Format: `{"correlation": 0.72, "data": [{"metric_value": 58, "readiness": 75}, ...]}`

**Technical Requirements:**
- Efficient database queries with date range filtering
- Caching for expensive calculations (60-minute cache)
- Pagination for large datasets
- Error handling for missing data

### Frontend: Insights Dashboard

#### File: `app/templates/insights.html` (Enhance)
**What:** Interactive analytics dashboard with Plotly charts

**Required Charts:**

1. **Readiness Trend Chart** (Line chart)
   - 30-day readiness score with color-coded zones
   - Markers for workouts (hover shows details)
   - Recommendation overlay (high/moderate/easy/rest)

2. **Training Load Chart** (Multi-line chart)
   - ACWR, Fitness, Fatigue, Form lines
   - Optimal ACWR zone shading (0.8-1.3)
   - Danger zone highlighting (>1.5)

3. **Sleep-Performance Correlation** (Scatter plot with trendline)
   - X-axis: Sleep score
   - Y-axis: Readiness score
   - Point size: HRV value
   - Trendline with R² value

4. **Activity Breakdown** (Pie chart + bar chart)
   - Pie: Activity type distribution by time
   - Bar: Distance by activity type

5. **Weekly Summary Table**
   - Rows: Last 8 weeks
   - Columns: Total distance, time, avg readiness, hard sessions, rest days
   - Sortable columns

#### File: `app/static/js/insights.js` (New)
**What:** JavaScript for fetching analytics data and rendering Plotly charts

**Features Required:**
1. **Data Fetching**
   - Fetch all analytics endpoints on page load
   - Show loading spinners during fetch
   - Handle errors gracefully

2. **Chart Rendering**
   - Use Plotly.js for interactive charts
   - Responsive layouts (adapt to screen size)
   - Dark mode compatible color schemes
   - Export buttons (PNG download)

3. **Date Range Selector**
   - Dropdown: 7 days, 30 days, 90 days, custom
   - Date pickers for custom range
   - Refresh charts on date change

4. **Interactivity**
   - Hover tooltips with detailed info
   - Click chart points to see workout details
   - Zoom and pan on charts

**Technical Requirements:**
- Use Plotly.js CDN (no build step)
- Efficient data transformation
- Debounced API calls on date changes
- LocalStorage for user preferences (date range, chart visibility)

---

## Feature 3: Training Plan Visualization

**Priority:** Medium
**Estimated Time:** 0.5 days
**Status:** Placeholder only (5%)

### Backend: Training Plan Router

#### File: `app/routers/training_plans.py` (New or enhance existing)
**What:** API endpoints for training plan management

**Required Endpoints:**

1. **`GET /api/training/plans/current`**
   - Returns: Active training plan with upcoming workouts
   - Format: `{"plan": {...}, "workouts": [{"date": "...", "type": "interval", ...}, ...]}`

2. **`GET /api/training/plans/{plan_id}`**
   - Returns: Full plan details with all workouts

3. **`POST /api/training/plans/generate`**
   - Body: `{"goal": "5k", "target_date": "2025-12-01", "current_fitness": 65}`
   - Returns: Generated training plan
   - Note: Uses existing `TrainingPlanner` service

4. **`PUT /api/training/workouts/{workout_id}/complete`**
   - Body: `{"actual_duration": 45, "actual_distance": 8.5, "notes": "Felt strong"}`
   - Returns: Updated workout with completion status

### Frontend: Training Plan Page

#### File: `app/templates/training_plan.html` (Enhance)
**What:** Visual calendar of planned workouts with progress tracking

**Features Required:**

1. **Weekly Calendar View**
   - 7-day grid showing upcoming workouts
   - Color-coded by workout type (easy/tempo/interval/long/rest)
   - Hover shows workout details
   - Click to mark complete or modify

2. **Plan Overview**
   - Plan name, goal, target date
   - Current phase (base/build/peak/taper)
   - Progress bar (weeks completed / total weeks)
   - Key metrics: total planned distance, time, hard sessions

3. **Workout Cards**
   - Daily workout details in expandable cards
   - Structure (warmup, main set, cooldown)
   - Target HR zones, pace, duration
   - Completion checkbox
   - Notes section

4. **Plan Generation Form**
   - Goal selector (5K, 10K, half marathon, marathon, general fitness)
   - Target date picker
   - Current fitness level slider
   - "Generate Plan" button

#### File: `app/static/js/training_plan.js` (New)
**What:** JavaScript for calendar rendering and plan interaction

**Features Required:**
- Render weekly calendar from API data
- Handle workout completion (AJAX PUT request)
- Plan generation form handling
- Progress tracking visualization

---

## Feature 4: Site Navigation System

**Priority:** High (Foundation for other features)
**Estimated Time:** 0.5 days
**Status:** Missing (0%)

### File: `app/templates/base.html` (Rewrite)
**What:** Base template with navigation bar

**Required Structure:**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}AI Training Optimizer{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('static', path='/css/base.css') }}">
    <link rel="stylesheet" href="{{ url_for('static', path='/css/dashboard.css') }}">
    {% block extra_css %}{% endblock %}
</head>
<body>
    <nav class="navbar">
        <div class="nav-brand">
            <a href="/">🏃 AI Training Optimizer</a>
        </div>
        <div class="nav-links">
            <a href="/" class="nav-link {% if request.url.path == '/' %}active{% endif %}">Dashboard</a>
            <a href="/insights" class="nav-link {% if request.url.path == '/insights' %}active{% endif %}">Analytics</a>
            <a href="/training-plan" class="nav-link {% if request.url.path == '/training-plan' %}active{% endif %}">Training Plan</a>
            <a href="/chat" class="nav-link {% if request.url.path == '/chat' %}active{% endif %}">AI Coach</a>
            <a href="/manual/sync/now" class="nav-link">Sync</a>
        </div>
        <div class="nav-actions">
            <button id="theme-toggle" class="nav-btn">🌙</button>
            <button id="language-toggle" class="nav-btn">🇬🇧</button>
        </div>
    </nav>

    <main class="main-container">
        {% block content %}{% endblock %}
    </main>

    <footer class="footer">
        <p>&copy; 2025 AI Training Optimizer · Powered by Claude AI</p>
    </footer>

    <script src="{{ url_for('static', path='/js/base.js') }}"></script>
    {% block extra_js %}{% endblock %}
</body>
</html>
```

### File: `app/static/css/base.css` (New)
**What:** Base styles for navigation and layout

**Required Styles:**
- Sticky navigation bar
- Responsive hamburger menu for mobile
- Active link highlighting
- Dark mode support
- Footer styling
- Container widths and padding

### File: `app/static/js/base.js` (New)
**What:** Shared JavaScript for navigation and theme

**Features Required:**
- Theme toggle (persist to localStorage)
- Language toggle (persist to localStorage)
- Mobile menu toggle
- Active link highlighting

---

## Feature 5: Route Registration

### File: `app/main.py` (Update)
**What:** Register new routes for chat, insights, training plan pages

**Required Updates:**

```python
from app.routers import analytics, training_plans

# HTML pages
@app.get("/insights", response_class=HTMLResponse, tags=["dashboard"])
async def insights_page(request: Request) -> HTMLResponse:
    """Analytics and insights dashboard."""
    return templates.TemplateResponse("insights.html", {"request": request})

@app.get("/training-plan", response_class=HTMLResponse, tags=["dashboard"])
async def training_plan_page(request: Request) -> HTMLResponse:
    """Training plan calendar and management."""
    return templates.TemplateResponse("training_plan.html", {"request": request})

@app.get("/chat", response_class=HTMLResponse, tags=["dashboard"])
async def chat_page(request: Request) -> HTMLResponse:
    """AI coach chat interface."""
    return templates.TemplateResponse("chat.html", {"request": request})

# Include routers
app.include_router(analytics.router)
app.include_router(training_plans.router)
# chat router already included per todo list
```

---

## Feature 6: End-to-End Testing

**Priority:** High
**Estimated Time:** 0.5 days
**Status:** Not started

### File: `tests/test_analytics_api.py` (New)
**What:** Integration tests for analytics endpoints

**Required Tests:**
- Test each analytics endpoint returns expected format
- Test date range filtering
- Test caching behavior
- Test error handling (missing data)

### File: `tests/test_training_plan_api.py` (New)
**What:** Integration tests for training plan endpoints

**Required Tests:**
- Test current plan retrieval
- Test plan generation
- Test workout completion
- Test plan adaptation

### File: `tests/test_navigation.py` (New)
**What:** UI/integration tests for navigation

**Required Tests:**
- Test all nav links accessible
- Test active link highlighting
- Test mobile menu toggle
- Test theme persistence

---

## Implementation Plan

### Parallel Agent Execution Strategy

**3 Agents Running Concurrently:**

1. **Agent 1: Frontend Developer (Chat + Navigation)**
   - Task 1A: Create `app/static/js/chat.js` with SSE streaming
   - Task 1B: Enhance `app/templates/chat.html` with message UI
   - Task 1C: Rewrite `app/templates/base.html` with navigation
   - Task 1D: Create `app/static/css/base.css` and `app/static/js/base.js`

2. **Agent 2: Frontend Developer (Analytics Dashboard)**
   - Task 2A: Implement `app/routers/analytics.py` with 5 endpoints
   - Task 2B: Enhance `app/templates/insights.html` with Plotly charts
   - Task 2C: Create `app/static/js/insights.js` with chart rendering
   - Task 2D: Test analytics endpoints

3. **Agent 3: Backend/Full-Stack (Training Plan + Integration)**
   - Task 3A: Implement `app/routers/training_plans.py` with CRUD endpoints
   - Task 3B: Enhance `app/templates/training_plan.html` with calendar view
   - Task 3C: Create `app/static/js/training_plan.js` with calendar logic
   - Task 3D: Update `app/main.py` with route registration
   - Task 3E: Write integration tests for all new features

---

## Success Criteria

**Phase 3 Completion Checklist:**
- [ ] AI chat interface functional with streaming responses
- [ ] Analytics dashboard with 5 interactive Plotly charts
- [ ] Training plan calendar with workout tracking
- [ ] Site-wide navigation bar with active link highlighting
- [ ] All HTML pages use `base.html` template
- [ ] Dark mode works across all pages
- [ ] Mobile responsive design for all new pages
- [ ] Integration tests pass for all new features
- [ ] No console errors on any page
- [ ] All features documented in README

**Definition of Done:**
- All code merged to `feature/phase3-completion` branch
- All tests passing
- No linting errors
- README updated with new features
- ROADMAP.md updated to reflect 100% Phase 3 completion

---

## Dependencies

**Python Packages (Add to requirements.txt if needed):**
- `plotly` (for server-side chart generation, optional)
- No new dependencies expected (using Plotly.js CDN)

**Frontend Libraries:**
- Plotly.js CDN: `https://cdn.plot.ly/plotly-2.26.0.min.js`
- Already using: dashboard.js patterns, fetch API, EventSource

**Database:**
- No schema changes expected (all tables already exist per todo list)
- May need indexes on date columns for analytics queries

---

## Technical Considerations

1. **SSE Streaming:**
   - Ensure CORS configured for EventSource
   - Implement heartbeat to keep connection alive
   - Handle browser connection limits (6 per domain)

2. **Chart Performance:**
   - Lazy load Plotly.js (only on insights page)
   - Debounce chart updates on date range changes
   - Limit data points for large datasets (downsample if >1000 points)

3. **Mobile Responsive:**
   - Hamburger menu for navigation on small screens
   - Single-column layout for charts on mobile
   - Touch-friendly workout calendar

4. **Dark Mode:**
   - Plotly dark theme (`template: 'plotly_dark'`)
   - CSS variables for easy theme switching
   - Persist theme choice across pages

5. **Accessibility:**
   - ARIA labels on all interactive elements
   - Keyboard navigation for calendar
   - Screen reader announcements for streaming chat

---

## File Structure Summary

**New Files:**
```
app/
├── routers/
│   ├── analytics.py         # New: 5 analytics endpoints
│   └── training_plans.py    # New: CRUD for training plans
├── static/
│   ├── css/
│   │   └── base.css         # New: Navigation and base styles
│   └── js/
│       ├── base.js          # New: Shared navigation logic
│       ├── chat.js          # New: SSE chat interface
│       ├── insights.js      # New: Plotly chart rendering
│       └── training_plan.js # New: Calendar interaction
└── templates/
    └── base.html            # Rewrite: With navigation

tests/
├── test_analytics_api.py    # New: Analytics endpoint tests
├── test_training_plan_api.py # New: Training plan tests
└── test_navigation.py       # New: UI navigation tests
```

**Modified Files:**
```
app/
├── main.py                  # Add route registration
└── templates/
    ├── chat.html            # Enhance: Add full chat UI
    ├── insights.html        # Enhance: Add Plotly charts
    ├── training_plan.html   # Enhance: Add calendar view
    └── dashboard.html       # Update: Use base.html extends
```

---

## Estimated Timeline

| Task | Agent | Time | Dependencies |
|------|-------|------|--------------|
| Base template + nav | Agent 1 | 2 hours | None |
| Chat interface | Agent 1 | 4 hours | Base template |
| Analytics router | Agent 2 | 3 hours | None |
| Insights dashboard | Agent 2 | 5 hours | Analytics router |
| Training plan router | Agent 3 | 3 hours | None |
| Training plan UI | Agent 3 | 4 hours | Training plan router |
| Route registration | Agent 3 | 1 hour | All routers |
| Integration testing | Agent 3 | 3 hours | All features |
| **Total** | - | **25 hours** | **~3-4 days** |

---

## Launch Command

**Start 3 agents in parallel:**
```bash
# Agent 1: Chat + Navigation
Task(subagent_type="frontend-mobile-development:frontend-developer",
     prompt="Implement chat interface and navigation system per PHASE3_COMPLETION_SPEC.md sections 1 & 4")

# Agent 2: Analytics Dashboard
Task(subagent_type="frontend-mobile-development:frontend-developer",
     prompt="Implement analytics dashboard per PHASE3_COMPLETION_SPEC.md section 2")

# Agent 3: Training Plan + Integration
Task(subagent_type="backend-development:backend-architect",
     prompt="Implement training plan system and integration tests per PHASE3_COMPLETION_SPEC.md sections 3, 5, 6")
```

---

**Next Steps:**
1. Review this spec
2. Launch agents in parallel
3. Monitor progress
4. Integrate completed work
5. Run full test suite
6. Update documentation
7. Merge to main

---

**Questions/Clarifications Needed:**
- None (spec is comprehensive)

**Ready to Execute:** ✅
