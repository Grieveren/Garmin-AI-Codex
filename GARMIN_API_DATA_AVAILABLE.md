# Garmin Connect API - Available Data Summary

**Library Version**: garminconnect==0.2.26
**Test Date**: 2025-10-17
**Status**: ✅ All core endpoints working

---

## ✅ AVAILABLE DATA FOR AI TRAINING OPTIMIZER

### 🏃 Daily Activity Metrics
- **Steps**: Total steps, distance, goal tracking
- **Calories**: Active, BMR, wellness, consumed, remaining
- **Activity Time**: Highly active, active, sedentary (in seconds)
- **Floors Climbed**: Floor count with timestamps
- **Distance**: Total distance in meters

**API Methods**: `get_stats()`, `get_steps_data()`, `get_floors()`

### ❤️ Heart Rate & HRV (CRITICAL FOR AI ANALYSIS)
- **Resting Heart Rate**: Daily resting HR (yours: 42 bpm)
- **Max Heart Rate**: Daily maximum
- **HRV (Heart Rate Variability)**:
  - HRV Summary with baseline values
  - Individual HRV readings throughout the day
  - Sleep-based HRV measurements
  - **Critical for recovery analysis**

**API Methods**: `get_heart_rates()`, `get_hrv_data()`

### 😴 Sleep Data (CRITICAL FOR RECOVERY)
- **Sleep Duration**: Total sleep time in seconds
- **Sleep Stages**:
  - Deep sleep minutes
  - Light sleep minutes
  - REM sleep minutes
  - Awake time
- **Sleep Quality Score**: 0-100 rating
- **Sleep Movement**: Restlessness data
- **Timing**: Sleep start/end timestamps

**API Methods**: `get_sleep_data()`

### 🎯 Training Readiness & Status
- **Training Readiness Score**: Daily readiness assessment
- **Training Status**:
  - Current VO2 Max estimate
  - Training load balance
  - Training status (productive, maintaining, peaking, etc.)
  - Heat/altitude acclimatization status
- **Personal Records**: 15 different PRs tracked (5K, 10K, etc.)

**API Methods**: `get_training_readiness()`, `get_training_status()`, `get_personal_record()`

### 🧘 Stress & Recovery
- **All-Day Stress Levels**: Continuous stress monitoring
- **Average Stress**: Daily average stress score
- **Max Stress**: Peak stress level
- **Stress Timestamps**: When stress occurred
- **Body Battery**:
  - Charged amount
  - Drained amount
  - Current battery level
  - Timestamps

**API Methods**: `get_all_day_stress()`, `get_stress_data()`, `get_body_battery()`

### 🫁 Advanced Health Metrics
- **SPO2 (Blood Oxygen)**:
  - 26 different data points
  - Sleep SPO2 levels
  - Continuous monitoring data
- **Respiration Rate**:
  - 24 different data points
  - Sleep respiration
  - Daily average
- **Hydration**:
  - Daily water intake (ML)
  - Hydration goal
  - Sweat loss estimate
  - Activity-based intake
- **Blood Pressure**: Manual BP readings (4 readings found)
- **Weight Tracking**: Daily weigh-ins with historical data

**API Methods**: `get_spo2_data()`, `get_respiration_data()`, `get_hydration_data()`, `get_blood_pressure()`, `get_daily_weigh_ins()`, `get_body_composition()`

### 🏋️ Activities & Workouts
- **Activity List**: Last N activities with full details
- **Activity Details** (per activity):
  - Duration, distance, pace
  - Average/max heart rate
  - Calories burned
  - Training effect (aerobic & anaerobic)
  - **Activity splits**: Lap-by-lap data
  - **HR zones**: Time in each heart rate zone
  - **Weather conditions**: Temperature, humidity, wind
  - Elevation gain/loss
  - Cadence, power (if available)
- **Workout Library**: 38 structured workouts available
- **Activity Types**: All supported activity types

**API Methods**: `get_activities()`, `get_activities_by_date()`, `get_activity()`, `get_activity_details()`, `get_activity_splits()`, `get_activity_hr_in_timezones()`, `get_activity_weather()`, `get_workouts()`

### 🎖️ Performance Metrics
- **Max Metrics**: Personal bests across different activities
- **VO2 Max**: Estimated aerobic capacity
- **Training Load**: Historical training load data
- **Lactate Threshold**: If available from recent activities
- **Personal Records**: PRs across 15+ categories

**API Methods**: `get_max_metrics()`, `get_training_status()`, `get_personal_record()`

