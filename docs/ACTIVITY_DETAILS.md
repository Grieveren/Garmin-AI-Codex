# Activity Detail Fetching

Comprehensive guide to fetching and analyzing detailed activity data from Garmin API.

## Overview

The Activity Detail system fetches granular performance data for individual workouts:
- **Splits**: Lap-by-lap pace, heart rate, and distance data
- **HR Zones**: Time spent in each heart rate zone
- **Weather**: Environmental conditions during the activity

This data enables advanced analysis like:
- Pace consistency scoring
- Heart rate drift calculation
- Zone-based training analysis
- Weather impact on performance

## Architecture

### Components

**GarminService** (`app/services/garmin_service.py`)
- `get_activity_splits(activity_id)` - Fetch lap/split data
- `get_activity_hr_zones(activity_id)` - Fetch HR zone distribution
- `get_activity_weather(activity_id)` - Fetch weather conditions
- `get_detailed_activity_analysis(activity_id)` - Fetch all data in one call

**ActivityDetailHelper** (`app/services/activity_detail_helper.py`)
- Calculates derived metrics (pace consistency, HR drift)
- Manages cache validation logic
- Stores/updates database records

**ActivityDetailService** (`app/services/activity_detail_service.py`)
- High-level orchestration service
- Combines API calls with caching
- Bulk fetch capabilities with rate limiting

**Database Model** (`app/models/database_models.py`)
- `ActivityDetail` table with JSON columns for flexibility
- Foreign key to `Activity` table
- Derived metric columns for quick queries

## Database Schema

```python
class ActivityDetail(Base):
    __tablename__ = "activity_details"

    id: int
    activity_id: int  # FK to activities table

    # Raw API data (JSON)
    splits_data: dict | None
    hr_zones_data: dict | None
    weather_data: dict | None

    # Derived metrics
    pace_consistency_score: float | None  # 0-100
    hr_drift_percent: float | None  # % change

    # Cache management
    fetched_at: datetime
    is_complete: bool
    fetch_errors: str | None  # JSON array
```

## Usage Examples

### Fetch Single Activity

```python
from app.services.garmin_service import GarminService
from app.services.activity_detail_service import ActivityDetailService
from app.database import SessionLocal

# Initialize
garmin = GarminService()
garmin.login(mfa_code="123456")
session = SessionLocal()
service = ActivityDetailService(garmin, session)

# Fetch details
result = service.fetch_and_store_details(activity_id=12345678)

print(f"Cached: {result['cached']}")
print(f"Complete: {result['is_complete']}")
print(f"Pace Consistency: {result['pace_consistency_score']}/100")
print(f"HR Drift: {result['hr_drift_percent']}%")

# Access raw data
if result['splits']:
    laps = result['splits']['lapDTOs']
    for i, lap in enumerate(laps, 1):
        print(f"Lap {i}: {lap['distance']}m in {lap['duration']}s")
```

### Bulk Fetch Recent Activities

```python
# Fetch details for last 30 days
from datetime import date, timedelta

start_date = date.today() - timedelta(days=30)
activities = session.query(Activity).filter(Activity.date >= start_date).all()
activity_ids = [a.id for a in activities]

# Bulk fetch with rate limiting
summary = service.bulk_fetch_recent_activities(activity_ids, limit=20)

print(f"Fetched: {summary['fetched']}")
print(f"Cached: {summary['cached']}")
print(f"Failed: {summary['failed']}")
```

### Using CLI Script

```bash
# Fetch single activity
python scripts/fetch_activity_details.py --activity-id 12345678

# Fetch recent activities (last 30 days, max 20 API calls)
python scripts/fetch_activity_details.py --recent-days 30 --limit 20

# Force refetch (ignore cache)
python scripts/fetch_activity_details.py --activity-id 12345678 --force

# With MFA code
python scripts/fetch_activity_details.py --activity-id 12345678 --mfa-code 123456
```

## Derived Metrics

### Pace Consistency Score

Measures how evenly paced an activity was (0-100 scale).

