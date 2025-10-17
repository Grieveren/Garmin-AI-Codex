# Historical Data Setup Guide

## Overview

We've implemented a **30-day historical baseline system** that dramatically improves AI recommendation quality by comparing your metrics against YOUR personal baselines, not population averages.

## What's Changed

### **Before** (Stateless):
- Analyzed only last 7 days of activities
- No HRV/sleep/HR baselines
- Generic recommendations based on population norms
- ~8-12 second response time

### **After** (With Historical Data):
- 30-day baselines for HRV, resting HR, sleep patterns
- ACWR (Acute:Chronic Workload Ratio) for injury prevention
- Training trend analysis (consecutive days, volume changes)
- Personalized recommendations based on YOUR normal ranges
- ~2-3 second response time (after initial backfill)

## Setup Instructions

### Step 1: Run the Backfill Script

This one-time operation fetches your last 30 days of Garmin data and saves it to the database:

```bash
# Backfill 30 days (default)
python scripts/backfill_data.py

# Or with MFA code if needed
python scripts/backfill_data.py --mfa-code 123456

# Or backfill 60 days for even better baselines
python scripts/backfill_data.py --days 60
```

**Expected output:**
```
Creating database tables...
🔐 Connecting to Garmin Connect...
✅ Logged in successfully

📅 Backfilling data from 2025-09-17 to 2025-10-17 (30 days)
============================================================

Fetching daily metrics...
  [1/30] 2025-09-17... ✅ Saved
  [2/30] 2025-09-18... ✅ Saved
  ...
  [30/30] 2025-10-17... ✅ Saved

Fetching activities...
Found 45 activities in the last 30 days
✅ Saved 45 activities

============================================================
📊 Summary:
  Daily Metrics: 28 saved, 0 skipped, 2 failed
  Activities: 45 saved, 0 skipped

✅ Backfill complete!
```

### Step 2: Test the Enhanced Recommendations

Visit your dashboard: **http://127.0.0.1:8002/**

You should now see:
- More accurate readiness scores
- References to "30-day baseline" in AI reasoning
- ACWR injury risk assessment
- Personalized HRV deviation analysis
- Sleep debt calculations

### Step 3: Set Up Daily Sync (Optional)

To keep your data fresh, set up the daily sync script to run automatically:

```bash
# Manual daily sync (run once per day)
python scripts/sync_data.py

# Or add to crontab for 8 AM daily:
0 8 * * * cd /path/to/Garmin\ AI\ Codex && python scripts/sync_data.py
```

## What the AI Now Knows About You

With historical data, Claude AI receives context like:

```
HISTORICAL BASELINES (30-day analysis):
- HRV Analysis:
  * Current: 49ms
  * 30-day baseline: 52ms
  * 7-day average: 48ms
  * Deviation: -5.8%
  * Trend: decreasing
  * ⚠️ Concerning: NO

- Resting Heart Rate:
  * Current: 58 bpm
  * Baseline: 56 bpm
  * Deviation: +2 bpm
  * ⚠️ Elevated: NO

- Sleep Pattern:
  * Current: 6.1 hours
  * Baseline: 7.2 hours
  * 7-day average: 6.5 hours
  * Weekly sleep debt: -4.9 hours
  * ⚠️ Sleep deprived: YES

- Training Load (ACWR):
  * Acute load (7 days): 285
  * Chronic load (28 days): 320
  * ACWR Ratio: 0.89
  * Status: optimal
  * Injury risk: LOW

- Training Trends:
  * Total activities: 28
  * Total distance: 185.3km
  * Average weekly distance: 43.6km/week
  * Consecutive training days: 7 days
  * ⚠️ No rest days: YES - overtraining risk!
```

## Key Improvements

### 1. **HRV Baseline Detection**
- Compares your current HRV to YOUR 30-day average
- Detects >10% drops (illness/overtraining indicator)
- Tracks 7-day trend (increasing/decreasing/stable)

### 2. **ACWR Injury Prevention**
- Monitors your acute load (last 7 days) vs chronic load (28 days)
- Optimal range: 0.8-1.3
- >1.5 = HIGH injury risk → AI will recommend reduced volume

### 3. **Sleep Debt Tracking**
- Calculates weekly sleep debt vs your baseline
- Detects cumulative sleep deprivation
- Recommends rest when debt >4 hours

### 4. **Training Pattern Recognition**
- Detects consecutive training days without rest
- Flags overtraining risk at 7+ days
- Tracks volume changes week-over-week

## Backward Compatibility

The system automatically detects if you have historical data:

**No historical data?** → Falls back to current stateless approach (last 7 days only)
**Historical data available?** → Uses enhanced 30-day baseline analysis

This means you can use the system immediately even before running the backfill script.

## Extending to 60 Days

Want even better baselines? Run the backfill with more days:

```bash
python scripts/backfill_data.py --days 60
```

This enables:
- More robust HRV baselines
- 42-day Fitness/Fatigue modeling (future enhancement)
- Better detection of long-term trends

## Troubleshooting

### "Login failed" error
- Run with MFA code: `python scripts/backfill_data.py --mfa-code 123456`
- Ensure `.env` has correct Garmin credentials

### "Failed to fetch data for some dates"
- Normal for dates with no Garmin data (device not worn)
- Script continues and saves available data

### Want to re-fetch data?
```bash
python scripts/backfill_data.py --force
```

## Next Steps

1. **Run the backfill** now to see immediate improvement in recommendations
2. **Compare before/after** - refresh your dashboard to see the difference
3. **Set up daily sync** to keep data fresh automatically
4. **Optional**: Extend to 60 days for even better baselines

---

## Technical Details

**Database Tables:**
- `daily_metrics` - HRV, resting HR, sleep, stress, body battery (30 days)
- `activities` - Full activity history with training load

**Baseline Calculations:**
- HRV: 30-day rolling average with trend analysis
- Resting HR: 30-day average with deviation threshold
- Sleep: 30-day average with 7-day debt calculation
- ACWR: 7-day acute / 28-day chronic ratio

**Storage:**
- ~2MB per year of data
- SQLite database (upgradeable to PostgreSQL)

**API Response Time:**
- First request after backfill: ~2-3 seconds (fast!)
- Without historical data: ~8-12 seconds (fetches live from Garmin)