### 📱 Device Information
- **Devices**: Connected Garmin devices (found: Enduro 3)
- **Last Sync**: Device synchronization status
- **Device Settings**: Configuration and capabilities
- **Solar Data**: Solar charging data (if applicable)
- **Alarms**: Device alarms

**API Methods**: `get_devices()`, `get_device_last_used()`, `get_device_settings()`, `get_device_solar_data()`, `get_device_alarms()`

---

## 🔑 KEY DATA FOR AI TRAINING ANALYSIS

### Daily Readiness Calculation Inputs:
1. **Sleep Quality** ✅
   - Duration: 7.3 hours
   - Sleep stages breakdown
   - Sleep score: Available

2. **HRV (Heart Rate Variability)** ✅
   - Current HRV readings
   - Historical baseline (7-day, 30-day)
   - Sleep HRV measurements

3. **Resting Heart Rate** ✅
   - Current: 42 bpm
   - Historical baseline
   - Trend analysis

4. **Training Load** ✅
   - Acute load (7-day)
   - Chronic load (28-day)
   - Training status

5. **Stress Levels** ✅
   - All-day stress monitoring
   - Average/max stress
   - Stress timestamps

6. **Body Battery** ✅
   - Current energy level
   - Charged/drained amounts
   - Recovery status

7. **Activity History** ✅
   - Recent workouts
   - Training effect
   - Recovery time

### Training Plan Generation Inputs:
1. **Current Fitness Level** ✅
   - VO2 Max estimate
   - Recent pace/HR relationship
   - Personal records
   - Training status

2. **Recovery Metrics** ✅
   - Sleep, HRV, RHR
   - Stress levels
   - Body battery

3. **Training History** ✅
   - Last 90 days of activities
   - Training load progression
   - Workout types performed

4. **Health Constraints** ✅
   - Blood pressure (if tracked)
   - Body composition changes
   - Injury indicators (via activity gaps)

---

## ⚠️ NOT AVAILABLE / LIMITED

### Requires Date Parameters (but available):
- Endurance Score: `get_endurance_score(start_date, end_date)`
- Hill Score: `get_hill_score(start_date, end_date)`
- Fitness Age: `get_fitnessage_data()` - parameter issues

### Requires User Profile ID:
- Gear tracking: `get_gear(userProfileNumber)`
- Gear stats: `get_gear_stats(userProfileNumber)`

### Social/Challenges (Available but less relevant):
- Badge challenges
- Adhoc challenges
- Virtual challenges
- Earned badges

---

## 📊 DATA FRESHNESS

- **Real-time**: Steps, HR, stress (when device synced)
- **Daily**: Sleep, HRV, readiness, stats
- **On-demand**: Activities (after sync)
- **Historical**: All metrics available for past 90+ days

---

## 🎯 RECOMMENDED API USAGE FOR AI OPTIMIZER

### For Daily Readiness Analysis:
```python
# Morning analysis (8 AM daily)
stats = client.get_stats(today)
sleep = client.get_sleep_data(today)
hrv = client.get_hrv_data(today)
hr = client.get_heart_rates(today)
stress = client.get_stress_data(today)
body_battery = client.get_body_battery(today)
training_readiness = client.get_training_readiness(today)
```

### For Training Plan Generation:
```python
# Weekly/monthly analysis
training_status = client.get_training_status(today)
activities = client.get_activities_by_date(start_date, end_date)
max_metrics = client.get_max_metrics(today)
personal_records = client.get_personal_record()
```

### For Workout Analysis:
```python
# Post-workout analysis
activity = client.get_activity(activity_id)
splits = client.get_activity_splits(activity_id)
hr_zones = client.get_activity_hr_in_timezones(activity_id)
weather = client.get_activity_weather(activity_id)
```

---

## ✅ CONCLUSION

**You have access to ALL critical data needed for the AI Training Optimizer:**

1. ✅ Daily readiness metrics (sleep, HRV, RHR, stress)
2. ✅ Training load and status
3. ✅ Detailed activity history
4. ✅ Recovery indicators
5. ✅ Performance trends
6. ✅ Health metrics (SPO2, respiration, hydration)
7. ✅ Workout library for plan generation

**The Garmin API provides comprehensive data for:**
- AI-powered daily workout recommendations
- Adaptive training plan generation
- Overtraining prevention
- Recovery optimization
- Performance prediction
- Injury risk assessment

**Next Step**: Implement the AI analysis engine using this data!