**Algorithm:**
1. Extract pace (sec/km) for each lap
2. Calculate coefficient of variation (CV) = (std_dev / mean) * 100
3. Convert to score: `score = max(0, min(100, 100 - (cv * 5)))`

**Interpretation:**
- 90-100: Excellent consistency (elite pacing)
- 75-89: Good consistency (well-paced effort)
- 60-74: Fair consistency (some variation)
- <60: Poor consistency (erratic pacing)

**Example:**
```python
# Perfect pacing (300s per lap)
laps = [300, 300, 300, 300]  # CV = 0%, Score = 100

# Good pacing (minor variation)
laps = [300, 305, 295, 302]  # CV ~2%, Score ~90

# Poor pacing (large variation)
laps = [280, 320, 290, 350]  # CV ~10%, Score ~50
```

### HR Drift

Percentage change in heart rate from start to finish.

**Algorithm:**
1. Get first lap average HR
2. Get last lap average HR
3. Calculate: `drift = ((last_hr - first_hr) / first_hr) * 100`

**Interpretation:**
- Positive drift (+): Heart rate increased (aerobic decoupling, heat stress, dehydration)
- Negative drift (-): Heart rate decreased (warm-up effect, improved efficiency)
- Low drift (<3%): Good cardiovascular efficiency
- High drift (>10%): Potential overexertion or environmental stress

**Example:**
```python
# Good efficiency (low drift)
first_hr = 150, last_hr = 153  # Drift = +2.0%

# Aerobic decoupling (high drift)
first_hr = 145, last_hr = 165  # Drift = +13.8%

# Warm-up effect (negative drift)
first_hr = 155, last_hr = 148  # Drift = -4.5%
```

## Caching Strategy

### Cache Validation

**Complete Data (is_complete=True):**
- Cache valid for 24 hours
- Refetch after 24 hours (data rarely changes)

**Incomplete Data (is_complete=False):**
- Cache valid for 1 hour
- Retry after 1 hour (some API calls may have failed temporarily)

**Force Refetch:**
- `force_refetch=True` bypasses all cache checks
- Useful for manual sync or debugging

### Cache Logic

```python
def should_refetch(detail: ActivityDetail | None, force: bool) -> bool:
    if force:
        return True

    if detail is None:
        return True  # No cache, must fetch

    if not detail.is_complete:
        age = now() - detail.fetched_at
        if age > 1 hour:
            return True  # Retry incomplete data

    if detail.is_complete:
        age = now() - detail.fetched_at
        if age < 24 hours:
            return False  # Fresh cache, skip

    return True  # Default to refetch
```

## Error Handling

### Graceful Degradation

Each API call (splits, HR zones, weather) is independent:
- If splits fail, HR zones and weather still attempted
- Partial data is stored (better than nothing)
- `is_complete` flag indicates success level

**Example:**
```python
result = service.fetch_and_store_details(12345678)

# Partial success
result = {
    "splits": {...},      # Success
    "hr_zones": None,     # Failed
    "weather": None,      # Failed
    "is_complete": False,
    "errors": ["hr_zones", "weather"]
}
```

### Common Failures

**Splits not available:**
- Strength training (no laps/splits)
- Manual activities
- Activities without auto-lap

**HR zones not available:**
- Activity without HR monitor
- HR data not recorded

**Weather not available:**
- Indoor activities (no GPS)
- Old activities (weather data purged)
- API rate limiting

## Performance Considerations

### API Rate Limiting

Garmin API has undocumented rate limits. Best practices:
- Use `limit` parameter in bulk fetches
- Space out API calls (built-in delays)
- Respect cache to minimize calls

**Example:**
```python
# Fetch 100 activities, but limit to 20 API calls
summary = service.bulk_fetch_recent_activities(
    activity_ids,
    limit=20  # Only 20 new fetches, rest from cache
)
```

### Database Storage

JSON columns provide flexibility but increase storage:
- **Splits**: ~2-10KB per activity (depends on lap count)
- **HR zones**: ~500 bytes per activity
- **Weather**: ~300 bytes per activity

**Optimization:**
- Limit historical backfill (only recent activities)
- Periodically purge old details (>1 year)

