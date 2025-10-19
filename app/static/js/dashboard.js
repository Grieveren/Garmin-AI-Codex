document.addEventListener('DOMContentLoaded', () => {
    const refreshBtn = document.getElementById('refresh-btn');
    const syncBtn = document.getElementById('sync-btn');
    const languageToggle = document.getElementById('language-toggle');
    const themeToggle = document.getElementById('theme-toggle');
    const toastContainer = document.getElementById('toast-container');
    const dateElement = document.getElementById('current-date');

    const THEME_KEY = 'dashboard-theme';
    const LANGUAGE_KEY = 'dashboard-language';
    const FALLBACK_LANGUAGE = 'en';

    const translations = {
        en: {
            'meta.title': 'AI Training Optimizer - Dashboard',
            'header.title': '🏃 AI Training Optimizer',
            'button.language': '🇬🇧 English',
            'button.sync': '⬇️ Sync Data',
            'button.refresh': '🔄 Refresh',
            'loading.message': 'Analyzing your Garmin data with Claude AI...',
            'readiness.heading': "Today's Readiness",
            'confidence.label': 'Confidence: {value}',
            'trend.title': '7-day trend',
            'trend.need_more': 'Need more history',
            'recommendation.high_intensity': 'HIGH INTENSITY',
            'recommendation.moderate': 'MODERATE',
            'recommendation.easy': 'EASY',
            'recommendation.rest': 'REST',
            'workout.heading': '💪 Suggested Workout',
            'workout.duration': 'Duration',
            'workout.intensity': 'Intensity',
            'workout.rationale_heading': 'Why this workout?',
            'workout.duration_value': '{minutes} min',
            'workout.intensity_value': '{intensity} / 10',
            'enhanced.heading': '🔬 Enhanced Recovery Metrics',
            'enhanced.training_readiness': 'Training Readiness',
            'enhanced.vo2_max': 'VO₂ Max',
            'enhanced.training_status': 'Training Status',
            'enhanced.spo2': 'Blood Oxygen',
            'enhanced.respiration': 'Respiration',
            'enhanced.not_available': 'Not available',
            'enhanced.respiration_value': '{value} breaths/min',
            'enhanced.spo2_value': '{value}%{min_part}',
            'enhanced.spo2_min_part': ' (min: {value}%)',
            'factors.heading': '✅ Key Factors',
            'tips.heading': '💡 Recovery Tips',
            'red_flags.heading': '⚠️ Things to Watch',
            'analysis.heading': '🤖 AI Analysis',
            'list.empty': 'No data available.',
            'toast.sync_success': 'Sync successful! Refreshing with latest data...',
            'toast.sync_failure': 'Sync failed: {error}',
            'toast.load_failure': 'Failed to load recommendation: {error}',
            'error.loading_title': 'Error loading recommendation:',
            'status.acwr': 'ACWR · {ratio} ({status})',
            'status.last_sync': 'Last sync · {label}',
            'status.last_sync_unknown': 'Last sync · unknown',
            'status.just_now': 'just now',
            'status.minutes_ago': '{minutes} min ago',
            'status.hours_ago': '{hours} hr{plural} ago',
            'status.days_ago': '{days} day{plural} ago',
            'status.sync_in_progress': '⏳ Syncing...',
            'summary.activities': 'Activities · {count}',
            'summary.distance': 'Distance · {distance} km',
            'summary.duration': 'Time · {duration} min',
            'language.aria': 'Toggle language',
            'language.label.en': '🇬🇧 English',
            'language.label.de': '🇩🇪 Deutsch',
            'theme.dark': '🌙 Dark',
            'theme.light': '☀️ Light',
            'acwr.status.high': 'High',
            'acwr.status.moderate': 'Moderate',
            'acwr.status.low': 'Low',
            'acwr.status.optimal': 'Optimal',
            'acwr.status.elevated': 'Elevated',
            'acwr.status.warning': 'Warning',
            'acwr.status.unknown': 'Unknown',
        },
        de: {
            'meta.title': 'KI Trainings-Optimierer - Dashboard',
            'header.title': '🏃 KI Trainings-Optimierer',
            'button.language': '🇩🇪 Deutsch',
            'button.sync': '⬇️ Daten synchronisieren',
            'button.refresh': '🔄 Aktualisieren',
            'loading.message': 'Analysiere deine Garmin-Daten mit Claude AI ...',
            'readiness.heading': 'Heutige Bereitschaft',
            'confidence.label': 'Vertrauen: {value}',
            'trend.title': '7-Tage-Trend',
            'trend.need_more': 'Mehr Verlauf nötig',
            'recommendation.high_intensity': 'HOHE INTENSITÄT',
            'recommendation.moderate': 'MODERAT',
            'recommendation.easy': 'LOCKER',
            'recommendation.rest': 'RUHETAG',
            'workout.heading': '💪 Vorgeschlagenes Workout',
            'workout.duration': 'Dauer',
            'workout.intensity': 'Intensität',
            'workout.rationale_heading': 'Warum dieses Workout?',
            'workout.duration_value': '{minutes} Min.',
            'workout.intensity_value': '{intensity} / 10',
            'enhanced.heading': '🔬 Erweiterte Erholungsmetriken',
            'enhanced.training_readiness': 'Trainingsbereitschaft',
            'enhanced.vo2_max': 'VO₂max',
            'enhanced.training_status': 'Trainingsstatus',
            'enhanced.spo2': 'Sauerstoffsättigung',
            'enhanced.respiration': 'Atmung',
            'enhanced.not_available': 'Nicht verfügbar',
            'enhanced.respiration_value': '{value} Atemzüge/Min.',
            'enhanced.spo2_value': '{value}%{min_part}',
            'enhanced.spo2_min_part': ' (Min.: {value}%)',
            'factors.heading': '✅ Wichtige Faktoren',
            'tips.heading': '💡 Erholungstipps',
            'red_flags.heading': '⚠️ Dinge zum Beobachten',
            'analysis.heading': '🤖 KI-Analyse',
            'list.empty': 'Keine Daten verfügbar.',
            'toast.sync_success': 'Synchronisierung erfolgreich! Lade aktuelle Daten ...',
            'toast.sync_failure': 'Synchronisierung fehlgeschlagen: {error}',
            'toast.load_failure': 'Empfehlung konnte nicht geladen werden: {error}',
            'error.loading_title': 'Fehler beim Laden der Empfehlung:',
            'status.acwr': 'ACWR · {ratio} ({status})',
            'status.last_sync': 'Letzte Synchronisierung · {label}',
            'status.last_sync_unknown': 'Letzte Synchronisierung · unbekannt',
            'status.just_now': 'soeben',
            'status.minutes_ago': 'vor {minutes} Min.',
            'status.hours_ago': 'vor {hours} Std.',
            'status.days_ago': 'vor {days} Tag{plural}',
            'status.sync_in_progress': '⏳ Synchronisiere ...',
            'summary.activities': 'Aktivitäten · {count}',
            'summary.distance': 'Distanz · {distance} km',
            'summary.duration': 'Zeit · {duration} Min.',
            'language.aria': 'Sprache umschalten',
            'language.label.en': '🇬🇧 Englisch',
            'language.label.de': '🇩🇪 Deutsch',
            'theme.dark': '🌙 Dunkel',
            'theme.light': '☀️ Hell',
            'acwr.status.high': 'Hoch',
            'acwr.status.moderate': 'Mittel',
            'acwr.status.low': 'Niedrig',
            'acwr.status.optimal': 'Optimal',
            'acwr.status.elevated': 'Erhöht',
            'acwr.status.warning': 'Warnung',
            'acwr.status.unknown': 'Unbekannt',
        },
    };

    const ACCEPT_LANGUAGE_HEADERS = {
        en: 'en-US,en;q=0.9',
        de: 'de-DE,de;q=0.9,en;q=0.5',
    };

    const dateLocales = {
        en: 'en-US',
        de: 'de-DE',
    };

    let currentLanguage = localStorage.getItem(LANGUAGE_KEY) ?? FALLBACK_LANGUAGE;
    if (!translations[currentLanguage]) {
        currentLanguage = FALLBACK_LANGUAGE;
    }

    let latestRecommendation = null;
   let lastSyncIso = null;
   let latestLoadSummary = null;

    function getAcceptLanguageHeader(lang = currentLanguage) {
        return ACCEPT_LANGUAGE_HEADERS[lang] ?? lang;
    }

    function normalizeLanguageCode(lang) {
        if (!lang) {
            return null;
        }
        const trimmed = lang.trim().toLowerCase();
        if (!trimmed) {
            return null;
        }
        if (trimmed.includes('-')) {
            return trimmed.split('-')[0];
        }
        return trimmed;
    }

    applyStoredTheme();
    setLanguage(currentLanguage, { save: false, revalidate: false });

    themeToggle?.addEventListener('click', toggleTheme);
    languageToggle?.addEventListener('click', () => {
        const next = currentLanguage === 'en' ? 'de' : 'en';
        setLanguage(next, { revalidate: true });
    });
    refreshBtn?.addEventListener('click', () => {
        void loadRecommendation();
    });
    syncBtn?.addEventListener('click', () => {
        void syncData();
    });

    void loadRecommendation();

    async function loadRecommendation() {
        const loadingDiv = document.getElementById('loading');
        const contentDiv = document.getElementById('content');
        const errorDiv = document.getElementById('error');

        if (loadingDiv) {
            loadingDiv.style.display = 'block';
        }
        if (contentDiv) {
            contentDiv.style.display = 'none';
        }
        if (errorDiv) {
            errorDiv.style.display = 'none';
        }
        if (refreshBtn) {
            refreshBtn.disabled = true;
        }

        try {
            const response = await fetch('/api/recommendations/today', {
                headers: {
                    'Cache-Control': 'no-cache',
                    'Accept-Language': getAcceptLanguageHeader(),
                },
            });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            handleRecommendationData(data);

            if (loadingDiv) {
                loadingDiv.style.display = 'none';
            }
            if (contentDiv) {
                contentDiv.style.display = 'flex';
            }
        } catch (error) {
            console.error('Error:', error);
            const message = error instanceof Error ? error.message : 'Unknown error';
            renderError(message);
            showToast('toast.load_failure', 'error', { error: message });
            if (loadingDiv) {
                loadingDiv.style.display = 'none';
            }
        } finally {
            if (refreshBtn) {
                refreshBtn.disabled = false;
            }
        }
    }

    function handleRecommendationData(data) {
        latestRecommendation = data;
        latestLoadSummary = data.recent_training_load || {};
        lastSyncIso = data.latest_data_sync || data.generated_at || null;

        const responseLanguage = normalizeLanguageCode(data.language);
        if (responseLanguage && responseLanguage !== currentLanguage) {
            setLanguage(responseLanguage, { save: true, revalidate: false });
        }

        renderRecommendation();
        updateLoadSummary(latestLoadSummary);
        updateAcwrBadge(latestRecommendation.historical_baselines?.acwr);
        renderReadinessTrend(data.readiness_history);
        updateLastSyncChip(lastSyncIso);
    }

    function renderRecommendation() {
        if (!latestRecommendation) {
            return;
        }

        const scoreElement = document.getElementById('readiness-score');
        if (scoreElement) {
            scoreElement.textContent = latestRecommendation.readiness_score;

            if (latestRecommendation.readiness_score >= 80) {
                scoreElement.className = 'readiness-score score-green';
            } else if (latestRecommendation.readiness_score >= 60) {
                scoreElement.className = 'readiness-score score-yellow';
            } else if (latestRecommendation.readiness_score >= 40) {
                scoreElement.className = 'readiness-score score-orange';
            } else {
                scoreElement.className = 'readiness-score score-red';
            }
        }

        const confidenceBadge = document.getElementById('confidence-badge');
        if (confidenceBadge) {
            confidenceBadge.textContent = t('confidence.label', {
                value: latestRecommendation.confidence ?? '--',
            });
        }

        const recBadge = document.getElementById('recommendation-badge');
        if (recBadge) {
            const key = `recommendation.${latestRecommendation.recommendation}`;
            const fallback = latestRecommendation.recommendation
                ? latestRecommendation.recommendation.replace(/_/g, ' ').toUpperCase()
                : '--';
            recBadge.textContent = t(key, { _fallback: fallback });

            if (latestRecommendation.recommendation === 'high_intensity') {
                recBadge.className = 'recommendation-badge badge-high';
            } else if (latestRecommendation.recommendation === 'moderate') {
                recBadge.className = 'recommendation-badge badge-moderate';
            } else if (latestRecommendation.recommendation === 'easy') {
                recBadge.className = 'recommendation-badge badge-easy';
            } else {
                recBadge.className = 'recommendation-badge badge-rest';
            }
        }

        const workout = latestRecommendation.suggested_workout || {};
        const workoutType = document.getElementById('workout-type');
        if (workoutType) {
            workoutType.textContent = workout.type ? workout.type.replace(/_/g, ' ').toUpperCase() : '--';
        }
        const workoutDescription = document.getElementById('workout-description');
        if (workoutDescription) {
            workoutDescription.textContent = workout.description ?? '--';
        }
        const workoutDuration = document.getElementById('workout-duration');
        if (workoutDuration) {
            const minutes = workout.target_duration_minutes ?? '--';
            workoutDuration.textContent = t('workout.duration_value', { minutes });
        }
        const workoutIntensity = document.getElementById('workout-intensity');
        if (workoutIntensity) {
            const intensity = workout.intensity ?? '--';
            workoutIntensity.textContent = t('workout.intensity_value', { intensity });
        }
        const workoutRationale = document.getElementById('workout-rationale');
        if (workoutRationale) {
            workoutRationale.textContent = workout.rationale ?? '--';
        }

        renderList('key-factors', latestRecommendation.key_factors, 'factor-item');

        const redFlagsSection = document.getElementById('red-flags-section');
        if (latestRecommendation.red_flags && latestRecommendation.red_flags.length > 0) {
            redFlagsSection?.setAttribute('style', 'display: block;');
            renderList('red-flags', latestRecommendation.red_flags, 'red-flag-item');
        } else {
            if (redFlagsSection) {
                redFlagsSection.style.display = 'none';
            }
        }

        renderList('recovery-tips', latestRecommendation.recovery_tips, 'tip-item');

        const aiReasoning = document.getElementById('ai-reasoning');
        if (aiReasoning) {
            aiReasoning.textContent = latestRecommendation.ai_reasoning ?? '--';
        }

        renderEnhancedMetrics(latestRecommendation.enhanced_metrics);
    }

    function renderList(containerId, items, itemClass) {
        const container = document.getElementById(containerId);
        if (!container) {
            return;
        }

        container.textContent = '';

        if (!items || items.length === 0) {
            const empty = document.createElement('div');
            empty.className = itemClass;
            empty.textContent = t('list.empty');
            container.appendChild(empty);
            return;
        }

        items.forEach((item) => {
            const div = document.createElement('div');
            div.className = itemClass;
            div.textContent = item;
            container.appendChild(div);
        });
    }

    function renderEnhancedMetrics(metrics) {
        const card = document.getElementById('enhanced-metrics-card');
        if (!card) {
            return;
        }

        if (!metrics) {
            card.style.display = 'none';
            return;
        }

        let hasAnyMetric = false;

        const readinessEl = document.getElementById('garmin-readiness');
        if (readinessEl) {
            if (metrics.training_readiness_score !== null && metrics.training_readiness_score !== undefined) {
                readinessEl.textContent = `${metrics.training_readiness_score}/100`;
                hasAnyMetric = true;
            } else {
                readinessEl.textContent = t('enhanced.not_available');
            }
        }

        const vo2El = document.getElementById('vo2-max');
        if (vo2El) {
            if (metrics.vo2_max) {
                vo2El.textContent = `${metrics.vo2_max} ml/kg/min`;
                hasAnyMetric = true;
            } else {
                vo2El.textContent = t('enhanced.not_available');
            }
        }

        const statusEl = document.getElementById('training-status');
        if (statusEl) {
            if (metrics.training_status) {
                statusEl.textContent = metrics.training_status.replace(/_/g, ' ').toUpperCase();
                hasAnyMetric = true;
            } else {
                statusEl.textContent = t('enhanced.not_available');
            }
        }

        const spo2El = document.getElementById('spo2');
        if (spo2El) {
            if (metrics.spo2_avg) {
                const avg = metrics.spo2_avg.toFixed(1);
                const minPart =
                    metrics.spo2_min !== null && metrics.spo2_min !== undefined
                        ? t('enhanced.spo2_min_part', { value: metrics.spo2_min.toFixed(1) })
                        : '';
                spo2El.textContent = t('enhanced.spo2_value', { value: avg, min_part: minPart });
                hasAnyMetric = true;
            } else {
                spo2El.textContent = t('enhanced.not_available');
            }
        }

        const respirationEl = document.getElementById('respiration');
        if (respirationEl) {
            if (metrics.respiration_avg) {
                respirationEl.textContent = t('enhanced.respiration_value', {
                    value: metrics.respiration_avg.toFixed(1),
                });
                hasAnyMetric = true;
            } else {
                respirationEl.textContent = t('enhanced.not_available');
            }
        }

        card.style.display = hasAnyMetric ? 'block' : 'none';
    }

    async function syncData() {
        if (!syncBtn) {
            return;
        }

        const syncingText = t('status.sync_in_progress');
        const restoreText = () => {
            if (syncBtn) {
                syncBtn.textContent = t('button.sync');
            }
        };

        syncBtn.disabled = true;
        syncBtn.textContent = syncingText;

        try {
            const response = await fetch('/manual/sync/now', {
                method: 'POST',
                headers: {
                    'Accept-Language': getAcceptLanguageHeader(),
                },
            });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            await response.json();
            showToast('toast.sync_success', 'success');
            await loadRecommendation();
        } catch (error) {
            console.error('Sync error:', error);
            const message = error instanceof Error ? error.message : 'Unknown error';
            showToast('toast.sync_failure', 'error', { error: message });
        } finally {
            syncBtn.disabled = false;
            restoreText();
        }
    }

    function renderError(message) {
        const errorDiv = document.getElementById('error');
        if (!errorDiv) {
            return;
        }

        errorDiv.textContent = '';

        const wrapper = document.createElement('div');
        wrapper.className = 'error-card';

        const title = document.createElement('strong');
        title.textContent = t('error.loading_title');
        wrapper.appendChild(title);
        wrapper.appendChild(document.createElement('br'));
        wrapper.appendChild(document.createTextNode(message));

        errorDiv.appendChild(wrapper);
        errorDiv.style.display = 'block';
    }

    function showToast(messageKey, variant = 'info', vars = {}) {
        if (!toastContainer) {
            return;
        }

        const toast = document.createElement('div');
        toast.className = `toast toast--${variant}`;
        toast.textContent = t(messageKey, vars);
        toastContainer.appendChild(toast);

        requestAnimationFrame(() => {
            toast.classList.add('toast--visible');
        });

        setTimeout(() => {
            toast.classList.remove('toast--visible');
            setTimeout(() => toast.remove(), 300);
        }, 5000);
    }

    function updateLoadSummary(summary) {
        const activityCount =
            summary && Number.isFinite(summary.activity_count) ? summary.activity_count : '--';
        const distanceValue =
            summary &&
            typeof summary.total_distance_km === 'number' &&
            Number.isFinite(summary.total_distance_km)
                ? summary.total_distance_km
                : '--';
        const durationValue =
            summary &&
            typeof summary.total_duration_min === 'number' &&
            Number.isFinite(summary.total_duration_min)
                ? Math.round(summary.total_duration_min)
                : '--';

        const countEl = document.getElementById('load-summary-count');
        if (countEl) {
            countEl.textContent = t('summary.activities', { count: activityCount });
        }
        const distanceEl = document.getElementById('load-summary-distance');
        if (distanceEl) {
            distanceEl.textContent = t('summary.distance', { distance: distanceValue });
        }
        const durationEl = document.getElementById('load-summary-duration');
        if (durationEl) {
            durationEl.textContent = t('summary.duration', { duration: durationValue });
        }
    }

    function updateAcwrBadge(acwrData) {
        const badge = document.getElementById('acwr-badge');
        if (!badge) {
            return;
        }

        if (!acwrData || acwrData.acwr == null) {
            badge.style.display = 'none';
            badge.textContent = '';
            badge.className = 'metric-chip';
            return;
        }

        const ratio = typeof acwrData.acwr === 'number' ? acwrData.acwr.toFixed(2) : acwrData.acwr;
        const statusKey = (acwrData.status || 'unknown').toLowerCase();
        const translatedStatus = t(`acwr.status.${statusKey}`, {
            _fallback: (acwrData.status || 'unknown').replace(/_/g, ' '),
        });
        const risk = (acwrData.injury_risk || 'unknown').toLowerCase();

        badge.style.display = 'inline-flex';
        badge.textContent = t('status.acwr', { ratio, status: translatedStatus });
        badge.className = 'metric-chip';

        if (risk === 'high') {
            badge.classList.add('metric-chip--danger');
        } else if (risk === 'moderate') {
            badge.classList.add('metric-chip--caution');
        } else {
            badge.classList.add('metric-chip--good');
        }
    }

    function renderReadinessTrend(history) {
        const container = document.getElementById('readiness-trend');
        if (!container) {
            return;
        }

        container.innerHTML = '';

        if (!history || history.length < 2) {
            const empty = document.createElement('span');
            empty.className = 'trend-empty';
            empty.textContent = t('trend.need_more');
            container.appendChild(empty);
            return;
        }

        const width = 160;
        const height = 50;
        const scores = history.map((item) => item.score);
        const max = Math.max(...scores);
        const min = Math.min(...scores);
        const range = max - min || 1;
        const step = width / (scores.length - 1 || 1);

        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
        svg.setAttribute('preserveAspectRatio', 'none');
        svg.classList.add('trend-sparkline');

        const points = scores
            .map((score, index) => {
                const x = index * step;
                const normalized = (score - min) / range;
                const y = height - normalized * (height - 10) - 5;
                return `${x.toFixed(1)},${y.toFixed(1)}`;
            })
            .join(' ');

        const polyline = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
        polyline.setAttribute('points', points);
        polyline.setAttribute('fill', 'none');
        polyline.setAttribute('stroke', 'var(--accent-primary)');
        polyline.setAttribute('stroke-width', '3');
        polyline.setAttribute('stroke-linecap', 'round');
        polyline.setAttribute('stroke-linejoin', 'round');

        const gradient = document.createElementNS('http://www.w3.org/2000/svg', 'linearGradient');
        gradient.setAttribute('id', 'trendGradient');
        gradient.setAttribute('x1', '0');
        gradient.setAttribute('x2', '0');
        gradient.setAttribute('y1', '0');
        gradient.setAttribute('y2', '1');

        const stop1 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
        stop1.setAttribute('offset', '0%');
        stop1.setAttribute('stop-color', 'var(--accent-primary)');
        stop1.setAttribute('stop-opacity', '0.35');

        const stop2 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
        stop2.setAttribute('offset', '100%');
        stop2.setAttribute('stop-color', 'var(--accent-primary)');
        stop2.setAttribute('stop-opacity', '0');

        gradient.appendChild(stop1);
        gradient.appendChild(stop2);

        const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
        defs.appendChild(gradient);

        const area = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
        area.setAttribute('points', `0,${height} ${points} ${width},${height}`);
        area.setAttribute('fill', 'url(#trendGradient)');
        area.setAttribute('stroke', 'none');

        svg.appendChild(defs);
        svg.appendChild(area);
        svg.appendChild(polyline);

        container.appendChild(svg);

        const labels = document.createElement('div');
        labels.className = 'trend-labels';
        labels.innerHTML = `<span>${history[0].score}</span><span>${
            history[history.length - 1].score
        }</span>`;
        container.appendChild(labels);
    }

    function updateLastSyncChip(isoString) {
        const chip = document.getElementById('last-sync-chip');
        if (!chip) {
            return;
        }

        if (!isoString) {
            chip.textContent = t('status.last_sync_unknown');
            chip.className = 'status-chip status-chip--old';
            return;
        }

        const parsed = new Date(isoString);
        if (Number.isNaN(parsed.getTime())) {
            chip.textContent = t('status.last_sync_unknown');
            chip.className = 'status-chip status-chip--old';
            return;
        }

        const now = new Date();
        const diffMinutes = Math.floor((now.getTime() - parsed.getTime()) / 60000);

        let label;
        if (diffMinutes < 1) {
            label = t('status.just_now');
        } else if (diffMinutes < 60) {
            label = t('status.minutes_ago', { minutes: diffMinutes });
        } else if (diffMinutes < 1440) {
            const hours = Math.floor(diffMinutes / 60);
            label = t('status.hours_ago', {
                hours,
                plural: hours > 1 ? 's' : '',
            });
        } else {
            const days = Math.floor(diffMinutes / 1440);
            label = t('status.days_ago', {
                days,
                plural: currentLanguage === 'de' ? (days > 1 ? 'en' : '') : days > 1 ? 's' : '',
            });
        }

        chip.textContent = t('status.last_sync', { label });
        chip.className = 'status-chip';

        if (diffMinutes <= 90) {
            chip.classList.add('status-chip--fresh');
        } else if (diffMinutes <= 240) {
            chip.classList.add('status-chip--stale');
        } else {
            chip.classList.add('status-chip--old');
        }
    }

    function applyStoredTheme() {
        const stored = localStorage.getItem(THEME_KEY);
        const isDark = stored === 'dark';
        document.body.classList.toggle('dark-theme', isDark);
        updateThemeToggleLabel(isDark);
    }

    function toggleTheme() {
        const isDark = document.body.classList.toggle('dark-theme');
        localStorage.setItem(THEME_KEY, isDark ? 'dark' : 'light');
        updateThemeToggleLabel(isDark);
    }

    function setLanguage(lang, { save = true, revalidate = false } = {}) {
        if (!translations[lang]) {
            lang = FALLBACK_LANGUAGE;
        }
        currentLanguage = lang;

        if (save) {
            localStorage.setItem(LANGUAGE_KEY, currentLanguage);
        }

        document.documentElement.lang = currentLanguage;

        applyStaticTranslations();
        updateDateDisplay();
        updateThemeToggleLabel(document.body.classList.contains('dark-theme'));
        updateLoadSummary(latestLoadSummary);
        updateAcwrBadge(latestRecommendation?.historical_baselines?.acwr);
        renderReadinessTrend(latestRecommendation?.readiness_history);
        updateLastSyncChip(lastSyncIso);
        if (latestRecommendation) {
            renderRecommendation();
        }

        if (revalidate) {
            void loadRecommendation();
        }
    }

    function applyStaticTranslations() {
        document.title = t('meta.title');

        document.querySelectorAll('[data-i18n]').forEach((el) => {
            const key = el.dataset.i18n;
            if (!key) {
                return;
            }
            if (el.id === 'language-toggle') {
                return;
            }
            el.textContent = t(key);
        });

        updateActionButtons();
    }

    function updateActionButtons() {
        if (languageToggle) {
            const labelKey = `language.label.${currentLanguage}`;
            languageToggle.textContent = t(labelKey);
            languageToggle.setAttribute('aria-label', t('language.aria'));
        }
        if (syncBtn) {
            syncBtn.textContent = t('button.sync');
        }
        if (refreshBtn) {
            refreshBtn.textContent = t('button.refresh');
        }
    }

    function updateThemeToggleLabel(isDark) {
        if (!themeToggle) {
            return;
        }
        themeToggle.textContent = isDark ? t('theme.light') : t('theme.dark');
    }

    function updateDateDisplay() {
        if (!dateElement) {
            return;
        }
        const locale = dateLocales[currentLanguage] ?? dateLocales[FALLBACK_LANGUAGE];
        const today = new Date();
        dateElement.textContent = today.toLocaleDateString(locale, {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric',
        });
    }

    function t(key, vars = {}) {
        const langDict = translations[currentLanguage] ?? {};
        const fallbackDict = translations[FALLBACK_LANGUAGE] ?? {};
        let template = langDict[key];
        if (template === undefined) {
            template = fallbackDict[key];
        }
        if (template === undefined) {
            template = vars._fallback ?? key;
        }

        return template.replace(/\{(\w+)\}/g, (match, varName) => {
            if (vars[varName] === undefined) {
                return '';
            }
            return String(vars[varName]);
        });
    }
});
