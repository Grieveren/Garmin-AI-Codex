document.addEventListener('DOMContentLoaded', () => {
    const refreshBtn = document.getElementById('refresh-btn');
    const syncBtn = document.getElementById('sync-btn');
    const toastContainer = document.getElementById('toast-container');
    const themeToggle = document.getElementById('theme-toggle');
    const dateElement = document.getElementById('current-date');
    const THEME_KEY = 'dashboard-theme';

    if (dateElement) {
        const today = new Date();
        dateElement.textContent = today.toLocaleDateString('en-US', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric',
        });
    }

    applyStoredTheme();
    themeToggle?.addEventListener('click', toggleTheme);
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
                headers: { 'Cache-Control': 'no-cache' },
            });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            displayRecommendation(data);
            updateLastSyncChip(data.latest_data_sync || data.generated_at);

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
            showToast(`Failed to load recommendation: ${message}`, 'error');
            if (loadingDiv) {
                loadingDiv.style.display = 'none';
            }
        } finally {
            if (refreshBtn) {
                refreshBtn.disabled = false;
            }
        }
    }

    function displayRecommendation(data) {
        const scoreElement = document.getElementById('readiness-score');
        if (scoreElement) {
            scoreElement.textContent = data.readiness_score;

            if (data.readiness_score >= 80) {
                scoreElement.className = 'readiness-score score-green';
            } else if (data.readiness_score >= 60) {
                scoreElement.className = 'readiness-score score-yellow';
            } else if (data.readiness_score >= 40) {
                scoreElement.className = 'readiness-score score-orange';
            } else {
                scoreElement.className = 'readiness-score score-red';
            }
        }

        const confidenceBadge = document.getElementById('confidence-badge');
        if (confidenceBadge) {
            confidenceBadge.textContent = `Confidence: ${data.confidence}`;
        }

        const recBadge = document.getElementById('recommendation-badge');
        if (recBadge) {
            const recText = data.recommendation.replace('_', ' ').toUpperCase();
            recBadge.textContent = recText;

            if (data.recommendation === 'high_intensity') {
                recBadge.className = 'recommendation-badge badge-high';
            } else if (data.recommendation === 'moderate') {
                recBadge.className = 'recommendation-badge badge-moderate';
            } else if (data.recommendation === 'easy') {
                recBadge.className = 'recommendation-badge badge-easy';
            } else {
                recBadge.className = 'recommendation-badge badge-rest';
            }
        }

        updateLoadSummary(data.recent_training_load || {});
        updateAcwrBadge(data.historical_baselines?.acwr);
        renderReadinessTrend(data.readiness_history);

        const workout = data.suggested_workout;
        const workoutType = document.getElementById('workout-type');
        if (workoutType) {
            workoutType.textContent = workout.type.replace('_', ' ').toUpperCase();
        }
        const workoutDescription = document.getElementById('workout-description');
        if (workoutDescription) {
            workoutDescription.textContent = workout.description;
        }
        const workoutDuration = document.getElementById('workout-duration');
        if (workoutDuration) {
            workoutDuration.textContent = `${workout.target_duration_minutes} min`;
        }
        const workoutIntensity = document.getElementById('workout-intensity');
        if (workoutIntensity) {
            workoutIntensity.textContent = `${workout.intensity} / 10`;
        }
        const workoutRationale = document.getElementById('workout-rationale');
        if (workoutRationale) {
            workoutRationale.textContent = workout.rationale;
        }

        renderList('key-factors', data.key_factors, 'factor-item');

        if (data.red_flags && data.red_flags.length > 0) {
            const section = document.getElementById('red-flags-section');
            if (section) {
                section.style.display = 'block';
            }
            renderList('red-flags', data.red_flags, 'red-flag-item');
        } else {
            const section = document.getElementById('red-flags-section');
            if (section) {
                section.style.display = 'none';
            }
        }

        renderList('recovery-tips', data.recovery_tips, 'tip-item');

        const aiReasoning = document.getElementById('ai-reasoning');
        if (aiReasoning) {
            aiReasoning.textContent = data.ai_reasoning;
        }

        renderEnhancedMetrics(data.enhanced_metrics);
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
            empty.textContent = 'No data available.';
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

        if (metrics.training_readiness_score !== null && metrics.training_readiness_score !== undefined) {
            const el = document.getElementById('garmin-readiness');
            if (el) {
                el.textContent = `${metrics.training_readiness_score}/100`;
            }
            hasAnyMetric = true;
        } else {
            const el = document.getElementById('garmin-readiness');
            if (el) {
                el.textContent = 'Not available';
            }
        }

        if (metrics.vo2_max) {
            const el = document.getElementById('vo2-max');
            if (el) {
                el.textContent = `${metrics.vo2_max} ml/kg/min`;
            }
            hasAnyMetric = true;
        } else {
            const el = document.getElementById('vo2-max');
            if (el) {
                el.textContent = 'Not available';
            }
        }

        if (metrics.training_status) {
            const el = document.getElementById('training-status');
            if (el) {
                el.textContent = metrics.training_status.replace(/_/g, ' ').toUpperCase();
            }
            hasAnyMetric = true;
        } else {
            const el = document.getElementById('training-status');
            if (el) {
                el.textContent = 'Not available';
            }
        }

        if (metrics.spo2_avg) {
            let spo2Text = `${metrics.spo2_avg.toFixed(1)}%`;
            if (metrics.spo2_min) {
                spo2Text += ` (min: ${metrics.spo2_min.toFixed(1)}%)`;
            }
            const el = document.getElementById('spo2');
            if (el) {
                el.textContent = spo2Text;
            }
            hasAnyMetric = true;
        } else {
            const el = document.getElementById('spo2');
            if (el) {
                el.textContent = 'Not available';
            }
        }

        if (metrics.respiration_avg) {
            const el = document.getElementById('respiration');
            if (el) {
                el.textContent = `${metrics.respiration_avg.toFixed(1)} breaths/min`;
            }
            hasAnyMetric = true;
        } else {
            const el = document.getElementById('respiration');
            if (el) {
                el.textContent = 'Not available';
            }
        }

        card.style.display = hasAnyMetric ? 'block' : 'none';
    }

    async function syncData() {
        if (!syncBtn) {
            return;
        }

        const originalText = syncBtn.textContent;

        syncBtn.disabled = true;
        syncBtn.textContent = '⏳ Syncing...';

        try {
            const response = await fetch('/manual/sync/now', { method: 'POST' });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            await response.json();
            showToast('Sync successful! Refreshing with latest data...', 'success');
            await loadRecommendation();
        } catch (error) {
            console.error('Sync error:', error);
            const message = error instanceof Error ? error.message : 'Unknown error';
            showToast(`Sync failed: ${message}`, 'error');
        } finally {
            syncBtn.disabled = false;
            syncBtn.textContent = originalText;
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
        title.textContent = 'Error loading recommendation:';
        wrapper.appendChild(title);
        wrapper.appendChild(document.createElement('br'));
        wrapper.appendChild(document.createTextNode(message));

        errorDiv.appendChild(wrapper);
        errorDiv.style.display = 'block';
    }

    function showToast(message, variant = 'info') {
        if (!toastContainer) {
            return;
        }

        const toast = document.createElement('div');
        toast.className = `toast toast--${variant}`;
        toast.textContent = message;
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
        const count = summary.activity_count ?? '--';
        const distance = summary.total_distance_km != null ? summary.total_distance_km : '--';
        const duration =
            summary.total_duration_min != null ? Math.round(summary.total_duration_min) : '--';

        const countEl = document.getElementById('load-summary-count');
        if (countEl) {
            countEl.textContent = `Activities · ${count}`;
        }
        const distanceEl = document.getElementById('load-summary-distance');
        if (distanceEl) {
            distanceEl.textContent = `Distance · ${distance} km`;
        }
        const durationEl = document.getElementById('load-summary-duration');
        if (durationEl) {
            durationEl.textContent = `Time · ${duration} min`;
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

        const acwr =
            typeof acwrData.acwr === 'number' ? acwrData.acwr.toFixed(2) : acwrData.acwr;
        const status = acwrData.status?.replace(/_/g, ' ') || 'unknown';
        const risk = (acwrData.injury_risk || 'unknown').toLowerCase();

        badge.style.display = 'inline-flex';
        badge.textContent = `ACWR · ${acwr} (${status})`;
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
            empty.textContent = 'Need more history';
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
        labels.innerHTML = `<span>${history[0].score}</span><span>${history[history.length - 1].score}</span>`;
        container.appendChild(labels);
    }

    function updateLastSyncChip(isoString) {
        const chip = document.getElementById('last-sync-chip');
        if (!chip) {
            return;
        }

        if (!isoString) {
            chip.textContent = 'Last sync · unknown';
            chip.className = 'status-chip status-chip--old';
            return;
        }

        const parsed = new Date(isoString);
        if (Number.isNaN(parsed.getTime())) {
            chip.textContent = 'Last sync · unknown';
            chip.className = 'status-chip status-chip--old';
            return;
        }

        const now = new Date();
        const diffMinutes = Math.floor((now.getTime() - parsed.getTime()) / 60000);

        let label;
        if (diffMinutes < 1) {
            label = 'just now';
        } else if (diffMinutes < 60) {
            label = `${diffMinutes} min ago`;
        } else if (diffMinutes < 1440) {
            const hours = Math.floor(diffMinutes / 60);
            label = `${hours} hr${hours > 1 ? 's' : ''} ago`;
        } else {
            const days = Math.floor(diffMinutes / 1440);
            label = `${days} day${days > 1 ? 's' : ''} ago`;
        }

        chip.textContent = `Last sync · ${label}`;
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
        if (stored === 'dark') {
            document.body.classList.add('dark-theme');
            if (themeToggle) {
                themeToggle.textContent = '☀️ Light';
            }
        } else if (themeToggle) {
            themeToggle.textContent = '🌙 Dark';
        }
    }

    function toggleTheme() {
        const isDark = document.body.classList.toggle('dark-theme');
        localStorage.setItem(THEME_KEY, isDark ? 'dark' : 'light');
        if (themeToggle) {
            themeToggle.textContent = isDark ? '☀️ Light' : '🌙 Dark';
        }
    }
});