## Testing

### Unit Tests

```bash
# Run all activity detail tests
python -m pytest tests/test_activity_details.py -v

# Run specific test class
python -m pytest tests/test_activity_details.py::TestActivityDetailHelper -v

# Run with coverage
python -m pytest tests/test_activity_details.py --cov=app.services
```

### Test Coverage

23 comprehensive tests covering:
- Pace consistency calculation (good, poor, edge cases)
- HR drift calculation (positive, negative, edge cases)
- Cache validation logic
- Database CRUD operations
- Bulk fetch with rate limiting
- Error handling and graceful degradation

## Integration with AI Analysis

**Future Use Cases:**

1. **Pacing Analysis**: Include pace consistency in readiness assessment
   ```python
   if pace_consistency < 60:
       recommendation = "Focus on even pacing in next run"
   ```

2. **HR Drift Alerts**: Detect aerobic decoupling
   ```python
   if hr_drift > 10:
       alert = "High HR drift indicates fatigue or heat stress"
   ```

3. **Weather Impact**: Correlate performance with conditions
   ```python
   if temperature > 25 and pace_consistency < 70:
       insight = "Heat may have affected pacing"
   ```

4. **Zone Training**: Optimize training intensity
   ```python
   zone_3_percent = hr_zones["zone_3"] / total_time
   if zone_3_percent > 0.8:
       recommendation = "Good tempo run execution"
   ```

## Troubleshooting

### "No splits data returned"

**Cause:** Activity type doesn't support splits (e.g., strength training)

**Solution:** This is expected. Check `activity_type` before fetching.

### "Failed to fetch HR zones"

**Cause:** Activity without HR monitor or data not recorded

**Solution:** Verify HR data exists in main activity record first.

### "All API calls failed"

**Cause:** Network issue, Garmin API down, or rate limiting

**Solution:**
- Check Garmin service status
- Wait 15-30 minutes before retry
- Verify authentication tokens

### "Database unique constraint violation"

**Cause:** Attempting to create duplicate `ActivityDetail` record

**Solution:** Use `create_or_update()` instead of creating new records.

## API Reference

### GarminService Methods

```python
def get_activity_splits(activity_id: int) -> dict | None:
    """Fetch lap/split data."""

def get_activity_hr_zones(activity_id: int) -> dict | None:
    """Fetch HR zone distribution."""

def get_activity_weather(activity_id: int) -> dict | None:
    """Fetch weather conditions."""

def get_detailed_activity_analysis(activity_id: int) -> dict:
    """Fetch all detailed data (splits + HR zones + weather)."""
```

### ActivityDetailService Methods

```python
def fetch_and_store_details(
    activity_id: int,
    force_refetch: bool = False
) -> dict:
    """Main entry point for fetching and caching."""

def get_cached_details(activity_id: int) -> dict | None:
    """Retrieve cached data without API call."""

def bulk_fetch_recent_activities(
    activity_ids: list[int],
    limit: int | None = None
) -> dict:
    """Fetch multiple activities with rate limiting."""
```

### ActivityDetailHelper Methods

```python
@staticmethod
def calculate_pace_consistency(splits_data: dict) -> float | None:
    """Calculate pace consistency score (0-100)."""

@staticmethod
def calculate_hr_drift(hr_zones_data: dict, splits_data: dict) -> float | None:
    """Calculate HR drift percentage."""

@staticmethod
def should_refetch(detail: ActivityDetail, force: bool) -> bool:
    """Determine if cache is valid."""

@staticmethod
def create_or_update(
    session: Session,
    activity_id: int,
    splits_data: dict | None,
    hr_zones_data: dict | None,
    weather_data: dict | None,
    errors: list[str]
) -> ActivityDetail:
    """Store/update activity details in database."""
```

## Next Steps

**Immediate:**
- Create database migration for `activity_details` table
- Integrate with existing sync scripts
- Add API endpoints for web UI

**Future Enhancements:**
- Auto-fetch details during daily sync
- Activity detail visualization in dashboard
- AI analysis integration for pacing recommendations
- Historical trend analysis (consistency over time)
