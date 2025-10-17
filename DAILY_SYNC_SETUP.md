# Daily Sync Setup Guide

## Overview

This guide shows you how to set up automated daily syncing of your Garmin data at 7 AM.

## What Gets Synced

The daily sync script (`scripts/sync_data.py`) automatically:
- Fetches **yesterday's** Garmin data (HRV, sleep, activities, etc.)
- Saves it to the database
- Updates your historical baselines for better AI recommendations

**Why yesterday?** Garmin data for a given day is most accurate and complete the following day after all processing is done.

## Setup Methods

### Option 1: macOS/Linux Cron (Recommended)

1. **Open your crontab editor:**
```bash
crontab -e
```

2. **Add this line for 7 AM daily sync:**
```bash
0 7 * * * cd "/Users/brettgray/Coding/Garmin AI Codex" && /usr/local/bin/python3 scripts/sync_data.py >> /Users/brettgray/Coding/Garmin\ AI\ Codex/logs/sync.log 2>&1
```

3. **Save and exit** (`:wq` in vim)

4. **Verify cron is scheduled:**
```bash
crontab -l
```

**Cron format explanation:**
```
0 7 * * *  =  At 7:00 AM every day
│ │ │ │ │
│ │ │ │ └─── Day of week (0-7, both 0 and 7 are Sunday)
│ │ │ └───── Month (1-12)
│ │ └─────── Day of month (1-31)
│ └───────── Hour (0-23)
└─────────── Minute (0-59)
```

**Note:** Make sure to update the path to match your Python installation:
```bash
# Find your Python path
which python3

# Common paths:
# macOS Homebrew: /usr/local/bin/python3 or /opt/homebrew/bin/python3
# macOS System: /usr/bin/python3
# Linux: /usr/bin/python3
```

### Option 2: macOS launchd (Alternative)

For macOS users who prefer launchd over cron:

1. **Create launch agent file:**
```bash
nano ~/Library/LaunchAgents/com.garmin.dailysync.plist
```

2. **Add this configuration:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.garmin.dailysync</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/python3</string>
        <string>/Users/brettgray/Coding/Garmin AI Codex/scripts/sync_data.py</string>
    </array>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>7</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>/Users/brettgray/Coding/Garmin AI Codex/logs/sync.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/brettgray/Coding/Garmin AI Codex/logs/sync.error.log</string>

    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
```

3. **Load the launch agent:**
```bash
launchctl load ~/Library/LaunchAgents/com.garmin.dailysync.plist
```

4. **Verify it's loaded:**
```bash
launchctl list | grep garmin
```

5. **Test it immediately (optional):**
```bash
launchctl start com.garmin.dailysync
```

### Option 3: Manual Daily Sync

If you prefer manual control, you can:

1. **Run the script manually each day:**
```bash
cd "/Users/brettgray/Coding/Garmin AI Codex"
python3 scripts/sync_data.py
```

2. **Or use the dashboard button:**
   - Open http://127.0.0.1:8002/
   - Click **"⬇️ Sync Data"** button in the header
   - This fetches yesterday's data and refreshes recommendations

## Logs

Sync logs are saved to:
```
/Users/brettgray/Coding/Garmin AI Codex/logs/sync.log
```

**View recent logs:**
```bash
tail -f logs/sync.log
```

**Check for errors:**
```bash
grep -i error logs/sync.log
```

## Troubleshooting

### Cron job not running?

1. **Check cron is enabled:**
```bash
# macOS: Grant Terminal full disk access
System Preferences > Security & Privacy > Full Disk Access > Add Terminal
```

2. **Check logs for errors:**
```bash
tail -f logs/sync.log
```

3. **Test the script manually:**
```bash
cd "/Users/brettgray/Coding/Garmin AI Codex"
python3 scripts/sync_data.py --verbose
```

### MFA token expired?

If you see "MFA code required" error:

```bash
python3 scripts/sync_data.py --mfa-code 123456
```

This re-authenticates and caches the token for another 30 days.

### No data for certain dates?

This is normal if:
- You didn't wear your Garmin watch
- Device wasn't synced to Garmin Connect
- Network issues prevented data upload

The script will continue and log which dates failed.

## Advanced Options

### Sync a specific date
```bash
python3 scripts/sync_data.py --date 2025-10-15
```

### Force overwrite existing data
```bash
python3 scripts/sync_data.py --force
```

### Verbose output
```bash
python3 scripts/sync_data.py --verbose
```

### Combine options
```bash
python3 scripts/sync_data.py --date 2025-10-15 --force --verbose
```

## Changing Sync Time

Want to sync at a different time? Just modify the cron schedule:

```bash
# 6 AM daily
0 6 * * * cd "/Users/brettgray/Coding/Garmin AI Codex" && python3 scripts/sync_data.py >> logs/sync.log 2>&1

# 8 PM daily
0 20 * * * cd "/Users/brettgray/Coding/Garmin AI Codex" && python3 scripts/sync_data.py >> logs/sync.log 2>&1

# Every 6 hours
0 */6 * * * cd "/Users/brettgray/Coding/Garmin AI Codex" && python3 scripts/sync_data.py >> logs/sync.log 2>&1
```

## Verifying It Works

After setup, wait until 7 AM the next day, then check:

1. **View logs:**
```bash
cat logs/sync.log
```

2. **Check database:**
```bash
python3 -c "
from app.database import SessionLocal
from app.models.database_models import DailyMetric
from datetime import date, timedelta

db = SessionLocal()
yesterday = date.today() - timedelta(days=1)
metric = db.query(DailyMetric).filter(DailyMetric.date == yesterday).first()

if metric:
    print(f'✅ Data synced for {yesterday}')
    print(f'   Steps: {metric.steps}')
    print(f'   Sleep: {metric.sleep_seconds/3600:.1f} hours' if metric.sleep_seconds else '   Sleep: N/A')
    print(f'   HRV: {metric.hrv_morning}' if metric.hrv_morning else '   HRV: N/A')
else:
    print(f'❌ No data found for {yesterday}')

db.close()
"
```

3. **Check dashboard recommendations:**
   - Open http://127.0.0.1:8002/
   - Look for "30-day baseline" references in AI Analysis section
   - This confirms historical data is being used

## Summary

**Quick Setup (macOS/Linux):**
```bash
# 1. Open crontab
crontab -e

# 2. Add this line (update Python path if needed)
0 7 * * * cd "/Users/brettgray/Coding/Garmin AI Codex" && /usr/local/bin/python3 scripts/sync_data.py >> /Users/brettgray/Coding/Garmin\ AI\ Codex/logs/sync.log 2>&1

# 3. Save and verify
crontab -l
```

**Done!** Your Garmin data will automatically sync every day at 7 AM.

**Manual sync anytime:** Use the "⬇️ Sync Data" button on the dashboard.

---

For more details on the data being synced, see `HISTORICAL_DATA_SETUP.md`.
